"""OpenAI or any OpenAI-compatible API (OpenRouter, Groq, Ollama) via base_url."""
from __future__ import annotations

import base64
import os
from typing import Optional

from ..documents import Document
from .base import ProviderError, document_as_text

DEFAULT_MODEL = "gpt-5-mini"


class OpenAICompatProvider:
    name = "openai"

    def __init__(
        self,
        model: Optional[str] = None,
        client=None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        send_pdf: Optional[bool] = None,
    ):
        self.model = model or DEFAULT_MODEL
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        # only openai itself takes pdf files
        self.send_pdf = (not self.base_url) if send_pdf is None else send_pdf
        if client is None:
            try:
                import openai
            except ImportError as err:
                raise ProviderError("Install openai to use the OpenAI-compatible provider.") from err
            key = api_key or os.environ.get("OPENAI_API_KEY") or ("not-needed" if self.base_url else None)
            client = openai.OpenAI(base_url=self.base_url, api_key=key)
        self.client = client

    def generate_json(self, document: Document, system: str, prompt: str, schema: dict) -> str:
        if document.is_pdf and self.send_pdf:
            b64 = base64.standard_b64encode(document.data).decode("ascii")
            doc_part = {"type": "file", "file": {"filename": document.filename,
                                                 "file_data": f"data:application/pdf;base64,{b64}"}}
        else:
            doc_part = {"type": "text", "text": document_as_text(document)}

        import openai

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": [doc_part, {"type": "text", "text": prompt}]},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "syllabus_parse", "schema": schema, "strict": True},
                },
            )
        except openai.AuthenticationError as err:
            raise ProviderError("The provider rejected the API key.") from err
        except openai.RateLimitError as err:
            raise ProviderError("The provider is busy. Try again in a minute.", retryable=True) from err
        except openai.APIStatusError as err:
            raise ProviderError(f"Provider error ({err.status_code}): {err.message}",
                                retryable=err.status_code >= 500) from err
        except openai.APIConnectionError as err:
            raise ProviderError("Could not reach the provider.", retryable=True) from err

        choice = completion.choices[0]
        if choice.finish_reason == "length":
            raise ProviderError("The syllabus was too long to finish parsing in one pass.")
        if choice.finish_reason == "content_filter" or getattr(choice.message, "refusal", None):
            raise ProviderError("The provider declined to read this document.")
        if not choice.message.content:
            raise ProviderError("The provider returned no result.")
        return choice.message.content
