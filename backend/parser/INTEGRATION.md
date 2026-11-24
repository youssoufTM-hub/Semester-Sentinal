# Integrating with the parser

What the parser gives each part of the project, and what came up when it was run
together with the other branches. Tested with `tests/test_integration.py` and a live run
of the frontend against the parser.

## Project layout (all branches)

```
Semester-Sentinal/
├── .gitignore, CONTRIBUTING.md, LICENSE, README.md   in every branch (identical, except
│                                                      Analytics filled in its team row)
├── frontend/                  main + feat/streamlit-frontend   Streamlit app
│   ├── app.py, api.py, logic.py, demo.json, requirements.txt
├── backend/
│   ├── requirements.txt       Analytics
│   ├── analytics/             Analytics        scoring, collisions, .ics export
│   ├── tests/                 Analytics        analytics tests
│   ├── parser/                feat/ai-parser   this folder
│   └── app/                   not in any branch yet
├── calculate_weekly_heatmap.py, endpoints.py,     feat/calculate_weekly_heatmap
│   schemas.py, test_calculate_weekly_heatmap.py   (at the repo root)
```

No two branches have a file at the same path apart from the four shared root files, so
the branches merge without conflicts. The parser only adds files under `backend/parser/`.

## How the data flows

```
frontend/api.py ── POST /api/parse/syllabi ──► parser/router.py
                                                  │
        ┌────────────────────┬────────────────────┼────────────────────┐
        ▼                    ▼                    ▼                    ▼
  "review_rows"         "deadlines"           "events"            "analysis"
  frontend Review    analytics Deadline   heatmap EventInput   scores, collisions,
  table                                                         hours, start dates
```

## API reference

### Endpoints

| Method | URL | What it does |
|---|---|---|
| `POST` | `/api/parse/syllabi` | Reads 1–8 syllabi and returns everything below |
| `GET` | `/api/parse/status` | `{"ready": true, "provider": "gemini", "model": "..."}`, or `{"ready": false, "error": "..."}` when no API key is set up |

`POST /api/parse/syllabi` takes a multipart form:

| field | required | example |
|---|---|---|
| `files` | yes, 1–8 | PDF, .docx or .txt files |
| `course_names` | no | `["CSCI1062U", "MATH1000U", "BUSI1700"]`, same order as `files` |
| `term` | no | `{"start": "2026-09-08", "end": "2026-12-19", "term_name": "Fall 2026", "breaks": [{"name": "Study Break", "start": "2026-10-12", "end": "2026-10-16"}]}` |

Status codes: `200` OK (some files may still be listed in `errors`), `400` bad form field
or file count, `422` no file could be parsed, `503` no API key on the server.

### Response

| key | shape | for |
|---|---|---|
| `review_rows` | every item: `course, title, kind, due_date, weight_pct, due_time, needs_review, note, estimated_hours, ...` | frontend Review tab |
| `deadlines` | dated items: `course, title, kind, due (YYYY-MM-DD), weight` | analytics |
| `events` | dated items: `title, start, end, type, weight_pct` | heatmap |
| `analysis` | `weeks`, `collisions`, `suggested_starts`, or `null` if analytics isn't in the branch | dashboard |
| `courses` | full result per syllabus: course info, class meetings, grading scheme, warnings | anyone |
| `errors` | `[{"file": ..., "error": ...}]` for files that couldn't be parsed | frontend warnings |

`analysis` looks like this:

```json
{
  "weeks": [{"week_start": "2026-10-05", "score": 15.0, "level": "red", "is_final_boss": true,
             "collisions": 0, "estimated_hours": 28.0, "items": ["CSCI1062U: Midterm 1", "..."]}],
  "collisions": [{"start": "2026-10-05", "end": "2026-10-07", "count": 3}],
  "suggested_starts": [{"course": "MATH1000U", "title": "Midterm I", "due": "2026-10-06",
                        "start_by": "2026-09-30", "days_ahead": 6, "estimated_hours": 12.0}]
}
```

`score`, `level`, `is_final_boss` and `collisions` are computed by the analytics code.
`estimated_hours` and `suggested_starts` come from the parser's hour estimate for each
item: an item in an orange or red week is started `estimated_hours / 2` days ahead
(2 hours a day, at least 1 day).

What every response guarantees:
- `kind` / `type` is always `exam`, `project`, `quiz` or `assignment`.
- `course` is the name sent in `course_names`; without one, it's the code on the syllabus.
- An item listed twice in a syllabus comes back once.
- Items with no date (TBA, registrar-scheduled finals) are only in `review_rows`, with
  `due_date: null` and `needs_review: true`.
- An item with no stated weight has `weight` 0.
- The same file with the same term and name is answered from memory (about 3s instead
  of about 60s).

### Python functions

All of them import from `parser` and work when run from `backend/`.

