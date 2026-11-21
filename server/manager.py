"""Knowledge Pack Manager for server runtime."""

import json
import os
import shutil
from typing import Any, Dict, Optional

import yaml
import sqlite3

from engine.context import ContextBuilder
from engine.generator import Generator
from engine.guardrails import Guardrails
from engine.pipeline import RuntimePipeline
from engine.query import QueryProcessor
from engine.retriever import HybridRetriever
from kpack.embedder import PackEmbedder
from kpack.packager import Packager


class PackManager:
    """Manages loaded Knowledge Packs, switching, and pipeline instantiations."""

    def __init__(self, packs_dir: str = "packs", active_pack_id: Optional[str] = None):
        self.packs_dir = packs_dir
        self.active_pack_id: Optional[str] = None
        self.previous_pack_id: Optional[str] = None
        self.pipeline: Optional[RuntimePipeline] = None
        self.active_manifest: Dict[str, Any] = {}
        self.active_config: Dict[str, Any] = {}
        self.installed_packs: Dict[str, Dict[str, Any]] = {}

        self.discover_packs()
        if active_pack_id and active_pack_id in self.installed_packs:
            self.activate_pack(active_pack_id)
        elif self.installed_packs:
            first_id = next(iter(self.installed_packs))
            self.activate_pack(first_id)

    def discover_packs(self) -> Dict[str, Dict[str, Any]]:
        """Scan packs directory for valid pack folders."""
        self.installed_packs = {}
        if not os.path.exists(self.packs_dir):
            os.makedirs(self.packs_dir, exist_ok=True)
            return self.installed_packs

        for entry in os.listdir(self.packs_dir):
            if entry.startswith(".") or entry == "_template":
                continue
            entry_path = os.path.join(self.packs_dir, entry)
            if os.path.isdir(entry_path):
                manifest_path = os.path.join(entry_path, "manifest.json")
                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            manifest = json.load(f)
                            pack_id = manifest.get("id", entry)
                            self.installed_packs[pack_id] = {
                                "id": pack_id,
                                "name": manifest.get("name", entry),
                                "version": manifest.get("version", "1.0.0"),
                                "edition": manifest.get("edition", "standard"),
                                "domain": manifest.get("domain", entry),
                                "path": entry_path,
                                "status": "active"
                                if pack_id == self.active_pack_id
                                else "installed",
                            }
                    except Exception:
                        continue
        return self.installed_packs

    def activate_pack(self, pack_id: str) -> bool:
        """Activate and load the specified knowledge pack into memory."""
        self.discover_packs()
        resolved_id = pack_id
        if resolved_id not in self.installed_packs:
            # Fallback search by folder basename or domain
            for pid, info in self.installed_packs.items():
                if os.path.basename(info["path"]) == pack_id or info.get("domain") == pack_id:
                    resolved_id = pid
                    break

        if resolved_id not in self.installed_packs:
            raise KeyError(f"Knowledge pack '{pack_id}' is not installed.")

        pack_info = self.installed_packs[resolved_id]
        pack_path = pack_info["path"]

        # Load manifest
        manifest_path = os.path.join(pack_path, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            self.active_manifest = json.load(f)

        # Load pack.yaml
        config_path = os.path.join(pack_path, "pack.yaml")
        pack_config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                pack_config = yaml.safe_load(f) or {}
        self.active_config = pack_config

        # Load glossary
        glossary_path = os.path.join(pack_path, "glossary.yaml")
        glossary = {}
        if os.path.exists(glossary_path):
            with open(glossary_path, "r", encoding="utf-8") as f:
                glossary = yaml.safe_load(f) or {}

        # Load router rules
        router_path = os.path.join(pack_path, "router.yaml")
        router_rules = {}
        if os.path.exists(router_path):
            with open(router_path, "r", encoding="utf-8") as f:
                router_rules = yaml.safe_load(f) or {}

        # Load system prompt
        system_prompt_path = os.path.join(pack_path, "prompts", "system.md")
        system_prompt = (
            "You are a helpful assistant answering strictly from the provided context. "
            "Always include citations [C#]."
        )
        if os.path.exists(system_prompt_path):
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read().strip()

        # Build pipeline components
        db_path = os.path.join(pack_path, "knowledge.sqlite")
        embedder = PackEmbedder()
        embedding_fn = embedder.embed if os.path.exists(embedder.model_path or "") else None

        # Clean up old retriever if exists
        if self.pipeline and hasattr(self.pipeline, "retriever") and self.pipeline.retriever:
            try:
                self.pipeline.retriever.close()
            except Exception:
                pass

        # Ensure SQLite database exists and schema is initialized
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        init_conn = sqlite3.connect(db_path)
        init_cursor = init_conn.cursor()
        init_cursor.executescript("""
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
        """)
        init_conn.commit()
        init_conn.close()

        # Instantiate retriever with the now‑guaranteed database file
        retriever = HybridRetriever(
            db_path=db_path,
            embedding_fn=embedding_fn,
        )
        # Ensure the required SQLite schema exists (chunks table and FTS virtual table)
        if hasattr(retriever, "_conn") and retriever._conn:
            cursor = retriever._conn.cursor()
            # Check for the chunks table; if missing, create it and the FTS virtual table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'")
            if not cursor.fetchone():
                cursor.executescript("""
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
                """)
                retriever._conn.commit()

        query_proc = QueryProcessor(
            glossary=glossary,
            router_rules=router_rules,
        )

        ctx_builder = ContextBuilder(
            max_context_tokens=self.active_config.get("token_budget", 2500),
        )

        generator = Generator(
            model_path=os.getenv("SLM_MODEL_PATH"),
            n_ctx=int(os.getenv("N_CTX", "2048")),
            n_threads=int(os.getenv("NUM_THREADS", "4")),
        )

        guardrails = Guardrails(
            min_retrieval_score=float(self.active_config.get("min_retrieval_score", 0.01)),
        )

        self.pipeline = RuntimePipeline(
            query_processor=query_proc,
            retriever=retriever,
            context_builder=ctx_builder,
            generator=generator,
            guardrails=guardrails,
            system_prompt=system_prompt,
        )

        if self.active_pack_id and self.active_pack_id != pack_id:
            self.previous_pack_id = self.active_pack_id

        self.active_pack_id = pack_id
        for pid in self.installed_packs:
            self.installed_packs[pid]["status"] = "active" if pid == pack_id else "installed"

        return True

    def rollback_pack(self) -> str:
        """Roll back to previously active knowledge pack."""
        if not self.previous_pack_id:
            raise ValueError("No previous pack available for rollback.")
        target_id = self.previous_pack_id
        self.activate_pack(target_id)
        return target_id

    def install_kpack(self, kpack_file_path: str) -> str:
        """Extract and install a .kpack archive file."""
        if not os.path.exists(kpack_file_path):
            raise FileNotFoundError(f"File not found: {kpack_file_path}")

        temp_extract = os.path.join(self.packs_dir, "_temp_install")
        if os.path.exists(temp_extract):
            shutil.rmtree(temp_extract)

        manifest = Packager.extract_kpack(kpack_file_path, temp_extract)
        pack_id = manifest.get("id", os.path.splitext(os.path.basename(kpack_file_path))[0])
        destination_dir = os.path.join(self.packs_dir, pack_id)

        if os.path.exists(destination_dir):
            shutil.rmtree(destination_dir)

        shutil.move(temp_extract, destination_dir)
        self.discover_packs()
        return pack_id
