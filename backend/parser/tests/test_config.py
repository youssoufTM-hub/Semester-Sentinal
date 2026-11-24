import json

import pytest

from parser.config import ConfigError, load_config
from parser.providers import ProviderError, get_provider

ENV_VARS = ["AI_CONFIG", "AI_PROVIDER", "AI_MODEL", "AI_FALLBACK_MODELS", "GEMINI_API_KEY",
            "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL"]


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    path = tmp_path / "ai_config.json"
    monkeypatch.setenv("AI_CONFIG", str(path))

    def write(data):
        path.write_text(json.dumps(data) if not isinstance(data, str) else data)
        return path
    return write


def test_example_file_loads(monkeypatch):
    from parser.config import PARSER_DIR
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    cfg = load_config(PARSER_DIR / "ai_config.example.json")
    assert cfg.provider == "gemini"
    assert cfg.settings().model == "gemini-3.5-flash"
    assert cfg.settings().api_key is None  # blank strings count as "not set"
    assert cfg.settings("openai").base_url is None


def test_file_picks_provider_key_and_model(config_file):
    pytest.importorskip("google.genai")
    config_file({"provider": "gemini", "providers": {"gemini": {"api_key": "k-123", "model": "gemini-x",
                                                                 "fallback_models": ["gemini-y"]}}})
    p = get_provider()
    assert (p.name, p.model, p.fallback_models) == ("gemini", "gemini-x", ["gemini-y"])


def test_env_overrides_file(config_file, monkeypatch):
    config_file({"provider": "gemini", "providers": {"gemini": {"api_key": "from-file"}}})
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    monkeypatch.setenv("AI_MODEL", "gemini-env")
    s = load_config().settings()
    assert (s.api_key, s.model) == ("from-env", "gemini-env")


def test_cli_args_override_file(config_file):
    pytest.importorskip("anthropic")
    config_file({"provider": "gemini", "providers": {"claude": {"api_key": "c-key"}}})
    p = get_provider("claude", "claude-sonnet-5-5")
    assert (p.name, p.model) == ("claude", "claude-sonnet-5-5")


def test_missing_key_says_where_to_put_it(config_file):
    config_file({"provider": "gemini", "providers": {"gemini": {"api_key": ""}}})
    with pytest.raises(ProviderError, match=r'providers\.gemini\.api_key'):
        get_provider()


def test_local_openai_server_needs_no_key(config_file):
    pytest.importorskip("openai")
    config_file({"provider": "ollama", "providers": {"openai": {"base_url": "http://localhost:11434/v1",
                                                                 "model": "llama3.3"}}})
    p = get_provider()
    assert (p.name, p.model, p.send_pdf) == ("openai", "llama3.3", False)


def test_bad_json_is_explained(config_file):
    config_file('{"provider": "gemini",}')
    with pytest.raises(ConfigError, match="not valid JSON"):
        load_config()


def test_unknown_provider_in_file(config_file):
    config_file({"provider": "skynet"})
    with pytest.raises(ProviderError, match="Unknown provider"):
        get_provider()
