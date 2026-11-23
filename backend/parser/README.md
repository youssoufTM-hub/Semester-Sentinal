# Parser

Reads a syllabus (PDF, .docx or .txt) and pulls out every graded item with its date,
weight and type, plus class times and the grading scheme. Uses Gemini by default.

Output plugs straight into the rest of the backend:

- `to_deadline_rows()` -> `analytics.models.Deadline(**row)`
- `to_event_inputs()` -> heatmap `EventInput`
- `to_review_rows()` -> rows for the frontend review table

## Setup

```powershell
cd backend
pip install -r parser/requirements.txt
copy parser\parser_config.example.json parser\parser_config.json
```

Put your API key in `parser_config.json`. The file is in `.gitignore`, so don't
worry about committing it by accident.

```json
{
  "provider": "gemini",
  "providers": {
    "gemini": { "api_key": "YOUR-KEY", "model": "gemini-3.5-flash", "fallback_models": ["gemini-3.5-flash-lite"] },
    "openai": { "api_key": "", "model": "gpt-5-mini", "base_url": "" }
  }
}
```

`openai` works with anything that has an OpenAI-style API. Set `base_url` for
OpenRouter (`https://openrouter.ai/api/v1`) or Ollama (`http://localhost:11434/v1`,
no key needed).

Environment variables override the file: `PARSER_PROVIDER`, `PARSER_MODEL`,
`GEMINI_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`.

## Running it

```powershell
python -m parser "outline.pdf" "other.docx" --term-start 2026-09-08 --term-end 2026-12-19 --break "Fall Study Break:2026-10-12:2026-10-16"
```

From code:

```python
from parser import SyllabusParser, SyllabusInput, TermContext

result = SyllabusParser().parse(
    SyllabusInput(open("outline.pdf", "rb").read(), filename="outline.pdf"),
    TermContext(start="2026-09-08", end="2026-12-19"),
)
```

API: add `app.include_router(parser_router)` (from `parser.router`) in `app/main.py`.
`POST /api/parse/syllabi` takes `files`, plus optional `course_names` (JSON list)
and `term` (JSON). It returns `{courses, review_rows, events, errors}`.

## How dates are handled

- Relative dates like "Week 7" are worked out from the term start and the break weeks.
- If only the week is known, the item goes on the first class of that week and is
  marked `needs_review`.
- TBA and registrar-scheduled dates stay `null`.
- Rows with dates outside the term, and grading schemes that don't add up to 100%,
  get flagged.

## Accuracy

Tested on 4 Fall 2026 Ontario Tech outlines (`eval/expected/`): CSCI 1062U (.docx),
BUSI 1700, MATH 1000U and PHY 1030U.

| Measure | Result |
|---------|--------|
| Deadlines found | 100% (32/32) |
| Correct date | 100% |
| Correct type | 100% |

```powershell
python -m parser.eval "path\to\syllabi" --term-start 2026-09-08 --term-end 2026-12-19
```

## Testing with your own syllabus

`inputs/` has a sample syllabus (MATH 1000U, Fall 2026) and `term.json` with the term
dates. To test yours, drop the .pdf / .docx / .txt into `inputs/`, update `term.json`
if it's a different term, and run:

```powershell
cd backend
pytest parser/tests -s
```

`-s` prints every deadline found in each file. The parsing tests call the API, so set
up `parser_config.json` first. Without a key they fail with `NoAPIKeyError`. If an
answer file in `eval/expected/` matches the syllabus name, the results are also checked
against it.
