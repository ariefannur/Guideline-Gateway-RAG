#!/usr/bin/env python3
"""Ingest the football‑laws pack sources into the pack's knowledge.sqlite.

The pack already contains a SQLite DB with the correct schema (created by
PackManager).  This script reads the sources listed in ``packs/football-laws-2024-2025/pack.yaml``
(`laws.md` and the original PDF), chunks the text using the same
`ContextBuilder` logic that the runtime uses, generates embeddings with the
provided ``PackEmbedder`` and bulk‑inserts the chunks into ``knowledge.sqlite``.

Running this script after any source change ensures that the pack's DB is
populated, so ``guideline ask`` can retrieve answers (e.g. number of
substitutes).
"""

import json
import os
import pathlib
import sqlite3
from typing import List

from kpack.embedder import PackEmbedder
from engine.context import ContextBuilder
from engine.models import Chunk
import yaml

# ---------------------------------------------------------------------------
# Configuration (paths are relative to the repository root)
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PACK_ROOT = REPO_ROOT / "packs" / "football-laws-2024-2025"
DB_PATH = PACK_ROOT / "knowledge.sqlite"

def load_pack_yaml() -> dict:
    """Load the pack.yaml file which lists the source files and parsers."""
    yaml_path = PACK_ROOT / "pack.yaml"
    return yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

def gather_sources() -> List[tuple[pathlib.Path, str]]:
    """Return a list of (source_path, parser_name) tuples.

    The pack.yaml ``sources`` section contains entries like:
        - file: sources/laws.md
          parser: markdown
          chunking: hierarchical-clause
    Only the ``file`` and ``parser`` fields are needed here.
    """
    manifest = load_pack_yaml()
    sources = []
    for src in manifest.get("sources", []):
        src_path = PACK_ROOT / src["file"]
        parser = src.get("parser", "markdown")
        sources.append((src_path, parser))
    return sources

def chunk_source(file_path: pathlib.Path, parser: str) -> List[Chunk]:
    """Chunk a single source file using the same ContextBuilder settings.

    For simplicity we only handle the markdown file; the PDF is already
    converted to ``laws.md`` by the build script.  If the PDF is needed, the
    same logic can be added later.
    """
    # Read raw text – the markdown file already contains the extracted text.
    raw_text = file_path.read_text(encoding="utf-8")

    # Build a minimal document dict that ContextBuilder expects.  The fields
    # mirror what the official pack parser would produce.
    doc = {
        "law_no": None,
        "law_title": None,
        "path": str(file_path.relative_to(PACK_ROOT)),
        "page": None,
        "edition": "2024/25",
        "source_type": parser,
        "text": raw_text,
    }

    # ContextBuilder creates hierarchical chunks (the same profile used by the
    # pack).  ``build_context`` expects a list of document dicts and returns a
    # list with a ``chunks`` key.
    ctx = ContextBuilder(max_context_tokens=2500)
    built = ctx.build_context([doc])
    # ``built`` is a list with a single element (our doc) containing a
    # ``chunks`` list of dicts.
    chunk_dicts = built[0]["chunks"]
    chunks: List[Chunk] = []
    for cd in chunk_dicts:
        chunks.append(
            Chunk(
                chunk_id=cd["chunk_id"],
                law_no=cd.get("law_no"),
                law_title=cd.get("law_title"),
                path=cd.get("path"),
                page=cd.get("page"),
                edition=cd.get("edition"),
                source_type=cd.get("source_type"),
                text=cd["text"],
                embedding=None,  # will be filled after embedding step
            )
        )
    return chunks

def main() -> None:
    # ---------------------------------------------------------------------
    # 1. Load sources and produce chunks (without embeddings yet)
    # ---------------------------------------------------------------------
    all_chunks: List[Chunk] = []
    for src_path, parser in gather_sources():
        if not src_path.is_file():
            print(f"[WARNING] Source file missing: {src_path}")
            continue
        all_chunks.extend(chunk_source(src_path, parser))
    print(f"✅ Generated {len(all_chunks)} chunks from sources.")

    if not all_chunks:
        print("[ERROR] No chunks to ingest – aborting.")
        return

    # ---------------------------------------------------------------------
    # 2. Compute embeddings in one batch using PackEmbedder
    # ---------------------------------------------------------------------
    embedder = PackEmbedder()
    texts = [c.text for c in all_chunks]
    embeddings = embedder.embed(texts)  # returns a list of numpy arrays
    for chunk, emb in zip(all_chunks, embeddings):
        chunk.embedding = emb.tobytes()

    # ---------------------------------------------------------------------
    # 3. Insert into SQLite (create tables if they are missing)
    # ---------------------------------------------------------------------
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            law_no INT,
            law_title TEXT,
            path TEXT,
            page INT,
            edition TEXT,
            source_type TEXT,
            text TEXT,
            embedding BLOB
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_id UNINDEXED,
            law_title,
            path,
            text,
            content='chunks',
            content_rowid='rowid'
        );
        """
    )

    insert_sql = """
        INSERT OR REPLACE INTO chunks
        (chunk_id, law_no, law_title, path, page, edition, source_type, text, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    rows = []
    for c in all_chunks:
        rows.append(
            (
                c.chunk_id,
                c.law_no,
                c.law_title,
                json.dumps(c.path) if isinstance(c.path, (list, dict)) else c.path,
                c.page,
                c.edition,
                c.source_type,
                c.text,
                c.embedding,
            )
        )
    cur.executemany(insert_sql, rows)
    conn.commit()
    conn.close()
    print(f"✅ Ingested {len(rows)} chunks into {DB_PATH}")

if __name__ == "__main__":
    main()
