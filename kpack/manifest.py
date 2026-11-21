"""Manifest and Configuration schema for Knowledge Packs (.kpack)."""

import hashlib
import json
import os
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


class Manifest(BaseModel):
    """Manifest for a packaged .kpack archive."""

    id: str
    name: str
    version: str
    edition: str
    created_at: str
    schema_version: str = "1.0"
    domain: str
    profile: str
    embedding_model: str = "multilingual-e5-small"
    embedding_dim: int = 384
    generator_target: str = "qwen2.5-1.5b-instruct-q4_k_m"
    sha256: Optional[str] = None
    chunk_count: int = 0


class PackConfig(BaseModel):
    """Domain configuration specified in pack.yaml."""

    domain: str
    profile: str = "hierarchical-clause"
    edition: str = "2024/25"
    description: str = ""
    languages: List[str] = Field(default_factory=lambda: ["en", "id"])
    min_retrieval_score: float = 0.01
    top_k: int = 5
    token_budget: int = 2500
    answer_format: str = "decision_basis_notes"
    scope_description: str = ""


def load_pack_config(pack_dir: str) -> PackConfig:
    """Load and parse pack.yaml from a pack directory."""
    pack_yaml_path = os.path.join(pack_dir, "pack.yaml")
    if not os.path.exists(pack_yaml_path):
        raise FileNotFoundError(f"Missing pack.yaml in {pack_dir}")

    with open(pack_yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PackConfig(**data)


def load_manifest(pack_dir: str) -> Manifest:
    """Load manifest.json from a pack directory."""
    manifest_path = os.path.join(pack_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Missing manifest.json in {pack_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Manifest(**data)


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()
