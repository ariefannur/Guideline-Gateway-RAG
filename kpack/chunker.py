"""Generic chunker delegating to selected domain profiles."""

from typing import List, Optional

from profiles import BaseProfile, ProfileChunk, get_profile


class PackChunker:
    """Structure-aware chunker wrapper applying the specified domain profile."""

    def __init__(self, profile_name: str = "hierarchical-clause"):
        self.profile: BaseProfile = get_profile(profile_name)

    def process_text(self, markdown_text: str, edition: Optional[str] = None) -> List[ProfileChunk]:
        """Split clean markdown into structured chunks."""
        return self.profile.chunk(markdown_text, edition=edition)
