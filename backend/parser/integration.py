"""Glue between the parser and backend/analytics.

Uses the analytics package as it is (Deadline, calculate_weekly_heatmap,
find_collisions, build_ics). Run from backend/ so `analytics` can be imported.
"""
from __future__ import annotations

import importlib.util
import math
from datetime import timedelta
from typing import Iterable

from .convert import course_label, to_deadline_rows, to_event_inputs
from .models import ParseResult, parse_iso_date

# for "when to start": how many hours a student puts into one item per day
STUDY_HOURS_PER_DAY = 2
HEAVY_LEVELS = ("orange", "red")


def analytics_available() -> bool:
    return importlib.util.find_spec("analytics") is not None


def to_analytics_deadlines(results: Iterable[ParseResult]) -> list:
    from analytics.models import Deadline

    return [Deadline(**row) for row in to_deadline_rows(results)]


def _monday(day):
    return day - timedelta(days=day.weekday())


def _dated_items(results: Iterable[ParseResult]):
    for result in results:
        for d in result.deadlines:
            due = parse_iso_date(d.due_date)
            if due is not None:
                yield course_label(result), d, due


def analyze(results: Iterable[ParseResult]) -> dict:
    """Weekly scores and collisions from analytics, plus the two things only the
    parser knows: estimated hours per week and when to start heavy-week items."""
    from analytics.collisions import collisions_per_week, find_collisions

    results = list(results)
    deadlines = to_analytics_deadlines(results)
    collisions = find_collisions(deadlines)
    per_week = collisions_per_week(collisions)

    hours: dict[str, float] = {}
    items: dict[str, list[str]] = {}
    for course, d, due in _dated_items(results):
        monday = _monday(due).isoformat()
        hours[monday] = hours.get(monday, 0) + d.estimated_hours
        items.setdefault(monday, []).append(f"{course}: {d.title}")

    weeks = []
    heavy_weeks = set()
    for w in weekly_scores(results):
        monday = w["week_start"]
        if w["level"] in HEAVY_LEVELS:
            heavy_weeks.add(monday)
        weeks.append({
            "week_start": monday,
            "score": w["score"],
            "level": w["level"],
            "is_final_boss": w["is_final_boss"],
            "collisions": per_week.get(monday, 0),
            "estimated_hours": round(hours.get(monday, 0), 1),
            "items": items.get(monday, []),
        })

    return {
        "weeks": weeks,
        "collisions": [
            {"start": c.start.isoformat(), "end": c.end.isoformat(), "count": c.count}
            for c in collisions
        ],
        "suggested_starts": suggested_starts(results, heavy_weeks),
    }


def weekly_scores(results: Iterable[ParseResult]) -> list[dict]:
    """One {week_start, score, level, is_final_boss} per week with deadlines.

    Analytics scores weeks with calculate_weekly_heatmap(); older versions of the
    package had analytics.scoring.score_weeks() instead, so both are supported."""
    results = list(results)
    try:
        from analytics.calculate_weekly_heatmap import calculate_weekly_heatmap
    except ImportError:
        from analytics.scoring import score_weeks

        return [
            {"week_start": w.week_start.isoformat(), "score": w.score,
             "level": w.level, "is_final_boss": w.is_final_boss}
            for w in score_weeks(to_analytics_deadlines(results))
            if w.items
        ]
    return [
        {"week_start": w["week_start"], "score": w["score"],
         "level": w["level"], "is_final_boss": w["is_final_boss_week"]}
        for w in calculate_weekly_heatmap(to_event_inputs(results))
    ]


def suggested_starts(results: Iterable[ParseResult], heavy_weeks: set[str]) -> list[dict]:
    # same keys as frontend logic.suggested_starts(), but based on the estimated hours
    rows = []
    for course, d, due in _dated_items(results):
        if _monday(due).isoformat() not in heavy_weeks:
            continue
        days = max(1, math.ceil(d.estimated_hours / STUDY_HOURS_PER_DAY))
        rows.append({
            "course": course,
            "title": d.title,
            "due": due.isoformat(),
            "start_by": (due - timedelta(days=days)).isoformat(),
            "days_ahead": days,
            "estimated_hours": d.estimated_hours,
        })
    rows.sort(key=lambda r: (r["due"], r["course"]))
    return rows


def to_ics(results: Iterable[ParseResult]) -> bytes:
    from analytics.ics_export import build_ics

    return build_ics(to_analytics_deadlines(results))
