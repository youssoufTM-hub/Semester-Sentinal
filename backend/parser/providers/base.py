from __future__ import annotations

from typing import Protocol

from ..documents import Document


class ProviderError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class Provider(Protocol):
    name: str
    model: str

    def generate_json(self, document: Document, system: str, prompt: str, schema: dict) -> str:
        ...


def document_as_text(document: Document) -> str:
    if not document.text.strip():
        raise ProviderError(
            f"No text could be read from {document.filename}. "
            "It may be a scanned PDF; use a provider that reads PDFs directly (gemini or openai)."
        )
    return f"<syllabus filename=\"{document.filename}\">\n{document.text}\n</syllabus>"
