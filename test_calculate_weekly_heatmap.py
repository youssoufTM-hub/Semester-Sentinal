from datetime import datetime
import pytest

from calculate_weekly_heatmap import (
    get_week_start,
    calculate_item_points,
    get_score_level,
    count_collisions,
    calculate_weekly_heatmap,
)


def test_get_week_start():
    # Wednesday -> should yield Monday
    wednesday = datetime(2025, 10, 15, 14, 30)
    assert get_week_start(wednesday) == "2025-10-13"

    # Sunday -> should yield preceding Monday
    sunday = datetime(2025, 10, 19, 23, 59)
    assert get_week_start(sunday) == "2025-10-13"


def test_calculate_item_points_base():
    # Base points without 20% multiplier
    assert calculate_item_points({"type": "exam", "weight_pct": 10.0}) == 4.0
    assert calculate_item_points({"type": "project", "weight_pct": 0.0}) == 3.0
    assert calculate_item_points({"type": "quiz", "weight_pct": 15.0}) == 1.5
    assert calculate_item_points({"type": "assignment", "weight_pct": 5.0}) == 1.0


def test_calculate_item_points_with_multiplier():
    # >= 20% weight receives a 1.5x boost
    assert calculate_item_points({"type": "exam", "weight_pct": 20.0}) == 6.0      # 4 * 1.5
    assert calculate_item_points({"type": "project", "weight_pct": 25.0}) == 4.5   # 3 * 1.5
    assert calculate_item_points({"type": "quiz", "weight_pct": 30.0}) == 2.25    # 1.5 * 1.5
    assert calculate_item_points({"type": "assignment", "weight_pct": 20.0}) == 1.5 # 1.0 * 1.5


def test_get_score_level():
    assert get_score_level(0.0) == "green"
    assert get_score_level(3.9) == "green"
    assert get_score_level(4.0) == "yellow"
    assert get_score_level(7.9) == "yellow"
    assert get_score_level(8.0) == "orange"
    assert get_score_level(11.9) == "orange"
    assert get_score_level(12.0) == "red"
    assert get_score_level(20.5) == "red"


def test_count_collisions():
    # 3 heavy items within 4 days (Mon, Tue, Thu) -> 1 collision
    colliding_events = [
        {"title": "Exam 1", "type": "exam", "weight_pct": 10.0, "start": "2025-10-13T10:00:00"},
        {"title": "Project 1", "type": "project", "weight_pct": 10.0, "start": "2025-10-14T10:00:00"},
        {"title": "Heavy Quiz", "type": "quiz", "weight_pct": 25.0, "start": "2025-10-16T10:00:00"},
    ]
    assert count_collisions(colliding_events) == 1

    # 3 heavy items spread across more than 4 days (Mon, Tue, Fri) -> 0 collisions
    spaced_events = [
        {"title": "Exam 1", "type": "exam", "weight_pct": 10.0, "start": "2025-10-13T10:00:00"},
        {"title": "Project 1", "type": "project", "weight_pct": 10.0, "start": "2025-10-14T10:00:00"},
        {"title": "Heavy Quiz", "type": "quiz", "weight_pct": 25.0, "start": "2025-10-17T10:00:00"}, # 4 days after Mon (diff = 4)
    ]
    assert count_collisions(spaced_events) == 0

    # 3 items, but only 2 are heavy -> 0 collisions
    not_enough_heavy = [
        {"title": "Exam 1", "type": "exam", "weight_pct": 10.0, "start": "2025-10-13T10:00:00"},
        {"title": "Project 1", "type": "project", "weight_pct": 10.0, "start": "2025-10-14T10:00:00"},
        {"title": "Light HW", "type": "assignment", "weight_pct": 5.0, "start": "2025-10-15T10:00:00"},
    ]
    assert count_collisions(not_enough_heavy) == 0


def test_example_scenario():
    # Physics midterm (30%), CS project (25%), Stats assignment (5%)
    # Expected: 6.0 + 4.5 + 1.0 = 11.5 -> Orange, not final boss
    events = [
        {"title": "Physics Midterm", "start": "2025-10-14T10:00:00", "type": "exam", "weight_pct": 30.0},
        {"title": "CS Project", "start": "2025-10-15T23:59:00", "type": "project", "weight_pct": 25.0},
        {"title": "Stats Assignment", "start": "2025-10-17T17:00:00", "type": "assignment", "weight_pct": 5.0},
    ]

    result = calculate_weekly_heatmap(events)
    assert len(result) == 1

    week = result[0]
    assert week["week_start"] == "2025-10-13"
    assert week["score"] == 11.5
    assert week["level"] == "orange"
    assert week["is_final_boss_week"] is False
    assert week["collision_count"] == 0
    assert week["event_count"] == 3


def test_final_boss_week():
    # Two heavily weighted exams: 6.0 + 6.0 = 12.0 -> Final Boss Week (Red)
    events = [
        {"title": "Final 1", "start": "2025-12-08T09:00:00", "type": "exam", "weight_pct": 30.0},
        {"title": "Final 2", "start": "2025-12-10T09:00:00", "type": "exam", "weight_pct": 30.0},
    ]

    result = calculate_weekly_heatmap(events)
    assert len(result) == 1

    week = result[0]
    assert week["score"] == 12.0
    assert week["level"] == "red"
    assert week["is_final_boss_week"] is True


def test_empty_events():
    assert calculate_weekly_heatmap([]) == []
