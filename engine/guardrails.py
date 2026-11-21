"""Guardrails: citation validation, abstain logic, and fallback enforcement."""

import re
from typing import Dict, List, Set, Tuple

from engine.models import Chunk, Citation, QueryResponse, RetrievedEvidence


class Guardrails:
    """Enforces citation integrity, abstain rules, and fallback responses."""

    def __init__(
        self,
        min_retrieval_score: float = 0.01,
        abstain_message_en: str = "Not enough basis found in the document.",
        abstain_message_id: str = "Dasar aturan tidak ditemukan dalam dokumen panduan.",
    ):
        """Initialize guardrails.

        Args:
            min_retrieval_score: Score threshold below which the system must abstain.
            abstain_message_en: Standard abstain response in English.
            abstain_message_id: Standard abstain response in Indonesian.
        """
        self.min_retrieval_score = min_retrieval_score
        self.abstain_message_en = abstain_message_en
        self.abstain_message_id = abstain_message_id

    def extract_citations(
        self,
        text: str,
        citation_map: Dict[str, Chunk],
    ) -> Tuple[str, List[Citation]]:
        """Extract and validate [C#] citation markers from generated text."""
        marker_pattern = re.compile(r"\[C(\d+)\]")
        matches = marker_pattern.findall(text)

        valid_citations: List[Citation] = []
        seen_markers: Set[str] = set()

        for num_str in matches:
            marker = f"[C{num_str}]"
            if marker in seen_markers:
                continue

            if marker in citation_map:
                seen_markers.add(marker)
                chunk = citation_map[marker]
                valid_citations.append(
                    Citation(
                        marker=marker,
                        chunk_id=chunk.chunk_id,
                        law_title=chunk.law_title,
                        path=chunk.path,
                        page=chunk.page,
                        text_snippet=chunk.text[:200] + "..."
                        if len(chunk.text) > 200
                        else chunk.text,
                        confidence=1.0,
                    )
                )

        # Check for hallucinations where the model references non-existent markers
        def replace_hallucinated(match: re.Match) -> str:
            m = match.group(0)
            if m not in citation_map:
                return ""  # Strip hallucinated citation
            return m

        cleaned_text = marker_pattern.sub(replace_hallucinated, text)
        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

        return cleaned_text, valid_citations

    def should_abstain_on_retrieval(self, evidence_list: List[RetrievedEvidence]) -> bool:
        """Determine if retrieval scores are too weak to support a grounded answer."""
        if not evidence_list:
            return True
        top_score = max(ev.score for ev in evidence_list)
        return top_score < self.min_retrieval_score

    def detect_model_abstain(self, answer_text: str) -> bool:
        """Check if model response indicates insufficient information."""
        abstain_phrases = [
            "not enough basis",
            "not enough information",
            "tidak cukup dasar",
            "tidak ditemukan",
            "tidak ada informasi",
            "di luar cakupan",
            "outside the scope",
        ]
        lower = answer_text.lower()
        return any(phrase in lower for phrase in abstain_phrases)

    def create_abstain_response(
        self,
        lang: str,
        evidence_list: List[RetrievedEvidence],
        reason: str = "insufficient_evidence",
    ) -> QueryResponse:
        """Create standardized abstain response accompanied by nearest relevant clauses."""
        msg = self.abstain_message_id if lang == "id" else self.abstain_message_en
        retrieved_chunks = [ev.chunk for ev in evidence_list[:3]]

        return QueryResponse(
            answer=msg,
            citations=[],
            retrieved_chunks=retrieved_chunks,
            status="abstained",
            abstain_reason=reason,
        )

    def create_fallback_response(
        self,
        lang: str,
        evidence_list: List[RetrievedEvidence],
    ) -> QueryResponse:
        """Provide a search-only fallback when SLM generation is unavailable."""
        if lang == "id":
            prefix = (
                "Mesin model lokal sedang tidak aktif. Berikut pasal/klausul yang paling relevan:"
            )
        else:
            prefix = "Local SLM engine is not active. Here are the most relevant clauses retrieved:"

        retrieved_chunks = [ev.chunk for ev in evidence_list[:5]]
        body_lines = [prefix, ""]

        citations: List[Citation] = []
        for idx, chunk in enumerate(retrieved_chunks, start=1):
            marker = f"[C{idx}]"
            title = chunk.law_title or "Klausul"
            path = " > ".join(chunk.path) if chunk.path else ""
            header = f"{marker} {title}" + (f" ({path})" if path else "")
            body_lines.append(f"### {header}\n{chunk.text}\n")
            citations.append(
                Citation(
                    marker=marker,
                    chunk_id=chunk.chunk_id,
                    law_title=chunk.law_title,
                    path=chunk.path,
                    page=chunk.page,
                    text_snippet=chunk.text[:200],
                    confidence=1.0,
                )
            )

        return QueryResponse(
            answer="\n".join(body_lines),
            citations=citations,
            retrieved_chunks=retrieved_chunks,
            status="fallback",
        )
