"""Guideline Gateway - Core Domain-Agnostic RAG Engine.

This package contains the domain-agnostic components for querying, retrieval,
context building, generation, and guardrails.
"""

from engine.context import ContextBuilder
from engine.guardrails import Guardrails
from engine.models import Chunk, Citation, QueryRequest, QueryResponse, RetrievedEvidence
from engine.pipeline import RuntimePipeline
from engine.query import QueryProcessor
from engine.retriever import HybridRetriever

__all__ = [
    "Chunk",
    "Citation",
    "ContextBuilder",
    "Guardrails",
    "HybridRetriever",
    "QueryProcessor",
    "QueryRequest",
    "QueryResponse",
    "RetrievedEvidence",
    "RuntimePipeline",
]
