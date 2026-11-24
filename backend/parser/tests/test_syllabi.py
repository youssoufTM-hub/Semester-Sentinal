"""Runs the parser on every syllabus in parser/inputs/.

Drop your own .pdf / .docx / .txt in that folder and run:

    cd backend
    pytest parser/tests -s

-s prints the deadlines found for each file. Term dates come from
inputs/term.json. The parsing tests call the API, so they need a key in
parser/parser_config.json (or GEMINI_API_KEY); without one they fail with
NoAPIKeyError.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from parser import NoAPIKeyError, ParseResult, SyllabusInput, SyllabusParser, TermContext, load_document
from parser.eval.__main__ import EXPECTED_DIR, score
from parser.providers import get_provider

INPUTS = Path(__file__).resolve().parents[1] / "inputs"
SYLLABI = sorted(p for p in INPUTS.iterdir() if p.suffix.lower() in (".pdf", ".docx", ".txt"))
TERM_FILE = INPUTS / "term.json"
TERM = TermContext.model_validate_json(TERM_FILE.read_text()) if TERM_FILE.exists() else None

_results: dict[str, tuple[ParseResult, str]] = {}


@pytest.fixture(scope="session")
def parser():
    return SyllabusParser(get_provider())


@pytest.fixture
def parsed(parser, request):
    path = request.param
    if path.name not in _results:
        result = parser.parse(SyllabusInput(path.read_bytes(), filename=path.name), TERM)
        model = getattr(parser.provider, "last_model", parser.provider.model)
        _results[path.name] = (result, model)
    return (path, *_results[path.name])


def show(name: str, result: ParseResult, model: str) -> None:
    print(f"\n{name} ({model}): {result.course.code} {result.course.name or ''}")
    for d in result.deadlines:
        flag = "  (check)" if d.needs_review else ""
        print(f"  {d.due_date or 'no date':<10}  {d.kind:<10}  {d.weight_pct if d.weight_pct is not None else '-':>5}%  {d.title}{flag}")
    for w in result.warnings:
        print(f"  ! {w}")


def test_no_api_key_raises(tmp_path, monkeypatch):
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "PARSER_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    empty = tmp_path / "parser_config.json"
    empty.write_text('{"provider": "gemini", "providers": {"gemini": {"api_key": ""}}}')
    monkeypatch.setenv("PARSER_CONFIG", str(empty))
    monkeypatch.setattr("parser.providers._load_dotenv", lambda: None)
    with pytest.raises(NoAPIKeyError, match="No API key configured"):
        get_provider()


def test_inputs_folder_has_a_syllabus():
    assert SYLLABI, f"put at least one syllabus in {INPUTS}"


@pytest.mark.parametrize("path", SYLLABI, ids=lambda p: p.name)
def test_file_can_be_read(path):
    doc = load_document(path.read_bytes(), path.name)
    if doc.is_pdf and not doc.text:
        pytest.skip("scanned pdf, no text layer (still works with gemini)")
    assert len(doc.text) > 200


@pytest.mark.parametrize("parsed", SYLLABI, ids=lambda p: p.name, indirect=True)
def test_syllabus_parses(parsed):
    path, result, model = parsed
    show(path.name, result, model)

    assert result.course.code or result.course.name
    assert result.deadlines, "no graded items found"
    assert any(d.kind == "exam" for d in result.deadlines), "no exams found"

    for d in result.deadlines:
        if d.due_date:
            due = date.fromisoformat(d.due_date)
            if TERM and TERM.start and TERM.end:
                assert date.fromisoformat(TERM.start) <= due <= date.fromisoformat(TERM.end), d.title
        if d.weight_pct is not None:
            assert 0 <= d.weight_pct <= 100, d.title

    if result.grading_scheme:
        total = sum(c.weight_pct for c in result.grading_scheme)
        assert 95 <= total <= 105, f"grading scheme adds up to {total}%"


@pytest.mark.parametrize("parsed", SYLLABI, ids=lambda p: p.name, indirect=True)
def test_matches_expected_answers(parsed):
    path, result, model = parsed
    specs = [json.loads(p.read_text(encoding="utf-8")) for p in EXPECTED_DIR.glob("*.json")]
    spec = next((s for s in specs if s["file_contains"].lower() in path.name.lower()), None)
    if spec is None:
        pytest.skip("no answer file in eval/expected for this syllabus")

    s = score(result, spec)
    assert not s.misses, f"answered by {model}: {s.misses}"
