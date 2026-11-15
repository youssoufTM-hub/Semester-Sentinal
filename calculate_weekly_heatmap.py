from datetime import datetime, date, timedelta
from collections import defaultdict

WEIGHTS = {
    "exam": 3.0,
    "assignment": 2.0,
    "class": 1.0,
    "study": 1.0,
}

# Return the Monday of the given date as an ISO date string (YYYY-MM-DD)
def get_week_start(dt: datetime) -> str:
    monday = dt.date() - timedelta(days=dt.weekday())
    return monday.isoformat()


def calculate_event_score(event: dict) -> float:
    start = datetime.fromisoformat(event["start"])
    end = datetime.fromisoformat(event["end"])
    event_type = event.get("type", "class").lower() # e.g. "exam"

    duration_hours = (end - start).total_seconds() / 3600.0
    weight = WEIGHTS.get(event_type, 1.0)
    score = duration_hours * weight

    return score


def normalize_intensity(score: float, max_score: float) -> int:
    if max_score <= 0:
        return 0
    return min(4, int((score / max_score) * 4))

# Might need to fill in gap weeks since they won't exist in the output list
def calculate_weekly_heatmap(events: list[dict]) -> list[dict]:
    if not events:
        return []

    weekly_totals = defaultdict(float)
    weekly_event_counts = defaultdict(int)

    for event in events:
        score = calculate_event_score(event)
        week_key = get_week_start(datetime.fromisoformat(event["start"]))

        weekly_totals[week_key] += score
        weekly_event_counts[week_key] += 1

    max_score = max(weekly_totals.values()) if weekly_totals else 1.0

    results = []
    for week_key in sorted(weekly_totals.keys()):
        raw_score = round(weekly_totals[week_key], 2)
        results.append({
            "week_start":week_key,
            "raw_score": raw_score,
            "intensity": normalize_intensity(raw_score, max_score),
            "even_count": weekly_event_counts[week_key],
        })

    return results

