from __future__ import annotations

from typing import Optional, Sequence

from ..documents import Document
from .base import ProviderError, document_as_text

DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_FALLBACKS = ("gemini-3.5-flash-lite",)


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        model: Optional[str] = None,
        client=None,
        api_key: Optional[str] = None,
        fallback_models: Optional[Sequence[str]] = None,
        timeout_seconds: float = 180,
    ):
        self.model = model or DEFAULT_MODEL
        if fallback_models is None:
            fallback_models = DEFAULT_FALLBACKS
        self.fallback_models = [m for m in fallback_models if m != self.model]
        self.last_model = self.model
        if client is None:
            try:
                from google import genai
            except ImportError as err:
                raise ProviderError("Install google-genai to use the Gemini provider.") from err
            from google.genai import types

            http = types.HttpOptions(timeout=int(timeout_seconds * 1000))
            client = genai.Client(api_key=api_key, http_options=http) if api_key else genai.Client(http_options=http)
        self.client = client

    def generate_json(self, document: Document, system: str, prompt: str, schema: dict) -> str:
        models = [self.model, *self.fallback_models]
        for model in models[:-1]:
            try:
                return self._generate(model, document, system, prompt, schema)
            except ProviderError as err:
                if not err.retryable:
                    raise
        return self._generate(models[-1], document, system, prompt, schema)

    def _generate(self, model: str, document: Document, system: str, prompt: str, schema: dict) -> str:
        from google.genai import errors, types

        if document.is_pdf:
            doc_part = types.Part.from_bytes(data=document.data, mime_type=document.mime_type)
        else:
            doc_part = types.Part.from_text(text=document_as_text(document))

        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema,
            max_output_tokens=65536,
        )
        try:
            response = self.client.models.generate_content(
                model=model,
                contents=[doc_part, prompt],
                config=config,
            )
        except errors.ClientError as err:
            if err.code == 429:
                raise ProviderError("Gemini is rate limiting this key. Try again in a minute.", retryable=True) from err
            if err.code in (401, 403):
                raise ProviderError("Gemini rejected the API key.") from err
            raise ProviderError(f"Gemini rejected the request ({err.code}): {err.message}") from err
        except errors.ServerError as err:
            raise ProviderError(f"Gemini server error ({err.code}). Try again.", retryable=True) from err
        except errors.APIError as err:
            raise ProviderError(f"Gemini error: {err}") from err

        candidate = (response.candidates or [None])[0]
        finish = str(getattr(candidate, "finish_reason", "") or "")
        if "MAX_TOKENS" in finish:
            raise ProviderError("The syllabus was too long to finish parsing in one pass.")
        if any(word in finish for word in ("SAFETY", "PROHIBITED", "BLOCKLIST", "RECITATION")):
            raise ProviderError("Gemini declined to read this document.")
        text = response.text
        if not text:
            raise ProviderError("Gemini returned no result.")
        self.last_model = model
        return text
