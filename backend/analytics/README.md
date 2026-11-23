# Analytics (`backend/analytics/`)

This package turns syllabus deadlines into weekly workload scores, identifies
clusters of major deadlines, and exports deadlines as an iCalendar (`.ics`)
file. It is the analytics layer for Semester Sentinel; it does not parse
syllabus files or expose an HTTP endpoint.

## Flow

```text
Deadline records
    ├── scoring.score_weeks()       → weekly scores and risk levels
    ├── collisions.find_collisions() → major-deadline collision windows
    └── ics_export.build_ics()      → downloadable calendar data
```

## Deadline data

Analytics functions accept `Deadline` objects from `models.py`:

| Field | Type | Meaning |
|---|---|---|
| `course` | `str` | Course name or code |
| `title` | `str` | Deadline title |
| `kind` | `str` | `exam`, `project`, `quiz`, or `assignment` |
| `due` | `datetime.date` | Due date |
| `weight` | `float` | Percentage of the course grade |

## Weekly workload scoring

`scoring.score_weeks(deadlines)` groups deadlines by the Monday of their week.
Each item contributes points based on its kind:

| Kind | Base points |
|---|---:|
| Exam | 4 |
| Project | 3 |
| Quiz | 1.5 |
| Assignment | 1 |

Items worth 20% or more of the course grade receive a 1.5× multiplier. Weekly
scores map to risk levels as follows:

| Score | Level |
|---:|---|
| Under 4 | Green |
| 4 to under 8 | Yellow |
| 8 to under 12 | Orange |
| 12 or more | Red (`is_final_boss`) |

An unrecognized deadline kind raises `ValueError`.

## Collision detection

`collisions.find_collisions(deadlines)` considers exams, projects, and any
deadline worth at least 20% to be heavy. A collision is a four-day inclusive
window containing at least three heavy deadlines and overlapping windows are
merged. Each `Collision` reports its first and last due dates and the number
of heavy deadlines in the merged window.

`collisions.collisions_per_week(collisions)` counts collisions by the Monday
of each collision's start week. Its keys are ISO date strings (`YYYY-MM-DD`).

## Calendar export

`ics_export.build_ics(deadlines)` returns calendar data as `bytes`. Each
deadline becomes an all-day event titled `<course>: <title>`, ending the day
after its due date as required by the iCalendar all-day event format. Event
UIDs are deterministic for the same course, title, and due date.

## Use it

Run commands from the `backend/` directory:

```powershell
pip install -r requirements.txt
python -c "from datetime import date; from analytics.models import Deadline; from analytics.scoring import score_weeks; print(score_weeks([Deadline('PHY', 'Midterm', 'exam', date(2026, 11, 12), 30)]))"
```

To create an `.ics` file from application code:

```python
from pathlib import Path

from analytics.ics_export import build_ics

Path("deadlines.ics").write_bytes(build_ics(deadlines))
```

## Tests

From `backend/`, run the analytics tests with:

```powershell
pytest tests/test_scoring.py tests/test_analytics.py tests/test_collisions.py
```

The tests cover score calculations and thresholds, collision rules and weekly
grouping, and calendar event generation.
