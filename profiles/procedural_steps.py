"""Procedural Steps profile for SOPs, runbooks, and troubleshooting procedures."""

import re
from typing import List, Optional

from profiles.base import BaseProfile, ProfileChunk


class ProceduralStepsProfile(BaseProfile):
    """Chunking profile for SOPs and procedural workflows."""

    name: str = "procedural-steps"
    description: str = "Preserves step sequence, prerequisites, and warnings for SOP procedures."

    def chunk(self, markdown_text: str, edition: Optional[str] = None) -> List[ProfileChunk]:
        """Split procedures into coherent step groups."""
        chunks: List[ProfileChunk] = []
        sections = re.split(r"\n(?=##\s+)", markdown_text)

        for idx, sec in enumerate(sections, start=1):
            sec_text = sec.strip()
            if not sec_text:
                continue

            lines = sec_text.splitlines()
            title = lines[0].replace("#", "").strip() if lines else f"Procedure {idx}"
            cid = f"sop-{idx}"

            chunks.append(
                ProfileChunk(
                    chunk_id=cid,
                    title=title,
                    path=[title],
                    text=f"[{title}]\n{sec_text}",
                    metadata={"profile": "procedural-steps", "edition": edition or "standard"},
                )
            )

        return chunks
