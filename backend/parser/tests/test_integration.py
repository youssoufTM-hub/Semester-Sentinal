"""Checks the parser output against the other parts of the project.

No API key needed: it uses a saved parse result (tests/fixtures/sample_result.json).
Each test skips if that part of the project isn't merged into this branch yet:
  analytics -> backend/analytics/
  heatmap   -> backend/analytics/calculate_weekly_heatmap.py (or the old copy at the repo root)
  frontend  -> frontend/api.py
"""
import importlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import parser.router as parser_router
from parser import ParseResult, SyllabusParser, to_analytics_deadlines, to_event_inputs
from parser.dev_server import app

FIXTURE = Path(__file__).parent / "fixtures" / "sample_result.json"
REPO = Path(__file__).resolve().parents[3]

for extra in (REPO, REPO / "frontend"):
    if extra.is_dir() and str(extra) not in sys.path:
        sys.path.append(str(extra))


def need(module):
    try:
        return importlib.import_module(module)
    except ImportError:
        pytest.skip(f"{module} isn't in this branch yet")


class SavedProvider:
    name = "saved"
    model = "saved"

    def __init__(self):
        self.calls = 0

    def generate_json(self, document, system, prompt, schema):
        self.calls += 1
        return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def result():
    return ParseResult.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(parser_router, "_parser", SyllabusParser(SavedProvider()))
    return TestClient(app)


def post_syllabi(client, count=3):
    files = [("files", (f"course{i}.pdf", b"%PDF-1.4 test " + bytes([i]), "application/pdf")) for i in range(count)]
    data = {"course_names": json.dumps([f"C{i}" for i in range(count)]),
            "term": json.dumps({"start": "2027-01-11", "end": "2027-04-24", "term_name": "", "breaks": []})}
    return client.post("/api/parse/syllabi", files=files, data=data)


def test_api_response_shape(client):
    resp = post_syllabi(client)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"courses", "review_rows", "deadlines", "events", "analysis", "errors"}
    assert len(body["courses"]) == 3 and body["errors"] == []
    for row in body["review_rows"]:
        assert {"course", "title", "kind", "due_date", "weight_pct"} <= set(row)


def test_status_endpoint(client):
    assert client.get("/api/parse/status").json()["ready"] is True


def test_analytics(result):
    need("analytics.models")
    from analytics.collisions import find_collisions
    from analytics.ics_export import build_ics
    from parser.integration import weekly_scores

    deadlines = to_analytics_deadlines([result])
    assert len(deadlines) == 3
    assert all(isinstance(d.due, date) for d in deadlines)
    weeks = weekly_scores([result])
    mondays = {(d.due - timedelta(days=d.due.weekday())).isoformat() for d in deadlines}
    assert {w["week_start"] for w in weeks} == mondays
    find_collisions(deadlines)
    assert b"BEGIN:VCALENDAR" in build_ics(deadlines)


def test_analytics_summary(result):
    need("analytics.models")
    from parser import analyze

    summary = analyze([result])
    assert summary["weeks"] and {"week_start", "score", "level", "is_final_boss"} <= set(summary["weeks"][0])


def test_heatmap(result):
    # the heatmap now lives in analytics; the old branch had it at the repo root
    try:
        heatmap = importlib.import_module("analytics.calculate_weekly_heatmap")
    except ImportError:
        heatmap = need("calculate_weekly_heatmap")
        schemas = need("schemas")
        for e in to_event_inputs([result]):
            schemas.EventInput(**e)

    events = to_event_inputs([result])
    weeks = heatmap.calculate_weekly_heatmap(events)
    # same items in the same weeks as analytics scoring
    assert sum(w["event_count"] for w in weeks) == len(events) == 3
    midterm_week = next(w for w in weeks if w["week_start"] == "2027-02-22")
    assert midterm_week["score"] == 6.0  # exam 4 x1.5 for 25%


def test_frontend_reads_response(client):
    api = need("api")
    if not hasattr(api, "row_to_deadline"):
        pytest.skip("frontend api.py has no row_to_deadline")

    body = post_syllabi(client).json()
    rows = [api.row_to_deadline(r) for r in body["review_rows"]]
    assert all(set(r) == {"course", "title", "kind", "due", "weight"} for r in rows)
    logic = need("logic")
    assert logic.weekly_scores(rows)


def test_course_names_from_frontend_are_used(client):
    body = post_syllabi(client).json()
    assert {r["course"] for r in body["review_rows"]} == {"C0", "C1", "C2"}
    assert {d["course"] for d in body["deadlines"]} == {"C0", "C1", "C2"}


def test_same_file_is_not_parsed_twice():
    provider = SavedProvider()
    p = SyllabusParser(provider)
    from parser import SyllabusInput
    for _ in range(3):
        p.parse(SyllabusInput(b"%PDF-1.4 same file", filename="a.pdf"))
    assert provider.calls == 1


def test_duplicate_rows_are_dropped(result):
    from parser import check_result
    result.deadlines.append(result.deadlines[1].model_copy())
    assert len(check_result(result).deadlines) == 4


def test_analysis_in_response(client):
    need("analytics.models")
    analysis = post_syllabi(client).json()["analysis"]
    assert {"weeks", "collisions", "suggested_starts"} <= set(analysis)
    assert all("estimated_hours" in w for w in analysis["weeks"])


def test_suggested_starts_match_frontend_keys(result):
    from parser import suggested_starts
    rows = suggested_starts([result], {"2027-02-22"})
    assert [r["title"] for r in rows] == ["Midterm Exam"]
    assert {"course", "title", "due", "start_by", "days_ahead"} <= set(rows[0])
    assert rows[0]["start_by"] == "2027-02-18"  # 12 hours at 2 a day = 6 days before
