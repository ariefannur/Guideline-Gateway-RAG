"""Unit tests for core engine components."""

import sqlite3

import numpy as np

from engine.context import ContextBuilder
from engine.guardrails import Guardrails
from engine.models import ChatMessage, Chunk, RetrievedEvidence
from engine.query import QueryProcessor
from engine.retriever import HybridRetriever


def test_query_processor_normalization_and_language():
    processor = QueryProcessor()

    # Normalization
    assert processor.normalize("  What IS this?! ") == "what is this?"

    # Language detection
    assert processor.detect_language("Apakah ini aturan yang benar?") == "id"
    assert processor.detect_language("What is the general guideline for this?") == "en"


def test_query_processor_multiturn():
    processor = QueryProcessor()
    history = [
        ChatMessage(role="user", content="Can you explain rule 5?"),
        ChatMessage(role="assistant", content="Rule 5 describes referee duties [C1]."),
    ]

    standalone = processor.contextualize_multi_turn("How about the exceptions?", history)
    assert "Can you explain rule 5?" in standalone
    assert "How about the exceptions?" in standalone


def test_query_processor_glossary_and_router():
    glossary = {"aturan": ["regulation", "rule"]}
    router = {"law1": ["pitch", "field"], "law2": ["ball"]}
    processor = QueryProcessor(glossary=glossary, router_rules=router)

    processed = processor.process("Bagaimana aturan tentang pitch?")
    assert "regulation" in processed.expanded_terms
    assert "rule" in processed.expanded_terms
    assert "law1" in processed.boosted_sections


def test_hybrid_retriever_bm25_and_vector(tmp_path):
    db_file = str(tmp_path / "test_knowledge.sqlite")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY,
            law_no INT,
            law_title TEXT,
            path TEXT,
            page INT,
            edition TEXT,
            source_type TEXT,
            text TEXT,
            embedding BLOB
        )
        """
    )
    cursor.execute(
        """
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            chunk_id UNINDEXED,
            law_title,
            path,
            text,
            content='chunks',
            content_rowid='rowid'
        )
        """
    )

    # Insert test chunks
    vec1 = np.ones(384, dtype=np.float32)
    vec1 /= np.linalg.norm(vec1)
    vec2 = -np.ones(384, dtype=np.float32)
    vec2 /= np.linalg.norm(vec2)

    cursor.execute(
        "INSERT INTO chunks VALUES ('c1', 1, 'Section 1', '[\"S1\"]', 1, '2024', 'original', 'Emergency evacuation procedures', ?)",
        (vec1.tobytes(),),
    )
    cursor.execute(
        "INSERT INTO chunks VALUES ('c2', 2, 'Section 2', '[\"S2\"]', 2, '2024', 'original', 'Routine daily inspection checklist', ?)",
        (vec2.tobytes(),),
    )
    cursor.execute(
        "INSERT INTO chunks_fts(rowid, chunk_id, law_title, path, text) SELECT rowid, chunk_id, law_title, path, text FROM chunks"
    )
    conn.commit()
    conn.close()

    def dummy_embed(texts):
        return np.array([vec1], dtype=np.float32)

    retriever = HybridRetriever(db_path=db_file, embedding_fn=dummy_embed)
    query_proc = QueryProcessor()
    proc_q = query_proc.process("emergency evacuation")

    evidence = retriever.retrieve(proc_q, top_k=2)
    assert len(evidence) == 2
    assert evidence[0].chunk.chunk_id == "c1"
    retriever.close()


def test_context_builder():
    builder = ContextBuilder(max_context_tokens=1000)
    chunk1 = Chunk(chunk_id="c1", text="First chunk text", path=["Section 1"])
    chunk2 = Chunk(chunk_id="c2", text="Second chunk text", path=["Section 2"])
    evidence = [
        RetrievedEvidence(chunk=chunk1, score=0.9),
        RetrievedEvidence(chunk=chunk2, score=0.8),
    ]

    built = builder.build(
        evidence_list=evidence,
        system_prompt_template="Answer based on context.",
        history=[],
        query="test query",
    )

    assert "[C1]" in built.formatted_context_text
    assert "[C2]" in built.formatted_context_text
    assert "[C1]" in built.citation_map
    assert built.citation_map["[C1]"].chunk_id == "c1"


def test_guardrails_abstain_and_citations():
    guardrails = Guardrails(min_retrieval_score=0.1)

    # Abstain on low score
    low_evidence = [
        RetrievedEvidence(chunk=Chunk(chunk_id="c1", text="Some irrelevant text"), score=0.001)
    ]
    assert guardrails.should_abstain_on_retrieval(low_evidence) is True

    # Citations extraction
    citation_map = {
        "[C1]": Chunk(chunk_id="c1", law_title="Safety", text="Safety rules", path=["Safety"])
    }
    raw_text = "According to standard procedure [C1], helmets are required."
    clean, citations = guardrails.extract_citations(raw_text, citation_map)
    assert len(citations) == 1
    assert citations[0].marker == "[C1]"
    assert citations[0].chunk_id == "c1"
