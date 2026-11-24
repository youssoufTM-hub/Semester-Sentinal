"""Converts a ParseResult into the formats analytics, heatmap and frontend use."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Iterable, Optional

from .models import ParseResult, TermContext, parse_iso_date

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def course_label(result: ParseResult) -> str:
    return result.course.code or result.course.name or "Unknown course"


def to_deadline_rows(results: Iterable[ParseResult]) -> list[dict]:
    # undated items are skipped (analytics needs a date)
    rows = []
    for result in results:
        for d in result.deadlines:
            due = parse_iso_date(d.due_date)
            if due is None:
                continue
            rows.append({
                "course": course_label(result),
                "title": d.title,
                "kind": d.kind,
                "due": due,
                "weight": d.weight_pct if d.weight_pct is not None else 0.0,
            })
    return rows


def _hhmm(value: Optional[str], default: time) -> time:
    if not value:
        return default
    try:
        return time.fromisoformat(value)
    except ValueError:
        return default


def to_event_inputs(
    results: Iterable[ParseResult],
    term: Optional[TermContext] = None,
    include_classes: bool = True,
) -> list[dict]:
    # timed exams use real start/end, everything else is estimated_hours before the due time
    events: list[dict] = []
    for result in results:
        course = course_label(result)
        for d in result.deadlines:
            due = parse_iso_date(d.due_date)
            if due is None:
                continue
            if d.kind == "exam" and d.due_time and d.end_time:
                start = datetime.combine(due, _hhmm(d.due_time, time(9)))
                end = datetime.combine(due, _hhmm(d.end_time, time(11)))
                if end <= start:
                    end = start + timedelta(hours=max(d.estimated_hours, 1))
            else:
                end = datetime.combine(due, _hhmm(d.due_time, time(23, 59)))
                start = end - timedelta(hours=max(d.estimated_hours, 0.5))
            events.append({
                "title": f"{course}: {d.title}",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "type": d.kind,
                "weight_pct": d.weight_pct,
            })
        if include_classes:
            events.extend(_meeting_events(result, term))
    return events


def _meeting_events(result: ParseResult, term: Optional[TermContext]) -> list[dict]:
    start = parse_iso_date((term.start if term else None) or result.course.term_start)
    end = parse_iso_date((term.end if term else None) or result.course.term_end)
    if not start or not end or not result.meetings:
        return []
    breaks = []
    for b in (term.breaks if term else []):
        bs, be = parse_iso_date(b.start), parse_iso_date(b.end)
        if bs and be:
            breaks.append((bs, be))

    course = course_label(result)
    events = []
    day = start
    while day <= end:
        if not any(bs <= day <= be for bs, be in breaks):
            weekday = _WEEKDAYS[day.weekday()]
            for m in result.meetings:
                if m.day != weekday:
                    continue
                s = datetime.combine(day, _hhmm(m.start_time, time(9)))
                e = datetime.combine(day, _hhmm(m.end_time, time(10)))
                if e <= s:
                    continue
                events.append({
                    "title": f"{course}: {m.kind}",
                    "start": s.isoformat(),
                    "end": e.isoformat(),
                    "type": "class",
                    "weight_pct": None,
                })
        day += timedelta(days=1)
    return events


def to_review_rows(results: Iterable[ParseResult]) -> list[dict]:
    rows = []
    for result in results:
        for d in result.deadlines:
            row = d.model_dump()
            row["course"] = course_label(result)
            rows.append(row)
    rows.sort(key=lambda r: (r["due_date"] is None, r["due_date"] or "", r["course"]))
    return rows
