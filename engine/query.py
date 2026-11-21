"""Query processing pipeline: normalization, lang detection, glossary expansion, and routing."""

import re
from typing import Dict, List, Optional, Set

from engine.models import ChatMessage


class ProcessedQuery:
    """Represents the preprocessed and expanded query ready for retrieval."""

    def __init__(
        self,
        raw_query: str,
        normalized_query: str,
        standalone_query: str,
        detected_lang: str,
        expanded_terms: List[str],
        boosted_sections: Dict[str, float],
    ):
        self.raw_query = raw_query
        self.normalized_query = normalized_query
        self.standalone_query = standalone_query
        self.detected_lang = detected_lang
        self.expanded_terms = expanded_terms
        self.boosted_sections = boosted_sections

    @property
    def full_search_text(self) -> str:
        """Combined text of standalone query and expanded terminology."""
        if not self.expanded_terms:
            return self.standalone_query
        return f"{self.standalone_query} {' '.join(self.expanded_terms)}"


class QueryProcessor:
    """Domain-agnostic query processor configured via domain configuration."""

    def __init__(
        self,
        glossary: Optional[Dict[str, List[str]]] = None,
        router_rules: Optional[Dict[str, List[str]]] = None,
    ):
        """Initialize query processor.

        Args:
            glossary: Mapping of terms (e.g. ID to EN terms) for terminology expansion.
            router_rules: Mapping of section/law identifiers to matching keyword lists.
        """
        self.glossary = glossary or {}
        self.router_rules = router_rules or {}

    def normalize(self, text: str) -> str:
        """Clean and normalize raw query text."""
        cleaned = re.sub(r"[^\w\s\?\-]", " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
        return cleaned

    def detect_language(self, text: str) -> str:
        """Lightweight heuristic language detector for ID and EN."""
        normalized = text.lower()
        id_tokens = {
            "apakah",
            "bagaimana",
            "jika",
            "pada",
            "oleh",
            "dari",
            "yang",
            "dan",
            "atau",
            "tidak",
            "bisa",
            "ini",
            "itu",
            "ke",
            "di",
            "adalah",
            "tentang",
            "harus",
            "kapan",
        }
        en_tokens = {
            "what",
            "how",
            "if",
            "when",
            "by",
            "from",
            "which",
            "and",
            "or",
            "not",
            "can",
            "this",
            "that",
            "to",
            "in",
            "is",
            "about",
            "must",
            "should",
        }

        words = set(re.findall(r"\b\w+\b", normalized))
        id_overlap = len(words & id_tokens)
        en_overlap = len(words & en_tokens)

        if id_overlap > en_overlap:
            return "id"
        elif en_overlap > id_overlap:
            return "en"
        return "en"  # Default fallback

    def contextualize_multi_turn(self, query: str, history: List[ChatMessage]) -> str:
        """Combine previous turns for context-dependent follow-up questions."""
        if not history:
            return query

        follow_up_cues = {
            "bagaimana jika",
            "lalu",
            "kalau",
            "bagaimana dengan",
            "what if",
            "then",
            "how about",
            "what about",
            "kenapa",
        }
        lower_q = query.lower()
        is_follow_up = any(lower_q.startswith(cue) or cue in lower_q for cue in follow_up_cues)

        if is_follow_up and len(history) >= 2:
            # Get last user turn and last assistant turn snippet
            last_user = next((msg.content for msg in reversed(history) if msg.role == "user"), None)
            if last_user:
                return f"{last_user} — {query}"
        return query

    def expand_glossary(self, text: str) -> List[str]:
        """Find matching terms from glossary and return expansion synonyms."""
        expansions: Set[str] = set()
        lower_text = text.lower()

        for source_term, target_terms in self.glossary.items():
            if re.search(rf"\b{re.escape(source_term.lower())}\b", lower_text):
                expansions.update(target_terms)

        return sorted(list(expansions))

    def compute_router_boosts(self, text: str) -> Dict[str, float]:
        """Compute candidate section boost weights from router keywords."""
        boosts: Dict[str, float] = {}
        lower_text = text.lower()

        for section_id, keywords in self.router_rules.items():
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw.lower())}\b", lower_text):
                    boosts[section_id] = boosts.get(section_id, 0.0) + 1.0

        # Normalize boost scores
        if boosts:
            max_val = max(boosts.values())
            boosts = {k: v / max_val for k, v in boosts.items()}

        return boosts

    def process(
        self,
        query: str,
        history: Optional[List[ChatMessage]] = None,
        forced_lang: Optional[str] = None,
    ) -> ProcessedQuery:
        """Run full query processing pipeline."""
        history = history or []
        normalized_raw = self.normalize(query)
        standalone = self.contextualize_multi_turn(query, history)
        normalized_standalone = self.normalize(standalone)

        lang = forced_lang or self.detect_language(standalone)
        expanded_terms = self.expand_glossary(normalized_standalone)
        router_boosts = self.compute_router_boosts(normalized_standalone)

        return ProcessedQuery(
            raw_query=query,
            normalized_query=normalized_raw,
            standalone_query=standalone,
            detected_lang=lang,
            expanded_terms=expanded_terms,
            boosted_sections=router_boosts,
        )
