"""SQLite index builder with chunks table and FTS5 full-text search."""

import json
import os
import sqlite3
from typing import List, Optional

import numpy as np

from profiles.base import ProfileChunk


class SQLiteIndexBuilder:
    """Creates knowledge.sqlite with metadata, text, raw embedding BLOBs, and FTS5 index."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        if os.path.exists(db_path):
            os.remove(db_path)

        self.conn = sqlite3.connect(self.db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        """Execute SQLite schema definitions."""
        cursor = self.conn.cursor()
        cursor.execute(
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
            )
            """
        )

        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                chunk_id UNINDEXED,
                law_title,
                path,
                text,
                content='chunks',
                content_rowid='rowid'
            )
            """
        )
        self.conn.commit()

    def insert_chunks(
        self, chunks: List[ProfileChunk], embeddings: Optional[np.ndarray] = None
    ) -> None:
        """Insert processed chunks and their float32 embedding BLOBs into database."""
        cursor = self.conn.cursor()

        for idx, chunk in enumerate(chunks):
            blob = None
            if embeddings is not None and idx < len(embeddings):
                # Ensure float32 byte buffer
                vec = embeddings[idx].astype(np.float32)
                blob = vec.tobytes()

            path_json = json.dumps(chunk.path)
            edition = chunk.metadata.get("edition", "standard")
            page = chunk.page

            cursor.execute(
                """
                INSERT INTO chunks (chunk_id, law_no, law_title, path, page, edition, source_type, text, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    chunk.section_no,
                    chunk.title,
                    path_json,
                    page,
                    edition,
                    "original",
                    chunk.text,
                    blob,
                ),
            )

        # Populate FTS5 virtual table from chunks table
        cursor.execute(
            """
            INSERT INTO chunks_fts(rowid, chunk_id, law_title, path, text)
            SELECT rowid, chunk_id, law_title, path, text FROM chunks
            """
        )
        self.conn.commit()

    def close(self) -> None:
        """Close SQLite database connection."""
        self.conn.close()
