# Semester Sentinel

[![CI](https://github.com/REPLACE_OWNER/REPLACE_REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/REPLACE_OWNER/REPLACE_REPO/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.12-blue)
![React](https://img.shields.io/badge/react-vite-informational)

Upload your syllabi and see which weeks of your semester will be the hardest, before they arrive.

**Live demo:** REPLACE_DEMO_URL

![Dashboard](docs/screenshots/dashboard.png)

## What it does

Most calendar tools list deadlines. Semester Sentinel scores each week by workload, flags stretches where several major deadlines pile up, and suggests when to start each exam or project so those stretches are less painful.

1. **Upload** 3 to 6 syllabus PDFs and name each course.
2. **Parse** assignments, quizzes, exams and projects with their dates and grade weights.
3. **Review** the extracted deadlines in a table and fix anything the parser got wrong.
4. **Analyze** the semester: weekly risk scores, collision windows, start-date suggestions.
5. **Export** the result as an `.ics` file for Google Calendar or Apple Calendar.

## How the risk score works

Each deadline earns points by type: exam 4, project 3, quiz 1.5, assignment 1. Items worth 20% or more of a course grade count 1.5 times. A week's score is the sum.

| Score | Level |
|-------|-------|
| under 4 | green |
| 4 to 7.9 | yellow |
| 8 to 11.9 | orange |
| 12 or more | red |

A collision is any 4-day window containing 3 or more exams, projects or heavily weighted items. Weeks that score 12 or more are marked as Final Boss Weeks.

Example: a Physics midterm (30%), a CS project (25%) and a Stats assignment (5%) in one week score 6 + 4.5 + 1 = 11.5, which is orange, with about 21 hours of estimated work.

## Built with

- Python 3.12, FastAPI, pdfplumber, dateparser, icalendar
- React, Vite
- pytest, GitHub Actions

## Getting started

You need Python 3.12 and Node 20 or newer.

Backend (Windows PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

On macOS or Linux, activate with `source .venv/bin/activate`. API docs are at http://127.0.0.1:8000/docs.

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

The app opens at http://localhost:5173. Click "Load demo" to try it without uploading anything.

Tests:

```powershell
cd backend
pytest
```

## Project layout

```
backend/parser/      PDF text extraction and deadline detection
backend/analytics/   risk scoring, collisions, suggestions, ICS export
backend/app/         FastAPI endpoints
frontend/            React dashboard
samples/             sample deadlines and test syllabi
docs/                data contract, screenshots
```

The shared data format is in [docs/data-contract.md](docs/data-contract.md).

## Parser accuracy

Measured on REPLACE_N real syllabi from 4 courses and 3 formats.

| Measure | Result |
|---------|--------|
| Deadlines found | REPLACE % |
| Correct date | REPLACE % |
| Correct type | REPLACE % |

## Known limitations

- Scanned PDFs without a text layer are rejected. There is no OCR.
- Syllabi that list dates without a year need the term start date entered at upload.
- Dates like "TBA" or "to be announced in class" are skipped.
- Workload hours are estimates by assignment type, not measured data.

## Team

| Name | Area |
|------|------|
| REPLACE_NAME | Parser |
| REPLACE_NAME | Backend and deployment |
| REPLACE_NAME | Frontend |
| REPLACE_NAME | Analytics |

Built for the REPLACE_CLUB_NAME project challenge, fall 2026.

## License

MIT. See [LICENSE](LICENSE).