| Function | Returns |
|---|---|
| `SyllabusParser().parse(SyllabusInput(bytes, filename, course_hint), TermContext(...))` | `ParseResult` for one syllabus |
| `SyllabusParser().parse_many([...], term)` | list of `ParseResult` or `ParserError`, parsed at the same time |
| `to_review_rows(results)` | rows for the frontend table |
| `to_deadline_rows(results)` | dicts that fit `analytics.models.Deadline(**row)` |
| `to_analytics_deadlines(results)` | `list[analytics.models.Deadline]` |
| `to_event_inputs(results)` | dicts that fit the heatmap's `schemas.EventInput` |
| `analyze(results)` | the `analysis` dict above |
| `suggested_starts(results, heavy_weeks)` | the start-date rows on their own |
| `to_ics(results)` | `.ics` bytes from `analytics.ics_export.build_ics` |

### Errors

| Exception | When |
|---|---|
| `NoAPIKeyError` | no key in `parser_config.json` or `GEMINI_API_KEY` |
| `ParserError` | a file couldn't be read or parsed (the message is fine to show the user) |
| `ProviderError` | the model service failed (rate limit, overloaded, bad key) |

## What each part can use

### Backend and deployment

- `parser.router.router`: a FastAPI `APIRouter` with both endpoints, ready for
  `app.include_router(...)`.
- `parser/dev_server.py`: a small app with only the parser routes
  (`uvicorn parser.dev_server:app --reload` from `backend/`). It allows browser requests
  from `localhost:5173` and `localhost:8501`.
- `parser/requirements.txt`: the parser's packages.
- The key can come from the `GEMINI_API_KEY` environment variable, so no config file is
  needed on a server.
- Timing: 3–6 syllabi take about 30–75s, all parsed at once. The frontend waits up to
  180s.

### Analytics

- `deadlines` in the response, or `to_analytics_deadlines(results)` in Python, give
  `Deadline` objects directly.
- `analyze(results)` runs `score_weeks`, `find_collisions` and `collisions_per_week` on the
  parser output, and adds hours per week and start dates.
- `to_ics(results)` runs `build_ics` on the parser output.

### Heatmap

- `events` in the response, or `to_event_inputs(results)` in Python, give `EventInput`
  dicts. `start` is the due date and time, so each item lands in its due week.
- Class meetings can be added with `to_event_inputs(results, term, include_classes=True)`
  (type `"class"`). They're off by default because each one adds a point to the week.

### Frontend

- `review_rows` already works with `api.row_to_deadline`.
- Extra fields on each row: `needs_review`, `note` (e.g. "only the week is known"),
  `due_time`, `estimated_hours`, `confidence`, `date_source`.
- `analysis.suggested_starts` has the same keys as `logic.suggested_starts()`.
- `courses[].warnings` has syllabus problems, e.g. "Midterm is Oct 24 on page 3 but
  Oct 31 on page 5".
- `GET /api/parse/status` says whether the server has an API key.

## What happened when the parser ran with the other branches

All results below are from merging the current branches into one folder and running the
parser against them.

### Analytics: no problems

- 3 of 3 analytics tests in `tests/test_integration.py` pass: `Deadline`, `score_weeks`,
  `find_collisions` and `build_ics` all accept the parser output.
- The analytics branch's own 13 tests still pass with the parser in the same folder.

### Heatmap: 2 problems

1. **`POST /api/heatmap/calculate` returns 404.** The route in `endpoints.py` is
   registered at `/api/heatmap/api/heatmap/calculate` (the router prefix and the route
   path both include `/api/heatmap`).
2. **The registered route returns 500 Internal Server Error.** Sent one parser event
   (`{"title": "Midterm", "start": "2027-02-24T10:10:00", "type": "exam", "weight_pct": 25}`),
   `calculate_weekly_heatmap` returns `score: 6.0` and `level: "red"`, but the response
   model `HeatmapBucket` expects an integer `score` and a `colour` field, so FastAPI
   fails while building the response.

Also seen: the heatmap files import each other as top-level modules
(`from schemas import ...`). They import from the repo root, but not from `backend/`,
which is where the parser and analytics run.

Calling `calculate_weekly_heatmap(events)` directly with parser events works: same weeks
and same scores as analytics.

### Frontend: works, 1 date problem

- A live run of `api.parse_syllabi()` against the parser with 4 real syllabi returned 63
  rows with no errors. The Review, Dashboard and collision logic in `logic.py` all ran
  on the result.
- With no API key on the server, the frontend showed the parser's 503 message.
- **Dates:** `api.parse_syllabi` sends `"breaks": []` and a term end of start + 15 weeks.
  Without the study break, MATH 1000U's "Week 10" midterm was placed in the week of
  Nov 9; with the Oct 12–16 break included it's the week of Nov 16.

### Backend: nothing to run against yet

There is no `backend/app/` in any branch, so the frontend's default `API_URL`
(`http://localhost:8000`) has no server behind it. The tests and the live run used
`parser/dev_server.py` instead.

## Testing the integration

```powershell
cd backend
pytest parser/tests/test_integration.py
```

No API key needed. Each test checks the parser output against one part of the project and
skips if that part isn't in the branch yet.
