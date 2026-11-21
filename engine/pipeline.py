"""End-to-end Runtime Pipeline for Guideline Gateway."""

import time

from engine.context import ContextBuilder
from engine.generator import Generator
from engine.guardrails import Guardrails
from engine.models import LatencyBreakdown, QueryRequest, QueryResponse
from engine.query import QueryProcessor
from engine.retriever import HybridRetriever


class RuntimePipeline:
    """Domain-agnostic orchestrator tying query processing, retrieval, context, generation, and guardrails."""

    def __init__(
        self,
        query_processor: QueryProcessor,
        retriever: HybridRetriever,
        context_builder: ContextBuilder,
        generator: Generator,
        guardrails: Guardrails,
        system_prompt: str,
    ):
        self.query_processor = query_processor
        self.retriever = retriever
        self.context_builder = context_builder
        self.generator = generator
        self.guardrails = guardrails
        self.system_prompt = system_prompt

    def run(self, request: QueryRequest) -> QueryResponse:
        """Execute the full offline RAG pipeline."""
        start_total = time.perf_counter()
        latencies = LatencyBreakdown()

        # Stage 1: Query Processing
        t0 = time.perf_counter()
        processed_q = self.query_processor.process(
            query=request.query,
            history=request.history,
            forced_lang=request.language,
        )
        latencies.query_processing_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Stage 2: Hybrid Retrieval
        t0 = time.perf_counter()
        evidence_list = self.retriever.retrieve(
            processed_query=processed_q,
            top_k=request.top_k,
        )
        latencies.retrieval_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Early Guardrail: Check retrieval score abstain threshold
        if self.guardrails.should_abstain_on_retrieval(evidence_list):
            latencies.total_ms = round((time.perf_counter() - start_total) * 1000, 2)
            resp = self.guardrails.create_abstain_response(
                lang=processed_q.detected_lang,
                evidence_list=evidence_list,
                reason="low_retrieval_score",
            )
            resp.latencies = latencies
            resp.session_id = request.session_id
            return resp

        # Stage 3: Context Building
        t0 = time.perf_counter()
        built_ctx = self.context_builder.build(
            evidence_list=evidence_list,
            system_prompt_template=self.system_prompt,
            history=request.history,
            query=processed_q.standalone_query,
        )
        latencies.context_building_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Stage 4: Generation or Fallback
        t0 = time.perf_counter()
        if not self.generator.is_available:
            latencies.generation_ms = 0.0
            resp = self.guardrails.create_fallback_response(
                lang=processed_q.detected_lang,
                evidence_list=evidence_list,
            )
            latencies.total_ms = round((time.perf_counter() - start_total) * 1000, 2)
            resp.latencies = latencies
            resp.session_id = request.session_id
            return resp

        try:
            raw_answer = self.generator.generate(
                system_prompt=built_ctx.system_prompt,
                context_text=built_ctx.formatted_context_text,
                user_query=processed_q.standalone_query,
                history_text=built_ctx.history_text,
            )
        except Exception:
            # Generation error -> fallback to search results
            resp = self.guardrails.create_fallback_response(
                lang=processed_q.detected_lang,
                evidence_list=evidence_list,
            )
            latencies.total_ms = round((time.perf_counter() - start_total) * 1000, 2)
            resp.latencies = latencies
            resp.session_id = request.session_id
            return resp

        latencies.generation_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Stage 5: Guardrails (Citation validation & abstain check)
        t0 = time.perf_counter()
        if self.guardrails.detect_model_abstain(raw_answer):
            resp = self.guardrails.create_abstain_response(
                lang=processed_q.detected_lang,
                evidence_list=evidence_list,
                reason="model_abstained",
            )
            latencies.guardrails_ms = round((time.perf_counter() - t0) * 1000, 2)
            latencies.total_ms = round((time.perf_counter() - start_total) * 1000, 2)
            resp.latencies = latencies
            resp.session_id = request.session_id
            return resp

        clean_answer, valid_citations = self.guardrails.extract_citations(
            text=raw_answer,
            citation_map=built_ctx.citation_map,
        )
        latencies.guardrails_ms = round((time.perf_counter() - t0) * 1000, 2)
        latencies.total_ms = round((time.perf_counter() - start_total) * 1000, 2)

        return QueryResponse(
            answer=clean_answer,
            citations=valid_citations,
            retrieved_chunks=[ev.chunk for ev in evidence_list],
            status="answered",
            latencies=latencies,
            session_id=request.session_id,
        )
