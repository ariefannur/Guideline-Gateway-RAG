"""Base profile definition and chunk data structures."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ParsedSection(BaseModel):
    """A structured heading or section extracted from intermediate markdown."""

    title: str
    level: int
    content: str = ""
    subsections: List["ParsedSection"] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProfileChunk(BaseModel):
    """Raw chunk produced by a domain profile chunker."""

    chunk_id: str
    title: Optional[str] = None
    section_no: Optional[int] = None
    path: List[str] = Field(default_factory=list)
    page: Optional[int] = None
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseProfile(ABC):
    """Abstract base class for domain chunking and formatting profiles."""

    name: str = "base"
    description: str = ""

    @abstractmethod
    def chunk(self, markdown_text: str, edition: Optional[str] = None) -> List[ProfileChunk]:
        """Split clean intermediate markdown into semantic, structure-aware chunks."""
        pass
