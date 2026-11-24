from datetime import date

from analytics.models import Deadline
from analytics.collisions import Collision, collisions_per_week, find_collisions, is_heavy


def deadline(title: str, kind: str, due: date, weight: float = 5) -> Deadline:
    return Deadline(course="TEST", title=title, kind=kind, due=due, weight=weight)


def test_is_heavy_uses_kind_and_weight_contract():
    assert is_heavy(deadline("Exam", "exam", date(2026, 11, 10)))
    assert is_heavy(deadline("Project", "project", date(2026, 11, 10)))
    assert is_heavy(deadline("Heavily weighted", "assignment", date(2026, 11, 10), 20))
    assert not is_heavy(deadline("Normal", "quiz", date(2026, 11, 10), 10))


def test_find_collisions_finds_and_merges_four_day_windows():
    deadlines = [
        deadline("Exam", "exam", date(2026, 11, 10)),
        deadline("Project", "project", date(2026, 11, 11)),
        deadline("Assignment", "assignment", date(2026, 11, 13), 25),
        deadline("Quiz", "quiz", date(2026, 11, 20)),
    ]

    assert find_collisions(deadlines) == [
        Collision(start=date(2026, 11, 10), end=date(2026, 11, 13), count=3)
    ]


def test_deadlines_four_days_apart_do_not_collide():
    deadlines = [
        deadline("Exam 1", "exam", date(2026, 11, 10)),
        deadline("Exam 2", "exam", date(2026, 11, 11)),
        deadline("Exam 3", "exam", date(2026, 11, 14)),
    ]

    assert find_collisions(deadlines) == []


def test_overlapping_collision_windows_merge():
    deadlines = [
        deadline(f"Exam {day}", "exam", date(2026, 11, day))
        for day in (10, 11, 13, 14)
    ]

    assert find_collisions(deadlines) == [
        Collision(start=date(2026, 11, 10), end=date(2026, 11, 14), count=4)
    ]


def test_same_day_deadlines_count_separately():
    same_day = date(2026, 11, 10)
    deadlines = [deadline(f"Exam {i}", "exam", same_day) for i in range(3)]

    assert find_collisions(deadlines) == [Collision(start=same_day, end=same_day, count=3)]


def test_light_deadlines_are_excluded_from_collisions():
    deadlines = [
        deadline("Quiz 1", "quiz", date(2026, 11, 10)),
        deadline("Quiz 2", "quiz", date(2026, 11, 11)),
        deadline("Quiz 3", "quiz", date(2026, 11, 12)),
    ]

    assert find_collisions(deadlines) == []


def test_collisions_per_week_counts_by_start_monday():
    collisions = [
        Collision(start=date(2026, 11, 10), end=date(2026, 11, 13), count=3),
        Collision(start=date(2026, 11, 12), end=date(2026, 11, 14), count=3),
    ]

    assert collisions_per_week(collisions) == {"2026-11-09": 2}
