import json
from datetime import date

import pytest

from parser import (
    ParserError,
    SyllabusInput,
    SyllabusParser,
    TermBreak,
    TermContext,
    to_deadline_rows,
    to_event_inputs,
    to_review_rows,
)
from parser.models import parse_result_json_schema

PDF = b"%PDF-1.7 fake syllabus bytes"
TERM = TermContext(
    term_name="Winter 2027",
    start="2027-01-11",
    end="2027-04-24",
    breaks=[TermBreak(name="Reading Week", start="2027-02-15", end="2027-02-19")],
)


def _parser(fake_provider, *replies):
    provider = fake_provider(*replies)
    return provider, SyllabusParser(provider=provider, backoff_seconds=0)


# --- what we send to the provider --------------------------------------------

def test_provider_gets_document_prompt_and_schema(fake_provider, sample_result_json):
    provider, parser = _parser(fake_provider, sample_result_json)
    parser.parse(SyllabusInput(PDF, filename="csci.pdf", course_hint="CS principles"), TERM)

    call = provider.calls[0]
    assert call["document"].is_pdf and call["document"].filename == "csci.pdf"
    assert "2027-01-11" in call["prompt"] and "Reading Week" in call["prompt"]
    assert "CS principles" in call["prompt"]
    assert call["schema"]["type"] == "object" and "deadlines" in call["schema"]["properties"]


def test_schema_is_strict_and_flat():
    schema = parse_result_json_schema()
    assert "$defs" not in json.dumps(schema) and "$ref" not in json.dumps(schema)
    deadline = schema["properties"]["deadlines"]["items"]
    assert "title" in deadline["properties"]

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            assert "default" not in node
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)


# --- parsing the reply ------------------------------------------------------

def test_parse_returns_validated_result(fake_provider, sample_result_json):
    _, parser = _parser(fake_provider, sample_result_json)
    result = parser.parse(SyllabusInput(PDF), TERM)
    assert result.course.code == "CSCI 2010U"
    assert [d.kind for d in result.deadlines] == ["assignment", "exam", "project", "exam"]
    assert result.deadlines[3].due_date is None and result.deadlines[3].needs_review


def test_out_of_term_and_bad_dates_are_flagged(fake_provider, sample_result_json):
    sample_result_json["deadlines"][0]["due_date"] = "2026-12-01"
    sample_result_json["deadlines"][2]["due_date"] = "April 2nd"
    _, parser = _parser(fake_provider, sample_result_json)
    result = parser.parse(SyllabusInput(PDF), TERM)
    assert result.deadlines[0].needs_review and "outside the term" in result.deadlines[0].note
    assert result.deadlines[2].due_date is None and result.deadlines[2].needs_review


def test_weights_not_summing_to_100_warns(fake_provider, sample_result_json):
    sample_result_json["grading_scheme"][0]["weight_pct"] = 10
    _, parser = _parser(fake_provider, sample_result_json)
    result = parser.parse(SyllabusInput(PDF), TERM)
    assert any("90%" in w for w in result.warnings)


def test_malformed_json_is_retried_once(fake_provider, sample_result_json):
    provider, parser = _parser(fake_provider, "{not json", sample_result_json)
    assert parser.parse(SyllabusInput(PDF)).course.code == "CSCI 2010U"
    assert len(provider.calls) == 2


def test_malformed_twice_raises(fake_provider):
    _, parser = _parser(fake_provider, "{not json")
    with pytest.raises(ParserError, match="malformed"):
        parser.parse(SyllabusInput(PDF))


def test_temporary_errors_are_retried(fake_provider, provider_error, sample_result_json):
    busy = provider_error("busy", retryable=True)
    provider, parser = _parser(fake_provider, busy, busy, sample_result_json)
    assert parser.parse(SyllabusInput(PDF)).course.code == "CSCI 2010U"
    assert len(provider.calls) == 3


def test_permanent_errors_are_not_retried(fake_provider, provider_error, sample_result_json):
    provider, parser = _parser(fake_provider, provider_error("bad key"), sample_result_json)
    with pytest.raises(ParserError, match="bad key"):
        parser.parse(SyllabusInput(PDF))
    assert len(provider.calls) == 1


def test_rejects_bad_files(fake_provider, sample_result_json):
    _, parser = _parser(fake_provider, sample_result_json)
    with pytest.raises(ParserError):
        parser.parse(SyllabusInput(b"hello", filename="x.pdf"))
    with pytest.raises(ParserError):
        parser.parse(SyllabusInput(b"hello", filename="x.png"))


def test_text_syllabus_is_accepted(fake_provider, sample_result_json):
    provider, parser = _parser(fake_provider, sample_result_json)
    parser.parse(SyllabusInput(b"CSCI 2010U outline. Midterm Feb 24.", filename="outline.txt"))
    doc = provider.calls[0]["document"]
    assert not doc.is_pdf and "Midterm Feb 24" in doc.text


def test_parse_many_keeps_going_after_a_failure(fake_provider, sample_result_json):
    _, parser = _parser(fake_provider, sample_result_json)
    out = parser.parse_many([SyllabusInput(PDF), SyllabusInput(b""), SyllabusInput(PDF)])
    assert isinstance(out[1], ParserError)
    assert out[0].course.code == out[2].course.code == "CSCI 2010U"


# --- converters ---------------------------------------------------------------

def test_deadline_rows_match_analytics_shape(fake_provider, sample_result_json):
    _, parser = _parser(fake_provider, sample_result_json)
    rows = to_deadline_rows([parser.parse(SyllabusInput(PDF), TERM)])
    assert len(rows) == 3  # undated final exam left out
    assert rows[1] == {"course": "CSCI 2010U", "title": "Midterm Exam", "kind": "exam",
                       "due": date(2027, 2, 24), "weight": 25.0}


def test_event_inputs_match_heatmap_shape(fake_provider, sample_result_json):
    _, parser = _parser(fake_provider, sample_result_json)
    events = to_event_inputs([parser.parse(SyllabusInput(PDF), TERM)], TERM)
    midterm = next(e for e in events if e["title"].endswith("Midterm Exam"))
    assert midterm["start"] == "2027-02-24T10:10:00" and midterm["end"] == "2027-02-24T11:30:00"
    project = next(e for e in events if e["title"].endswith("Term Project"))
    assert project["end"] == "2027-04-02T23:59:00" and project["start"] == "2027-04-01T22:59:00"

    classes = [e for e in events if e["type"] == "class"]
    # Mon+Wed for 15 weeks (Jan 11 - Apr 24) minus reading week = 28 meetings
    assert len(classes) == 28
    assert not any(e["start"].startswith("2027-02-1") and e["start"] >= "2027-02-15"
                   and e["start"] < "2027-02-20" for e in classes)
    for e in events:
        assert set(e) == {"title", "start", "end", "type", "weight_pct"}


def test_review_rows_sort_undated_last(fake_provider, sample_result_json):
    _, parser = _parser(fake_provider, sample_result_json)
    rows = to_review_rows([parser.parse(SyllabusInput(PDF), TERM)])
    assert rows[-1]["title"] == "Final Exam"
    assert rows[0]["course"] == "CSCI 2010U"


def test_rows_feed_analytics_once_merged(fake_provider, sample_result_json):
    models = pytest.importorskip("analytics.models")
    _, parser = _parser(fake_provider, sample_result_json)
    deadlines = [models.Deadline(**r) for r in to_deadline_rows([parser.parse(SyllabusInput(PDF), TERM)])]
    assert deadlines[0].kind == "assignment"
