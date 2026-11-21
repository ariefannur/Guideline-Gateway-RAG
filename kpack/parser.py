"""Two-stage document parser: PDF/Raw text extraction to intermediate structured Markdown."""

import os
import re


class DocumentParser:
    """Extracts text from source documents and converts them to clean structured Markdown."""

    def __init__(self, margin_top: float = 40.0, margin_bottom: float = 40.0):
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom

    def denoise_text(self, text: str) -> str:
        """Apply denoising rules to remove PDF artifacts, excess spaces, and strange ligatures."""
        # Normalize whitespace
        cleaned = re.sub(r"\r\n", "\n", text)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)

        # Remove common PDF ligatures
        ligatures = {
            "\ufb01": "fi",
            "\ufb02": "fl",
            "\ufb00": "ff",
            "\ufb03": "ffi",
            "\ufb04": "ffl",
        }
        for lig, repl in ligatures.items():
            cleaned = cleaned.replace(lig, repl)

        # Normalize multiple newlines
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def parse_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF using PyMuPDF with header/footer bounding-box filtering."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError(
                "PyMuPDF (fitz) is required for PDF parsing. Install with `uv pip install pymupdf`."
            )

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(pdf_path)
        markdown_blocks = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            rect = page.rect
            # Skip top and bottom margins to eliminate running headers/footers
            clip_rect = fitz.Rect(0, self.margin_top, rect.width, rect.height - self.margin_bottom)
            text = page.get_text("text", clip=clip_rect)

            cleaned_page = self.denoise_text(text)
            if cleaned_page:
                markdown_blocks.append(f"<!-- Page {page_num + 1} -->\n{cleaned_page}")

        return "\n\n".join(markdown_blocks)

    def parse_markdown_or_text(self, file_path: str) -> str:
        """Read and normalize an existing markdown or text document."""
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()
        return self.denoise_text(raw)
