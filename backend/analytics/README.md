# Analytics (`backend/analytics/`)

The analytics package turns deadline event dictionaries into weekly workload
scores, detects clusters of major deadlines, and exports deadlines as an
iCalendar (`.ics`) file. It does not parse syllabus files or expose an HTTP
endpoint.

## Weekly heatmap

`calculate_weekly_heatmap(events)` groups events by the Monday of their due
week. Each event must include `start`, an ISO date or datetime string.
`type`, `weight_pct`, `course`, and `title` are optional.

```python
from analytics.calculate_weekly_heatmap import calculate_weekly_heatmap

events = [
    {"course": "PHYS", "title": "Midterm", "start": "2026-11-12",
     "type": "exam", "weight_pct": 30},
    {"course": "CS", "title": "Project", "start": "2026-11-13",
     "type": "project", "weight_pct": 25},
    {"course": "MATH", "title": "Assignment", "start": "2026-11-10",
     "type": "assignment", "weight_pct": 5},
]

print(calculate_weekly_heatmap(events))
```

Each result contains `week_start` (Monday as `YYYY-MM-DD`), `score`, `level`,
`is_final_boss_week`, `collision_count`, and `event_count`.

Base points by event type are:

| Type | Points |
|---|---:|
| Exam | 4 |
| Project | 3 |
| Quiz | 1.5 |
| Assignment | 1 |
| Class or study | 1 |

Events worth 20% or more of the course grade receive a 1.5× multiplier.
Unknown event types default to 1 point. Score levels are green below 4, yellow
from 4 to under 8, orange from 8 to under 12, and red at 12 or more. Red weeks
are marked as Final Boss Weeks.

## Deadline models and collisions

`analytics.models.Deadline` represents a deadline with `course`, `title`,
`kind`, `due` (`datetime.date`), and `weight`. Use
`deadline_from_event(event)` to convert an event dictionary into a model.

`collisions.find_collisions(deadlines)` considers exams, projects, and
deadlines worth at least 20% to be heavy. A collision is a four-day inclusive
window containing at least three heavy deadlines. Overlapping qualifying
windows are merged. `collisions_per_week(collisions)` counts each collision
in the week containing its start date; the heatmap reports that count in
`collision_count`.

## Calendar export

`ics_export.build_ics(deadlines)` returns calendar data as `bytes`. Each
deadline becomes an all-day event titled `<course>: <title>`, ending the day
after its due date. Event UIDs are deterministic for the same course, title,
and due date.

```python
from pathlib import Path

from analytics.ics_export import build_ics

Path("deadlines.ics").write_bytes(build_ics(deadlines))
```

## Setup and tests

Run commands from the `backend/` directory:

```powershell
pip install -r requirements.txt
python -m pytest
```

The tests cover heatmap scores and thresholds, collision rules and weekly
grouping, and calendar event generation. For the sample-data sensitivity
analysis, see [`backend/scripts/README.md`](../scripts/README.md).
