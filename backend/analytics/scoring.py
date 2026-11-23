from datetime import date, timedelta
from .models import Deadline, WeekScore

POINTS = {"exam": 4, "project": 3, "quiz": 1.5, "assignment": 1}
HEAVY_WEIGHT = 20
HEAVY_MULTIPLIER = 1.5


def item_points(d: Deadline) -> float:
    kind = d.kind.lower()
    if kind not in POINTS:
        raise ValueError(f"Unknown deadline type: {d.kind}")
    points = POINTS[kind]
    if d.weight >= HEAVY_WEIGHT:
        points *= HEAVY_MULTIPLIER
    return points


def colour_for(score: float) -> str:
    if score < 4:
        return "green"
    if score < 8:
        return "yellow"
    if score < 12:
        return "orange"
    return "red"


def score_weeks(deadlines: list[Deadline]) -> list[WeekScore]:
    grouped: dict[date, list[Deadline]] = {}
    for deadline in deadlines:
        monday = deadline.due - timedelta(days=deadline.due.weekday())
        grouped.setdefault(monday, []).append(deadline)

    weeks: list[WeekScore] = []
    for monday in sorted(grouped):
        items = grouped[monday]
        score = sum(item_points(item) for item in items)
        weeks.append(
            WeekScore(
                week_start=monday,
                score=score,
                level=colour_for(score),
                is_final_boss=score >= 12,
                items=items,
            )
        )
    return weeks