from dataclasses import dataclass
from datetime import date, timedelta

try:
    from .models import Deadline
except ImportError:
    from analytics.models import Deadline

WINDOW_DAYS = 4
MIN_HEAVY = 3
HEAVY_WEIGHT = 20


@dataclass(frozen=True)
class Collision:
    start: date
    end: date
    count: int


def is_heavy(d: Deadline) -> bool:
    return d.kind.lower() in ("exam", "project") or d.weight >= HEAVY_WEIGHT


def find_collisions(deadlines: list[Deadline]) -> list[Collision]:
    heavy = sorted((d for d in deadlines if is_heavy(d)), key=lambda d: d.due)
    span = timedelta(days=WINDOW_DAYS - 1)

    # (first_index, last_index)
    windows = []  
    j = 0
    for i in range(len(heavy)):
        j = max(j, i)
        while j + 1 < len(heavy) and heavy[j + 1].due - heavy[i].due <= span:
            j += 1
        if j - i + 1 >= MIN_HEAVY:
            windows.append((i, j))

    #merges windows that share items into one collision.
    merged = []
    for first, last in windows:
        if merged and first <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], last)
        else:
            merged.append([first, last])

    return [
        Collision(start=heavy[a].due, end=heavy[b].due, count=b - a + 1)
        for a, b in merged
    ]


def collisions_per_week(collisions: list[Collision]) -> dict[str, int]:
    #maps a week's Monday to the number of collisions starting in it.
    counts: dict[str, int] = {}
    for c in collisions:
        monday = (c.start - timedelta(days=c.start.weekday())).isoformat()
        counts[monday] = counts.get(monday, 0) + 1
    return counts