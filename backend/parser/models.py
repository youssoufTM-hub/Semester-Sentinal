from __future__ import annotations

import copy
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

# same types analytics scores
Kind = Literal["exam", "project", "quiz", "assignment"]
MeetingKind = Literal["lecture", "lab", "tutorial", "seminar", "other"]
Weekday = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class TermBreak(BaseModel):
    name: str = Field(description="e.g. 'Reading Week', 'Thanksgiving'")
    start: str = Field(description="YYYY-MM-DD")
    end: str = Field(description="YYYY-MM-DD, inclusive")


class TermContext(BaseModel):
    term_name: Optional[str] = None
    start: Optional[str] = Field(None, description="First day of classes, YYYY-MM-DD")
    end: Optional[str] = Field(None, description="Last day of exams, YYYY-MM-DD")
    breaks: list[TermBreak] = Field(default_factory=list)


class CourseInfo(BaseModel):
    code: Optional[str] = Field(description="Course code as written, e.g. 'CSCI 2010U'")
    name: Optional[str] = Field(description="Course title")
    term: Optional[str] = Field(description="Term as written, e.g. 'Winter 2027'")
    instructor: Optional[str]
    term_start: Optional[str] = Field(description="First day of classes YYYY-MM-DD if known")
    term_end: Optional[str] = Field(description="Last day of term/exams YYYY-MM-DD if known")


class Meeting(BaseModel):
    kind: MeetingKind
    day: Weekday
    start_time: str = Field(description="24h HH:MM")
    end_time: str = Field(description="24h HH:MM")
    location: Optional[str]
    section: Optional[str] = Field(description="Section label if the syllabus lists several, e.g. 'LAB 002'")


class GradeComponent(BaseModel):
    name: str = Field(description="Component as named in the grading breakdown")
    weight_pct: float = Field(description="Total percent of the final grade")


class Deadline(BaseModel):
    title: str = Field(description="Short title, e.g. 'Assignment 3' or 'Midterm Exam'")
    kind: Kind
    raw_label: str = Field(description="What the syllabus calls it, verbatim")
    due_date: Optional[str] = Field(description="YYYY-MM-DD, or null if the syllabus gives no resolvable date")
    due_time: Optional[str] = Field(description="24h HH:MM if stated, else null")
    end_time: Optional[str] = Field(description="24h HH:MM end time for timed exams/tests if stated, else null")
    weight_pct: Optional[float] = Field(description="Percent of final grade for this item, or null if unknown")
    estimated_hours: float = Field(description="Estimated hours of student work to prepare/complete this item")
    date_source: str = Field(description="Exact syllabus text the date was derived from")
    confidence: Literal["high", "medium", "low"]
    needs_review: bool = Field(description="True if the student should double-check this row")
    note: Optional[str] = Field(description="Why it needs review, or how the date/weight was derived")


class ParseResult(BaseModel):
    course: CourseInfo
    deadlines: list[Deadline]
    meetings: list[Meeting]
    grading_scheme: list[GradeComponent]
    warnings: list[str] = Field(description="Problems the student should know about (TBA dates, conflicting info, ...)")
    # set by the parser, not the model: the name the student gave the course
    label: Optional[str] = None


def _strictify(node):
    if isinstance(node, dict):
        # don't drop a property that is literally called "title"
        if not isinstance(node.get("title"), dict):
            node.pop("title", None)
        node.pop("default", None)
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"].keys())
            for prop in node["properties"].values():
                _strictify(prop)
        for key, value in node.items():
            if key != "properties":
                _strictify(value)
    elif isinstance(node, list):
        for value in node:
            _strictify(value)
    return node


def _inline_refs(node, defs):
    # gemini handles flat schemas better
    if isinstance(node, dict):
        ref = node.get("$ref")
        if ref and ref.startswith("#/$defs/"):
            return _inline_refs(copy.deepcopy(defs[ref.split("/")[-1]]), defs)
        return {k: _inline_refs(v, defs) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_inline_refs(v, defs) for v in node]
    return node


def parse_result_json_schema() -> dict:
    schema = copy.deepcopy(ParseResult.model_json_schema())
    schema["properties"].pop("label", None)
    schema = _inline_refs(schema, schema.get("$defs", {}))
    return _strictify(schema)


def parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
