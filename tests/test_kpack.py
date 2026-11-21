"""Unit tests for kpack tooling and packager."""

import json
import os

import numpy as np

from kpack.chunker import PackChunker
from kpack.indexer import SQLiteIndexBuilder
from kpack.packager import Packager
from kpack.parser import DocumentParser
from profiles.base import ProfileChunk


def test_document_parser_denoising():
    parser = DocumentParser()
    raw = "Here is a \ufb01rst test with   extra   spaces\r\nand a new line."
    clean = parser.denoise_text(raw)
    assert "first" in clean
    assert "extra spaces" in clean
    assert "\r" not in clean


def test_pack_chunker_delegation():
    chunker = PackChunker(profile_name="hierarchical-clause")
    sample = "# Law 1 - Field\n## 1. Surface\nSurface must be green."
    chunks = chunker.process_text(sample, edition="2024")
    assert len(chunks) >= 1
    assert chunks[0].section_no == 1


def test_packager_build_and_extract(tmp_path):
    pack_dir = tmp_path / "sample_pack"
    pack_dir.mkdir()
    (pack_dir / "prompts").mkdir()

    (pack_dir / "manifest.json").write_text(
        json.dumps({"id": "sample-1", "name": "Sample"}), encoding="utf-8"
    )
    (pack_dir / "pack.yaml").write_text(
        "domain: sample\nprofile: hierarchical-clause", encoding="utf-8"
    )
    (pack_dir / "knowledge.sqlite").write_text("dummy sqlite", encoding="utf-8")
    (pack_dir / "prompts" / "system.md").write_text("You are assistant.", encoding="utf-8")
    (pack_dir / "SOURCES.md").write_text("# Sources", encoding="utf-8")

    out_kpack = str(tmp_path / "sample.kpack")
    pack_hash = Packager.build_kpack(str(pack_dir), out_kpack)
    assert os.path.exists(out_kpack)
    assert len(pack_hash) == 64

    extract_dir = str(tmp_path / "extracted")
    manifest = Packager.extract_kpack(out_kpack, extract_dir)
    assert manifest["id"] == "sample-1"
    assert os.path.exists(os.path.join(extract_dir, "pack.yaml"))


def test_sqlite_indexer(tmp_path):
    db_file = str(tmp_path / "test.sqlite")
    builder = SQLiteIndexBuilder(db_file)

    chunk = ProfileChunk(
        chunk_id="test-1",
        title="Title 1",
        section_no=1,
        path=["P1"],
        text="Sample indexed text",
    )
    vec = np.zeros(384, dtype=np.float32)
    builder.insert_chunks([chunk], np.array([vec]))
    builder.close()

    assert os.path.exists(db_file)
