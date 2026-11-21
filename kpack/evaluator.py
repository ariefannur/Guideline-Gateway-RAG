"""Automated regression evaluation harness for Knowledge Packs."""

import json
import os
from typing import Any, Dict, List

from engine.models import QueryRequest
from engine.pipeline import RuntimePipeline


class EvaluationHarness:
    """Runs evaluation benchmark over domain golden questions (golden.jsonl)."""

    def __init__(self, pipeline: RuntimePipeline, golden_path: str):
        self.pipeline = pipeline
        self.golden_path = golden_path

    def run_eval(self, top_k: int = 5) -> Dict[str, Any]:
        """Execute evaluation suite and calculate MRR, Recall@k, and Abstain accuracy."""
        if not os.path.exists(self.golden_path):
            raise FileNotFoundError(f"golden.jsonl not found: {self.golden_path}")

        records: List[Dict[str, Any]] = []
        with open(self.golden_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    records.append(json.loads(line_str))

        if not records:
            return {"total_questions": 0, "status": "empty"}

        recall_hits = 0
        reciprocal_ranks = []
        abstain_correct = 0
        abstain_total = 0
        details: List[Dict[str, Any]] = []

        for item in records:
            qid = item.get("id", f"q-{len(details) + 1}")
            query = item["q"]
            lang = item.get("lang", "en")
            gold_chunks = set(item.get("gold_chunks", []))
            must_abstain = item.get("must_abstain", False)

            req = QueryRequest(query=query, language=lang, top_k=top_k)
            resp = self.pipeline.run(req)

            if must_abstain:
                abstain_total += 1
                is_abstain = resp.status == "abstained"
                if is_abstain:
                    abstain_correct += 1
                details.append(
                    {
                        "id": qid,
                        "query": query,
                        "type": "trap",
                        "abstained": is_abstain,
                        "status": resp.status,
                    }
                )
                continue

            # Check retrieval against gold chunks
            retrieved_ids = [c.chunk_id for c in resp.retrieved_chunks]
            hit = any(cid in gold_chunks for cid in retrieved_ids)
            if hit:
                recall_hits += 1

            # Reciprocal rank
            rr = 0.0
            for rank, cid in enumerate(retrieved_ids, start=1):
                if cid in gold_chunks:
                    rr = 1.0 / rank
                    break
            reciprocal_ranks.append(rr)
            details.append(
                {
                    "id": qid,
                    "query": query,
                    "type": "factual",
                    "hit": hit,
                    "rr": rr,
                    "retrieved": retrieved_ids[:top_k],
                }
            )

        non_abstain_total = len(records) - abstain_total
        recall_at_k = (recall_hits / non_abstain_total) if non_abstain_total > 0 else 1.0
        mrr = (sum(reciprocal_ranks) / non_abstain_total) if non_abstain_total > 0 else 1.0
        abstain_acc = (abstain_correct / abstain_total) if abstain_total > 0 else 1.0

        return {
            "total_questions": len(records),
            "factual_questions": non_abstain_total,
            "trap_questions": abstain_total,
            f"recall@{top_k}": round(recall_at_k * 100, 2),
            "mrr": round(mrr, 4),
            "abstain_accuracy": round(abstain_acc * 100, 2),
            "passes_gate": (recall_at_k >= 0.85 and abstain_acc >= 0.80),
            "details": details,
        }
