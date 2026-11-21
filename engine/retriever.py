"""Hybrid Retriever combining SQLite FTS5 BM25 and NumPy In-Memory Vector Search."""

import json
import re
import sqlite3
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from engine.models import Chunk, RetrievedEvidence
from engine.query import ProcessedQuery


class HybridRetriever:
    """Fast hybrid retriever with zero heavy external vector database dependencies."""

    def __init__(
        self,
        db_path: str,
        embedding_fn: Optional[Callable[[List[str]], np.ndarray]] = None,
        rrf_k: int = 60,
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
        router_boost_weight: float = 0.2,
    ):
        """Initialize hybrid retriever.

        Args:
            db_path: Path to knowledge.sqlite database.
            embedding_fn: Callable that generates normalized embeddings for text queries.
            rrf_k: Smoothing constant for Reciprocal Rank Fusion (default: 60).
            bm25_weight: Weight for BM25 rank in RRF.
            vector_weight: Weight for vector rank in RRF.
            router_boost_weight: Weight added for chunks matching router rules.
        """
        self.db_path = db_path
        self.embedding_fn = embedding_fn
        self.rrf_k = rrf_k
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self.router_boost_weight = router_boost_weight

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._load_vector_cache()

    def _load_vector_cache(self) -> None:
        """Load all chunk IDs and embedding BLOBs into in-memory NumPy matrix."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT chunk_id, embedding FROM chunks WHERE embedding IS NOT NULL")
        rows = cursor.fetchall()

        self.chunk_ids: List[str] = []
        vectors: List[np.ndarray] = []

        for row in rows:
            cid = row["chunk_id"]
            blob = row["embedding"]
            if blob:
                vec = np.frombuffer(blob, dtype=np.float32)
                self.chunk_ids.append(cid)
                vectors.append(vec)

        if vectors:
            self.embedding_matrix = np.vstack(vectors)
            # Ensure row-wise L2 normalization
            norms = np.linalg.norm(self.embedding_matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1e-10
            self.embedding_matrix = self.embedding_matrix / norms
        else:
            self.embedding_matrix = np.empty((0, 384), dtype=np.float32)

        self.chunk_id_to_idx = {cid: idx for idx, cid in enumerate(self.chunk_ids)}

    def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        """Fetch a single chunk by chunk_id from SQLite."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT chunk_id, law_no, law_title, path, page, edition, source_type, text
            FROM chunks WHERE chunk_id = ?
            """,
            (chunk_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        path_data = []
        if row["path"]:
            try:
                path_data = json.loads(row["path"])
            except Exception:
                path_data = [row["path"]]

        return Chunk(
            chunk_id=row["chunk_id"],
            law_no=row["law_no"],
            law_title=row["law_title"],
            path=path_data,
            page=row["page"],
            edition=row["edition"],
            source_type=row["source_type"] or "original",
            text=row["text"],
        )

    def search_bm25(self, query_text: str, limit: int = 20) -> List[Tuple[str, float]]:
        """Perform BM25 search via SQLite FTS5."""
        cursor = self._conn.cursor()
        words = [w for w in re.findall(r"\b\w+\b", query_text) if len(w) > 1]
        if not words:
            return []

        clean_q = " OR ".join([f'"{w}"' for w in words])
        try:
            sql = """
                SELECT chunk_id, rank
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            cursor.execute(sql, (clean_q, limit))
            # In SQLite FTS5, lower rank is better (negative value). Convert to positive score.
            results = [(row["chunk_id"], -float(row["rank"])) for row in cursor.fetchall()]
            return results
        except sqlite3.OperationalError:
            # Fallback to LIKE if FTS fails or special characters are present
            sql = """
                SELECT chunk_id FROM chunks
                WHERE text LIKE ?
                LIMIT ?
            """
            cursor.execute(sql, (f"%{query_text[:50]}%", limit))
            return [(row["chunk_id"], 1.0) for row in cursor.fetchall()]

    def search_vector(self, query_vec: np.ndarray, limit: int = 20) -> List[Tuple[str, float]]:
        """Perform in-memory cosine similarity search via NumPy dot product."""
        if len(self.chunk_ids) == 0:
            return []

        # Ensure query_vec is normalized 1D float32
        q = query_vec.astype(np.float32).flatten()
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm

        # Dot product with all cached normalized embeddings (< 1ms for thousands of chunks)
        scores = np.dot(self.embedding_matrix, q)

        # Top indices
        top_k_indices = np.argsort(scores)[::-1][:limit]
        return [(self.chunk_ids[idx], float(scores[idx])) for idx in top_k_indices]

    def retrieve(
        self,
        processed_query: ProcessedQuery,
        top_k: int = 5,
        search_limit: int = 25,
    ) -> List[RetrievedEvidence]:
        """Perform hybrid retrieval using Reciprocal Rank Fusion (RRF) and router boosts."""
        # 1. Lexical BM25 search
        bm25_hits = self.search_bm25(processed_query.full_search_text, limit=search_limit)

        # 2. Vector search if embedding function is available
        vector_hits: List[Tuple[str, float]] = []
        if self.embedding_fn and len(self.chunk_ids) > 0:
            query_embeddings = self.embedding_fn([processed_query.standalone_query])
            if len(query_embeddings) > 0:
                vector_hits = self.search_vector(query_embeddings[0], limit=search_limit)

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scores: Dict[str, float] = {}

        for rank, (cid, _) in enumerate(bm25_hits, start=1):
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + self.bm25_weight / (self.rrf_k + rank)

        for rank, (cid, _) in enumerate(vector_hits, start=1):
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + self.vector_weight / (self.rrf_k + rank)

        # 4. Apply Router Boosts
        if processed_query.boosted_sections:
            for cid in list(rrf_scores.keys()):
                chunk = self.get_chunk(cid)
                if not chunk:
                    continue
                # Collect candidate keys for domain-agnostic router matching
                candidates = []
                if chunk.law_no is not None:
                    candidates.append(f"law{chunk.law_no}")
                    candidates.append(str(chunk.law_no))
                if chunk.chunk_id:
                    candidates.append(chunk.chunk_id)
                for p in chunk.path:
                    candidates.append(p.lower().strip())
                if chunk.metadata and "section_id" in chunk.metadata:
                    candidates.append(str(chunk.metadata["section_id"]))

                for candidate in candidates:
                    if candidate in processed_query.boosted_sections:
                        boost = (
                            processed_query.boosted_sections[candidate] * self.router_boost_weight
                        )
                        rrf_scores[cid] += boost
                        break

        # Sort combined results descending by fused score
        sorted_cids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        # Hydrate full chunk objects
        results: List[RetrievedEvidence] = []
        for cid, score in sorted_cids:
            chunk = self.get_chunk(cid)
            if chunk:
                results.append(RetrievedEvidence(chunk=chunk, score=score, retrieval_method="rrf"))

        return results

    def close(self) -> None:
        """Close SQLite database connection."""
        self._conn.close()
