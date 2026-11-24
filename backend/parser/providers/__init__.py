from __future__ import annotations

from typing import Optional

from ..config import ConfigError, load_config, normalize
from .base import Provider, ProviderError

PROVIDERS = ("gemini", "openai")


class NoAPIKeyError(ProviderError):
    pass


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def get_provider(name: Optional[str] = None, model: Optional[str] = None) -> Provider:
    _load_dotenv()
    try:
        config = load_config()
    except ConfigError as err:
        raise ProviderError(str(err)) from err

    name = normalize(name or config.provider)
    if name not in PROVIDERS:
        raise ProviderError(f"Unknown provider '{name}'. Use one of: {', '.join(PROVIDERS)}.")
    s = config.settings(name)
    model = model or s.model
    where = config.source or "parser/parser_config.json"

    if not s.api_key and not (name == "openai" and s.base_url):
        raise NoAPIKeyError(
            f'No API key configured for "{name}". Put it in "providers.{name}.api_key" in {where} '
            "(copy parser_config.example.json if the file does not exist yet), "
            "or set the GEMINI_API_KEY / OPENAI_API_KEY environment variable."
        )

    if name == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(model=model, api_key=s.api_key, fallback_models=s.fallback_models)
    from .openai_compat import OpenAICompatProvider
    return OpenAICompatProvider(model=model, api_key=s.api_key, base_url=s.base_url)


__all__ = ["NoAPIKeyError", "Provider", "ProviderError", "PROVIDERS", "get_provider"]
