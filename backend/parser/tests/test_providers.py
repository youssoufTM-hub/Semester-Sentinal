import io
import json
from types import SimpleNamespace

import pytest

from parser.documents import DOCX, DocumentError, load_document
from parser.eval.__main__ import score
from parser.models import ParseResult, parse_result_json_schema
from parser.providers import ProviderError, get_provider
from parser.providers.claude import ClaudeProvider
from parser.providers.gemini import GeminiProvider
from parser.providers.openai_compat import OpenAICompatProvider

PDF = b"%PDF-1.7 fake"


# --- documents --------------------------------------------------------------

def test_docx_text_keeps_tables_in_document_order():
    docx = pytest.importorskip("docx")
    d = docx.Document()
    d.add_paragraph("Evaluation")
    table = d.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Midterm 1", "Oct 5, 2026"
    table.cell(1, 0).text, table.cell(1, 1).text = "Midterm 2", "Nov 16, 2026"
    d.add_paragraph("Policies")
    buf = io.BytesIO()
    d.save(buf)

    doc = load_document(buf.getvalue(), "CSCI.docx")
    assert doc.mime_type == DOCX
    assert doc.text.index("Evaluation") < doc.text.index("Midterm 1 | Oct 5, 2026") < doc.text.index("Policies")


@pytest.mark.parametrize("data,name", [(b"", "a.pdf"), (b"nope", "a.pdf"), (b"x", "a.png")])
def test_bad_documents(data, name):
    with pytest.raises(DocumentError):
        load_document(data, name)


# --- provider selection -------------------------------------------------------

def test_unknown_provider():
    with pytest.raises(ProviderError):
        get_provider("skynet")


def test_env_selects_provider(monkeypatch, tmp_path):
    pytest.importorskip("google.genai")
    cfg = tmp_path / "ai_config.json"
    cfg.write_text("{}")
    monkeypatch.setenv("AI_CONFIG", str(cfg))
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("AI_MODEL", "gemini-test")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    p = get_provider()
    assert p.name == "gemini" and p.model == "gemini-test"


# --- each provider builds the right request -------------------------------------

def test_gemini_request(sample_result_json):
    pytest.importorskip("google.genai")
    sent = {}

    def generate_content(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(candidates=[SimpleNamespace(finish_reason="STOP")], text=json.dumps(sample_result_json))

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    p = GeminiProvider(model="gemini-x", client=client)
    out = p.generate_json(load_document(PDF, "a.pdf"), "SYS", "PROMPT", parse_result_json_schema())
    assert json.loads(out)["course"]["code"] == "CSCI 2010U"
    assert sent["model"] == "gemini-x"
    assert sent["contents"][0].inline_data.mime_type == "application/pdf"
    assert sent["config"].response_mime_type == "application/json"
    assert sent["config"].system_instruction == "SYS"


def test_gemini_max_tokens_is_an_error():
    pytest.importorskip("google.genai")
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **k: SimpleNamespace(
        candidates=[SimpleNamespace(finish_reason="FinishReason.MAX_TOKENS")], text="{")))
    with pytest.raises(ProviderError, match="too long"):
        GeminiProvider(client=client).generate_json(load_document(PDF, "a.pdf"), "s", "p", {})


def test_openai_compat_sends_text_to_other_servers(sample_result_json):
    pytest.importorskip("openai")
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        msg = SimpleNamespace(content=json.dumps(sample_result_json), refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=msg)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    p = OpenAICompatProvider(model="llama", client=client, base_url="http://localhost:11434/v1")
    doc = load_document(b"Course outline text", "a.txt")
    p.generate_json(doc, "SYS", "PROMPT", {"type": "object"})
    user = sent["messages"][1]["content"]
    assert user[0]["type"] == "text" and "Course outline text" in user[0]["text"]
    assert sent["response_format"]["json_schema"]["strict"] is True


def test_claude_request(sample_result_json):
    pytest.importorskip("anthropic")
    sent = {}
    message = SimpleNamespace(stop_reason="end_turn",
                              content=[SimpleNamespace(type="text", text=json.dumps(sample_result_json))])

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return message

    def stream(**kwargs):
        sent.update(kwargs)
        return Stream()

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    ClaudeProvider(client=client).generate_json(load_document(PDF, "a.pdf"), "SYS", "P", {"type": "object"})
    assert sent["model"] == "claude-opus-5-5"
    assert sent["messages"][0]["content"][0]["source"]["media_type"] == "application/pdf"
    assert sent["output_config"]["format"]["type"] == "json_schema"


# --- eval scoring ------------------------------------------------------------------

def test_eval_scoring(sample_result_json):
    result = ParseResult.model_validate(sample_result_json)
    spec = {"items": [
        {"title": "Midterm", "kind": ["exam"], "due_date": "2027-02-24", "match": "mid.?term"},
        {"title": "Project", "kind": ["assignment"], "due_date": "2027-04-03", "match": "project"},
        {"title": "Final", "kind": ["exam"], "due_date": None, "match": "final"},
        {"title": "Quiz 1", "kind": ["quiz"], "due_date": "2027-01-20", "match": "quiz"},
    ]}
    s = score(result, spec)
    assert (s.expected, s.found, s.date_ok, s.kind_ok, s.extra_rows) == (4, 3, 2, 2, 1)
