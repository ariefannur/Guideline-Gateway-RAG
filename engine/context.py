"""Context Builder with token budgeting and citation marker formatting."""

from typing import Dict, List

from engine.models import ChatMessage, Chunk, RetrievedEvidence


class BuiltContext:
    """Represents the assembled prompt context and citation mapping."""

    def __init__(
        self,
        formatted_context_text: str,
        citation_map: Dict[str, Chunk],
        system_prompt: str,
        history_text: str,
        estimated_tokens: int,
    ):
        self.formatted_context_text = formatted_context_text
        self.citation_map = citation_map  # e.g., "[C1]" -> Chunk
        self.system_prompt = system_prompt
        self.history_text = history_text
        self.estimated_tokens = estimated_tokens


class ContextBuilder:
    """Domain-agnostic context builder with strict token budgeting."""

    def __init__(
        self,
        max_context_tokens: int = 2500,
        chars_per_token: float = 3.8,
    ):
        """Initialize context builder.

        Args:
            max_context_tokens: Total token ceiling for evidence chunks.
            chars_per_token: Heuristic ratio for token estimation without heavy tokenizer.
        """
        self.max_context_tokens = max_context_tokens
        self.chars_per_token = chars_per_token

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count based on character length."""
        return max(1, int(len(text) / self.chars_per_token))

    def format_history(self, history: List[ChatMessage], max_turns: int = 3) -> str:
        """Format recent multi-turn conversation history into a sliding window."""
        if not history:
            return ""

        recent = history[-max_turns * 2 :]
        lines = []
        for msg in recent:
            prefix = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{prefix}: {msg.content}")

        return "\n".join(lines)

    def build(
        self,
        evidence_list: List[RetrievedEvidence],
        system_prompt_template: str,
        history: List[ChatMessage],
        query: str,
    ) -> BuiltContext:
        """Assemble prompt context, evidence blocks with [C#] markers, and citation mapping."""
        citation_map: Dict[str, Chunk] = {}
        context_blocks: List[str] = []
        consumed_tokens = 0

        for idx, evidence in enumerate(evidence_list, start=1):
            chunk = evidence.chunk
            marker = f"[C{idx}]"
            citation_map[marker] = chunk

            # Header with breadcrumbs and metadata
            path_str = " > ".join(chunk.path) if chunk.path else ""
            header_parts = []
            if chunk.law_title:
                header_parts.append(chunk.law_title)
            if path_str:
                header_parts.append(path_str)
            breadcrumb = " > ".join(header_parts) if header_parts else "Guideline Excerpt"

            page_info = f", page {chunk.page}" if chunk.page else ""
            block_header = f"{marker} ({breadcrumb}{page_info})"
            block_content = f"{block_header}\n{chunk.text.strip()}\n"

            block_tokens = self.estimate_tokens(block_content)
            if consumed_tokens + block_tokens > self.max_context_tokens and context_blocks:
                # Stop adding chunks once budget is filled
                break

            context_blocks.append(block_content)
            consumed_tokens += block_tokens

        formatted_context = "\n".join(context_blocks)
        history_text = self.format_history(history)
        total_estimated = (
            self.estimate_tokens(system_prompt_template)
            + self.estimate_tokens(history_text)
            + consumed_tokens
            + self.estimate_tokens(query)
        )

        return BuiltContext(
            formatted_context_text=formatted_context,
            citation_map=citation_map,
            system_prompt=system_prompt_template,
            history_text=history_text,
            estimated_tokens=total_estimated,
        )
