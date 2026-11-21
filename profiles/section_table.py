"""Section Table profile for technical manuals and tabular specifications."""

import re
from typing import List, Optional

from profiles.base import BaseProfile, ProfileChunk


class SectionTableProfile(BaseProfile):
    """Chunking profile for technical manuals with embedded markdown tables."""

    name: str = "section-table"
    description: str = "Splits technical manuals per section while preserving table headers."

    def chunk(self, markdown_text: str, edition: Optional[str] = None) -> List[ProfileChunk]:
        chunks: List[ProfileChunk] = []
        sections = re.split(r"\n(?=##\s+)", markdown_text)

        for idx, sec in enumerate(sections, start=1):
            sec_text = sec.strip()
            if not sec_text:
                continue

            lines = sec_text.splitlines()
            title = lines[0].replace("#", "").strip() if lines else f"Section {idx}"
            cid = f"table-sec-{idx}"

            chunks.append(
                ProfileChunk(
                    chunk_id=cid,
                    title=title,
                    path=[title],
                    text=f"[{title}]\n{sec_text}",
                    metadata={"profile": "section-table", "edition": edition or "standard"},
                )
            )

        return chunks
