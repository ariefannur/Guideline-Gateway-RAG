"""QA Pair profile for FAQ documents and knowledge bases."""

import re
from typing import List, Optional

from profiles.base import BaseProfile, ProfileChunk


class QAPairProfile(BaseProfile):
    """Chunking profile for Question & Answer pairs."""

    name: str = "qa-pair"
    description: str = "Splits Q&A documents so each question and its answer form a single chunk."

    def chunk(self, markdown_text: str, edition: Optional[str] = None) -> List[ProfileChunk]:
        chunks: List[ProfileChunk] = []
        pairs = re.split(
            r"\n(?=###?\s+(?:Q|Tanya|Pertanyaan):)", markdown_text, flags=re.IGNORECASE
        )

        for idx, pair in enumerate(pairs, start=1):
            pair_text = pair.strip()
            if not pair_text:
                continue

            lines = pair_text.splitlines()
            question_title = lines[0].replace("#", "").strip() if lines else f"FAQ {idx}"
            cid = f"faq-{idx}"

            chunks.append(
                ProfileChunk(
                    chunk_id=cid,
                    title=question_title,
                    path=["FAQ", question_title],
                    text=pair_text,
                    metadata={"profile": "qa-pair", "edition": edition or "standard"},
                )
            )

        return chunks
