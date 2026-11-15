from datetime import datetime
import pytest

from calculate_weekly_heatmap import (
    get_week_start,
    calculate_event_score,
    normalize_intensity,
    calculate_weekly_heatmap,
)


def test_get_week_start():
    # Wednesday, Oct 15, 2025 -> should yield Monday, Oct 13, 2025
    wednesday = datetime(2025, 10, 15, 14, 30)
    assert get_week_start(wednesday) == "2025-10-13"

    # Monday should yield itself
    monday = datetime(2025, 10, 13, 9, 0)
    assert get_week_start(monday) == "2025-10-13"

    # Sunday should yield the preceding Monday
    sunday = datetime(2025, 10, 19, 23, 59)
    assert get_week_start(sunday) == "2025-10-13"


def test_calculate_event_score():
    # 2-hour exam: weight is 3.0 -> score should be 6.0
    exam_event = {
        "title": "Midterm",
        "start": "2025-10-15T10:00:00",
        "end": "2025-10-15T12:00:00",
        "type": "exam",
    }
    score = calculate_event_score(exam_event)
    assert score == 6.0

    # 1.5-hour standard class: default weight is 1.0 -> score should be 1.5
    class_event = {
        "title": "Lecture",
        "start": "2025-10-15T10:00:00",
        "end": "2025-10-15T11:30:00",
        "type": "class",
    }
    score = calculate_event_score(class_event)
    assert score == 1.5


def test_normalize_intensity():
    # 0 score should yield 0
    assert normalize_intensity(0.0, 100.0) == 0

    # Halfway (50 / 100 * 4 = 2)
    assert normalize_intensity(50.0, 100.0) == 2

    # Max score should clamp to 4
    assert normalize_intensity(100.0, 100.0) == 4

    # Guard when max_score is 0
    assert normalize_intensity(0.0, 0.0) == 0


def test_calculate_weekly_heatmap_end_to_end():
    sample_events = [
        # Week 1: Monday, Oct 13
        {
            "title": "Class A",
            "start": "2025-10-13T09:00:00",
            "end": "2025-10-13T10:00:00",
            "type": "class",
        },
        # Week 2: Monday, Oct 20 (busiest week)
        {
            "title": "Exam A",
            "start": "2025-10-20T13:00:00",
            "end": "2025-10-20T16:00:00", 
            "type": "exam",
        },
    ]

    result = calculate_weekly_heatmap(sample_events)

    assert len(result) == 2

    # Week 1
    assert result[0]["week_start"] == "2025-10-13"
    assert result[0]["raw_score"] == 1.0
    assert result[0]["intensity"] == 0  # 1.0 / 9.0 * 4 = 0

    # Week 2 (Max score week)
    assert result[1]["week_start"] == "2025-10-20"
    assert result[1]["raw_score"] == 9.0
    assert result[1]["intensity"] == 4  # 9.0 / 9.0 * 4 = 4


def test_calculate_weekly_heatmap_empty():
    assert calculate_weekly_heatmap([]) == []
