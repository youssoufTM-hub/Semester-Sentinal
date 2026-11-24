"""Loads provider settings from parser_config.json. Env vars override the file.

Lookup order: $PARSER_CONFIG, parser/parser_config.json, backend/parser_config.json
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PARSER_DIR = Path(__file__).resolve().parent
SEARCH_PATHS = (PARSER_DIR / "parser_config.json", PARSER_DIR.parent / "parser_config.json")

KEY_ENV_VARS = {
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "openai": ("OPENAI_API_KEY",),
}
PROVIDER_ALIASES = {"google": "gemini", "openrouter": "openai",
                    "groq": "openai", "ollama": "openai"}


class ConfigError(Exception):
    pass


@dataclass
class ProviderSettings:
    api_key: Optional[str] = None
    model: Optional[str] = None
    fallback_models: Optional[list[str]] = None
    base_url: Optional[str] = None


@dataclass
class ParserConfig:
    provider: str = "gemini"
    providers: dict[str, ProviderSettings] = field(default_factory=dict)
    source: Optional[Path] = None

    def settings(self, name: Optional[str] = None) -> ProviderSettings:
        return self.providers.get(normalize(name or self.provider), ProviderSettings())


def normalize(name: str) -> str:
    name = (name or "").strip().lower()
    return PROVIDER_ALIASES.get(name, name)


def find_config_file() -> Optional[Path]:
    env = os.environ.get("PARSER_CONFIG")
    if env:
        path = Path(env)
        if not path.is_file():
            raise ConfigError(f"PARSER_CONFIG points to {path}, which does not exist.")
        return path
    return next((p for p in SEARCH_PATHS if p.is_file()), None)


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def load_config(path: Optional[Path] = None) -> ParserConfig:
    path = path or find_config_file()
    raw: dict = {}
    if path is not None:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            raise ConfigError(f"{path} is not valid JSON (line {err.lineno}): {err.msg}") from err
        if not isinstance(raw, dict):
            raise ConfigError(f"{path} must contain a JSON object.")

    config = ParserConfig(provider=normalize(raw.get("provider") or "gemini"), source=path)
    for name, block in (raw.get("providers") or {}).items():
        if name.startswith("_"):
            continue
        if not isinstance(block, dict):
            raise ConfigError(f'"providers.{name}" in {path} must be an object.')
        fallbacks = block.get("fallback_models")
        config.providers[normalize(name)] = ProviderSettings(
            api_key=_blank_to_none(block.get("api_key")),
            model=_blank_to_none(block.get("model")),
            fallback_models=[m for m in fallbacks if m] if isinstance(fallbacks, list) else None,
            base_url=_blank_to_none(block.get("base_url")),
        )

    _apply_env_overrides(config)
    return config


def _apply_env_overrides(config: ParserConfig) -> None:
    if os.environ.get("PARSER_PROVIDER"):
        config.provider = normalize(os.environ["PARSER_PROVIDER"])
    for name, env_vars in KEY_ENV_VARS.items():
        key = next((os.environ[v] for v in env_vars if os.environ.get(v)), None)
        if key:
            config.providers.setdefault(name, ProviderSettings()).api_key = key
    active = config.providers.setdefault(config.provider, ProviderSettings())
    if os.environ.get("PARSER_MODEL"):
        active.model = os.environ["PARSER_MODEL"]
    if os.environ.get("PARSER_FALLBACK_MODELS"):
        active.fallback_models = [m.strip() for m in os.environ["PARSER_FALLBACK_MODELS"].split(",") if m.strip()]
    if os.environ.get("OPENAI_BASE_URL"):
        config.providers.setdefault("openai", ProviderSettings()).base_url = os.environ["OPENAI_BASE_URL"]
