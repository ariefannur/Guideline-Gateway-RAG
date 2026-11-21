"""Domain chunking profiles for Guideline Gateway."""

from typing import Dict, Type

from profiles.base import BaseProfile, ProfileChunk
from profiles.hierarchical_clause import HierarchicalClauseProfile
from profiles.procedural_steps import ProceduralStepsProfile
from profiles.qa_pair import QAPairProfile
from profiles.section_table import SectionTableProfile

PROFILES: Dict[str, Type[BaseProfile]] = {
    HierarchicalClauseProfile.name: HierarchicalClauseProfile,
    ProceduralStepsProfile.name: ProceduralStepsProfile,
    SectionTableProfile.name: SectionTableProfile,
    QAPairProfile.name: QAPairProfile,
}


def get_profile(name: str) -> BaseProfile:
    """Retrieve an instantiated profile by name."""
    profile_cls = PROFILES.get(name)
    if not profile_cls:
        raise ValueError(f"Unknown profile: {name}. Available: {list(PROFILES.keys())}")
    return profile_cls()


__all__ = [
    "BaseProfile",
    "HierarchicalClauseProfile",
    "PROFILES",
    "ProceduralStepsProfile",
    "ProfileChunk",
    "QAPairProfile",
    "SectionTableProfile",
    "get_profile",
]
