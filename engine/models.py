"""Domain-agnostic data models for Guideline Gateway engine."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single turn in conversational history."""

    role: Literal["user", "assistant", "system"]
    content: str


class Chunk(BaseModel):
    """A granular unit of indexed guideline document text."""

    chunk_id: str
    law_no: Optional[int] = None
    law_title: Optional[str] = None
    path: List[str] = Field(default_factory=list)
    page: Optional[int] = None
    edition: Optional[str] = None
    source_type: str = "original"
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievedEvidence(BaseModel):
    """A chunk retrieved via BM25, Vector, or RRF hybrid search."""

    chunk: Chunk
    score: float
    retrieval_method: Literal["bm25", "vector", "rrf"] = "rrf"


class Citation(BaseModel):
    """Citation linking a generated claim back to a source chunk."""

    marker: str  # e.g., "[C1]"
    chunk_id: str
    law_title: Optional[str] = None
    path: List[str] = Field(default_factory=list)
    page: Optional[int] = None
    text_snippet: Optional[str] = None
    confidence: float = 1.0


class QueryRequest(BaseModel):
    """User query request payload."""

    query: str
    history: List[ChatMessage] = Field(default_factory=list)
    session_id: Optional[str] = None
    top_k: int = 5
    stream: bool = False
    language: Optional[str] = None  # "id", "en", or None for auto-detect


class LatencyBreakdown(BaseModel):
    """Latency metrics per pipeline stage in milliseconds."""

    query_processing_ms: float = 0.0
    retrieval_ms: float = 0.0
    context_building_ms: float = 0.0
    generation_ms: float = 0.0
    guardrails_ms: float = 0.0
    total_ms: float = 0.0


class QueryResponse(BaseModel):
    """Generated response payload with verifiable citations."""

    answer: str
    citations: List[Citation] = Field(default_factory=list)
    retrieved_chunks: List[Chunk] = Field(default_factory=list)
    status: Literal["answered", "abstained", "fallback"] = "answered"
    abstain_reason: Optional[str] = None
    latencies: LatencyBreakdown = Field(default_factory=LatencyBreakdown)
    session_id: Optional[str] = None
