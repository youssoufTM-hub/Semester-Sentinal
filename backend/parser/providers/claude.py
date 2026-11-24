"""Anthropic Claude via the `anthropic` SDK. Reads ANTHROPIC_API_KEY."""
from __future__ import annotations

import base64
from typing import Optional

from ..documents import Document
from .base import ProviderError, document_as_text

DEFAULT_MODEL = "claude-opus-5-5"


class ClaudeProvider:
    name = "claude"

    def __init__(
        self,
        model: Optional[str] = None,
        client=None,
        api_key: Optional[str] = None,
        effort: str = "high",
        use_fallbacks: bool = True,
    ):
        self.model = model or DEFAULT_MODEL
        self.effort = effort
        self.use_fallbacks = use_fallbacks
        if client is None:
            try:
                import anthropic
            except ImportError as err:
                raise ProviderError("Install anthropic to use the Claude provider.") from err
            client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.client = client

    def generate_json(self, document: Document, system: str, prompt: str, schema: dict) -> str:
        if document.is_pdf:
            doc_block = {
                "type": "document",
                "title": document.filename,
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(document.data).decode("ascii"),
                },
            }
        else:
            doc_block = {
                "type": "document",
                "title": document.filename,
                "source": {"type": "text", "media_type": "text/plain", "data": document_as_text(document)},
            }

        request = dict(
            model=self.model,
            max_tokens=64000,
            system=system,
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": [doc_block, {"type": "text", "text": prompt}]}],
        )
        if self.use_fallbacks:
            # On a policy decline the API retries on a fallback model in the same call.
            request["betas"] = ["server-side-fallback-2026-07-01"]
            request["fallbacks"] = "default"

        import anthropic

        try:
            with self.client.beta.messages.stream(**request) as stream:
                message = stream.get_final_message()
        except anthropic.BadRequestError as err:
            raise ProviderError(f"Claude rejected the request: {err.message}") from err
        except anthropic.AuthenticationError as err:
            raise ProviderError("Claude rejected the API key.") from err
        except anthropic.RateLimitError as err:
            raise ProviderError("Claude is busy. Try again in a minute.", retryable=True) from err
        except anthropic.APIStatusError as err:
            raise ProviderError(f"Claude error ({err.status_code}). Try again.", retryable=err.status_code >= 500) from err
        except anthropic.APIConnectionError as err:
            raise ProviderError("Could not reach Claude.", retryable=True) from err

        if message.stop_reason == "refusal":
            raise ProviderError("Claude declined to read this document.")
        if message.stop_reason == "max_tokens":
            raise ProviderError("The syllabus was too long to finish parsing in one pass.")
        text = next((b.text for b in message.content if b.type == "text"), None)
        if not text:
            raise ProviderError("Claude returned no result.")
        return text
