from datetime import datetime, date, timedelta
from collections import defaultdict

WEIGHTS = {
    "exam": 4.0,
    "project": 3.0,
    "quiz": 1.5,
    "assignment": 1.0,
    "class": 1.0,
    "study": 1.0,
}

HEAVY_TYPES = {"exam", "project"}

# Returns the Monday of the given datetime as YYYY-MM-DD.
def get_week_start(dt: datetime) -> str:
    monday = dt.date() - timedelta(days=dt.weekday())
    return monday.isoformat()


def calculate_item_points(event: dict) -> float:
    event_type = event.get("type", "assignment").lower()
    weight_pct = event.get("weight_pct", 0.0) or 0.0

    base = WEIGHTS.get(event_type, 1.0)
    multiplier = 1.5 if weight_pct >= 20.0 else 1.0

    return base * multiplier


def get_score_level(score: float) -> str:
    if score < 4.0:
        return "green"
    elif score < 8.0:
        return "yellow"
    elif score < 12.0:
        return "orange"
    else:
        return "red"


def count_collisions(week_events: list[dict]) -> int:
    heavy_dates = []
    for event in week_events:
        event_type = event.get("type", "assignment").lower()
        weight_pct = event.get("weight_pct", 0.0) or 0.0
        if event_type in HEAVY_TYPES or weight_pct >= 20.0:
            heavy_dates.append(datetime.fromisoformat(event["start"]).date())

    heavy_dates.sort()
    n = len(heavy_dates)
    if n < 3:
        return 0


    collisions = 0
    # A 4-day window means: date_k - date_i <= 3 days (e.g. Mon to Thu is 3 days diff)
    for i in range(n - 2):
        if (heavy_dates[i + 2] - heavy_dates[i]).days <= 3:
            collisions += 1

    return collisions


def calculate_weekly_heatmap(events: list[dict]) -> list[dict]:
    if not events:
        return []

    weeks_events = defaultdict(list)
    for event in events:
        start_dt = datetime.fromisoformat(event["start"])
        week_key = get_week_start(start_dt)
        weeks_events[week_key].append(event)

    results = []
    for week_key in sorted(weeks_events.keys()):
        week_items = weeks_events[week_key]
        
        total_score = sum(calculate_item_points(ev) for ev in week_items)
        total_score = round(total_score, 2)

        level = get_score_level(total_score)
        is_final_boss = total_score >= 12.0

        collisions = count_collisions(week_items)

        results.append({
            "week_start": week_key,
            "score": total_score,
            "level": level,
            "is_final_boss_week": is_final_boss,
            "collision_count": collisions,
            "event_count": len(week_items),
        })

    return results
