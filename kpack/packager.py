"""Packaging and unpacking utilities for .kpack Knowledge Pack files."""

import hashlib
import json
import os
import zipfile
from typing import Dict


class Packager:
    """Creates and extracts .kpack self-contained zip archives with integrity verification."""

    REQUIRED_FILES = [
        "manifest.json",
        "pack.yaml",
        "knowledge.sqlite",
        "prompts/system.md",
        "SOURCES.md",
    ]

    @staticmethod
    def validate_pack_dir(pack_dir: str) -> bool:
        """Verify that a pack directory contains all mandatory files."""
        for rel_path in Packager.REQUIRED_FILES:
            full_path = os.path.join(pack_dir, rel_path)
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"Missing required file in pack: {rel_path}")
        return True

    @staticmethod
    def build_kpack(pack_dir: str, output_path: str) -> str:
        """Package a pack directory into a .kpack zip archive."""
        Packager.validate_pack_dir(pack_dir)

        # Ensure directory of output exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(pack_dir):
                for file in files:
                    if file.endswith(".kpack") or file == ".DS_Store":
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, pack_dir)
                    zipf.write(file_path, arcname)

        # Compute hash of the resulting .kpack
        hasher = hashlib.sha256()
        with open(output_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        pack_hash = hasher.hexdigest()

        return pack_hash

    @staticmethod
    def extract_kpack(kpack_path: str, target_dir: str) -> Dict[str, str]:
        """Extract a .kpack archive to a target directory and verify manifest."""
        if not os.path.exists(kpack_path):
            raise FileNotFoundError(f".kpack file not found: {kpack_path}")

        os.makedirs(target_dir, exist_ok=True)
        with zipfile.ZipFile(kpack_path, "r") as zipf:
            zipf.extractall(target_dir)

        Packager.validate_pack_dir(target_dir)

        manifest_path = os.path.join(target_dir, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        return manifest
