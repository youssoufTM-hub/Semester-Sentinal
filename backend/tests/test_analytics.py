import pytest
from analytics.calculate_weekly_heatmap import (
    calculate_item_points, get_score_level, calculate_weekly_heatmap)
from analytics.collisions import find_collisions
from analytics.models import deadline_from_event
from analytics.ics_export import build_ics


def ev(kind, day, pct=0, month=11):
    return {"title": f"{kind} {day}", "start": f"2026-{month:02d}-{day:02d}",
            "type": kind, "weight_pct": pct}


def dl(kind, day, pct=0):
    return deadline_from_event(ev(kind, day, pct))


def test_readme_example_end_to_end():
    result = calculate_weekly_heatmap(
        [ev("exam", 12, 30), ev("project", 13, 25), ev("assignment", 10, 5)])
    assert len(result) == 1
    assert result[0]["week_start"] == "2026-11-09"
    assert result[0]["score"] == 11.5
    assert result[0]["level"] == "orange"
    assert result[0]["is_final_boss_week"] is False
    assert result[0]["event_count"] == 3


def test_heavy_weight_boundary():
    assert calculate_item_points(ev("project", 1, 20)) == 4.5
    assert calculate_item_points(ev("project", 1, 19.9)) == 3


def test_level_boundaries():
    assert [get_score_level(s) for s in (3.99, 4, 7.99, 8, 11.99, 12)] == [
        "green", "yellow", "yellow", "orange", "orange", "red"]


def test_three_within_four_days_collide():
    assert len(find_collisions([dl("exam", 10), dl("exam", 11), dl("exam", 13)])) == 1


def test_four_days_apart_does_not_collide():
    assert find_collisions([dl("exam", 10), dl("exam", 11), dl("exam", 14)]) == []


def test_overlapping_windows_merge():
    result = find_collisions([dl("exam", d) for d in (10, 11, 13, 14)])
    assert len(result) == 1 and result[0].count == 4


def test_collision_across_week_boundary_is_counted():
    result = calculate_weekly_heatmap(
        [ev("exam", 13, 30), ev("exam", 14, 30), ev("exam", 16, 30)])
    assert result[0]["week_start"] == "2026-11-09"
    assert result[0]["collision_count"] == 1


def test_light_items_are_ignored():
    assert find_collisions([dl("quiz", 10), dl("quiz", 11), dl("quiz", 12)]) == []


def test_ics_has_one_event_per_deadline():
    data = build_ics([dl("exam", 10), dl("project", 11)])
    assert data.count(b"BEGIN:VEVENT") == 2