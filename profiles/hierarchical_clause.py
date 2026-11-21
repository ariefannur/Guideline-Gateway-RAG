"""Hierarchical Clause profile for regulations, laws, and articles."""

import re
from typing import List, Optional

from profiles.base import BaseProfile, ProfileChunk


class HierarchicalClauseProfile(BaseProfile):
    """Chunking profile for hierarchical regulations (e.g. Law > Section > Clause)."""

    name: str = "hierarchical-clause"
    description: str = "Splits hierarchical documents by Law, Section, and numbered clauses."

    def chunk(self, markdown_text: str, edition: Optional[str] = None) -> List[ProfileChunk]:
        """Split markdown containing # Law and ## Section headers into clause-level chunks."""
        chunks: List[ProfileChunk] = []

        lines = markdown_text.splitlines()
        current_law_no: Optional[int] = None
        current_law_title: Optional[str] = None
        current_section: Optional[str] = None
        current_path: List[str] = []

        current_clause_lines: List[str] = []
        clause_index = 1

        def flush_clause():
            nonlocal current_clause_lines, clause_index
            if not current_clause_lines:
                return

            text_body = "\n".join(current_clause_lines).strip()
            if not text_body:
                current_clause_lines = []
                return

            cid_law = f"law{current_law_no}" if current_law_no is not None else "sec"
            cid = f"{cid_law}-{clause_index}"

            # Format contextual header: [Law X — Title > Section > Subclause]
            path_parts = []
            if current_law_title:
                path_parts.append(current_law_title)
            if current_section:
                path_parts.append(current_section)
            for p in current_path:
                if p not in path_parts:
                    path_parts.append(p)

            breadcrumb = " > ".join(path_parts) if path_parts else "Guideline Clause"
            enriched_text = f"[{breadcrumb}]\n{text_body}"

            chunks.append(
                ProfileChunk(
                    chunk_id=cid,
                    title=current_law_title,
                    section_no=current_law_no,
                    path=path_parts,
                    text=enriched_text,
                    metadata={"edition": edition or "standard", "clause_index": clause_index},
                )
            )
            clause_index += 1
            current_clause_lines = []

        for line in lines:
            line_str = line.strip()

            # Level 1 Heading: e.g. # Law 11 — Offside or # Pasal 1
            h1_match = re.match(r"^#\s+(.+)$", line_str)
            if h1_match:
                flush_clause()
                heading = h1_match.group(1).strip()
                current_law_title = heading

                # Try to extract number
                num_match = re.search(r"\b(\d+)\b", heading)
                current_law_no = int(num_match.group(1)) if num_match else None
                current_section = None
                current_path = []
                clause_index = 1
                continue

            # Level 2 Heading: e.g. ## 1. Offside position
            h2_match = re.match(r"^##\s+(.+)$", line_str)
            if h2_match:
                flush_clause()
                current_section = h2_match.group(1).strip()
                current_path = []
                continue

            # Level 3 Heading: e.g. ### 1.1 Offside offence
            h3_match = re.match(r"^###\s+(.+)$", line_str)
            if h3_match:
                flush_clause()
                sub = h3_match.group(1).strip()
                current_path = [sub]
                continue

            # Numbered or bullet clause break if text is long enough
            if re.match(r"^(\d+\.|\*|-)\s+", line_str) and len(current_clause_lines) >= 8:
                flush_clause()

            current_clause_lines.append(line)

        flush_clause()
        return chunks
