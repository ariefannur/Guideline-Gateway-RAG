"""SLM Generator wrapper supporting llama.cpp (GGUF) and graceful local fallback."""

import os
from typing import Generator as PyGenerator
from typing import Optional


class Generator:
    """Encapsulates small language model generation using local llama.cpp GGUF weights."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        n_ctx: int = 2048,
        n_threads: int = 4,
        temperature: float = 0.1,
        max_tokens: int = 512,
    ):
        """Initialize generator.

        Args:
            model_path: Path to .gguf model file.
            n_ctx: Context window size.
            n_threads: Number of CPU threads.
            temperature: Sampling temperature (low for deterministic citations).
            max_tokens: Max new tokens to generate.
        """
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._llm = None
        self._is_available = False

        if model_path and os.path.exists(model_path):
            self._init_llm()

    def _init_llm(self) -> None:
        """Attempt to load llama.cpp model."""
        try:
            from llama_cpp import Llama

            self._llm = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                verbose=False,
            )
            self._is_available = True
        except (ImportError, Exception):
            self._llm = None
            self._is_available = False

    @property
    def is_available(self) -> bool:
        """Return True if local GGUF model is loaded and ready."""
        return self._is_available and self._llm is not None

    def generate(
        self,
        system_prompt: str,
        context_text: str,
        user_query: str,
        history_text: str = "",
    ) -> str:
        """Generate response text given prompt context."""
        if not self.is_available:
            raise RuntimeError("Local SLM runtime is not available or model weight not found.")

        prompt = (
            f"<|im_start|>system\n{system_prompt}\nHere is the context:\n{context_text}<|im_end|>\n"
        )
        if history_text:
            prompt += f"<|im_start|>user\nPrevious discussion:\n{history_text}\n"

        prompt += f"<|im_start|>user\n{user_query}<|im_end|>\n<|im_start|>assistant\n"

        output = self._llm(
            prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stop=["<|im_end|>", "User:", "\n\nUser:"],
            echo=False,
        )

        text = output["choices"][0]["text"].strip()
        return text

    def generate_stream(
        self,
        system_prompt: str,
        context_text: str,
        user_query: str,
        history_text: str = "",
    ) -> PyGenerator[str, None, None]:
        """Stream generated response token by token."""
        if not self.is_available:
            yield "Local SLM model not found. Running in search/fallback mode."
            return

        prompt = (
            f"<|im_start|>system\n{system_prompt}\nHere is the context:\n{context_text}<|im_end|>\n"
        )
        if history_text:
            prompt += f"<|im_start|>user\nPrevious discussion:\n{history_text}\n"

        prompt += f"<|im_start|>user\n{user_query}<|im_end|>\n<|im_start|>assistant\n"

        stream = self._llm(
            prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stop=["<|im_end|>", "User:", "\n\nUser:"],
            stream=True,
            echo=False,
        )

        for chunk in stream:
            delta = chunk["choices"][0]["text"]
            yield delta
