# Parser

Reads a syllabus (PDF, .docx or .txt) and pulls out every graded item with its date,
weight and type, plus class times and the grading scheme. Uses Gemini by default.

Output plugs straight into the rest of the backend:

- `to_deadline_rows()` -> `analytics.models.Deadline(**row)`
- `to_event_inputs()` -> heatmap `EventInput`
- `to_review_rows()` -> rows for the frontend review table

## Setup

Everyone uses their own API key, kept on their own computer. Keys never go on GitHub.

### 1. Install the packages

```powershell
cd backend
pip install -r parser/requirements.txt
```

### 2. Get a Gemini API key (free)

1. Go to https://aistudio.google.com/apikey and sign in with a Google account.
2. Click **Create API key**.
3. Copy the key (it starts with `AIza`).

Get your own instead of sharing one. The free tier has rate limits, and a shared key
runs out fast.

### 3. Add the key

**Option A: config file (recommended)**

From the `backend` folder, make your own copy of the example file:

```powershell
copy parser\parser_config.example.json parser\parser_config.json
```

Open `parser\parser_config.json` and paste your key between the quotes after `"api_key"`
under `gemini`:

```json
{
  "provider": "gemini",
  "providers": {
    "gemini": { "api_key": "PASTE-YOUR-KEY-HERE", "model": "gemini-3.5-flash", "fallback_models": ["gemini-3.5-flash-lite"] },
    "openai": { "api_key": "", "model": "gpt-5-mini", "base_url": "" }
  }
}
```

Important:
- Put the key in `parser_config.json`, **not** in `parser_config.example.json`. The
  parser never reads the example file, and that file is committed, so a key in it
  would end up on GitHub.
- `parser_config.json` is in `.gitignore`, so it stays on your machine. Check with
  `git status`: it should not show up.

**Option B: environment variable**

For the current terminal only:

```powershell
$env:GEMINI_API_KEY = "PASTE-YOUR-KEY-HERE"
```

Saved permanently (open a new terminal afterwards):

```powershell
setx GEMINI_API_KEY "PASTE-YOUR-KEY-HERE"
```

Environment variables override the config file. The full list: `PARSER_PROVIDER`,
`PARSER_MODEL`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and
`PARSER_CONFIG` (path to a config file somewhere else).

### 4. Check that it works

```powershell
pytest parser/tests -s
```

If the key is missing you'll see `NoAPIKeyError: No API key configured for "gemini"`.
That means the key isn't in `parser\parser_config.json` and isn't set as an
environment variable.

### Using a different provider

Set `"provider"` to `"openai"` and fill in the `openai` block. It works with anything
that has an OpenAI-style API:

| Service | `base_url` | key |
|---|---|---|
| OpenAI | leave blank | OpenAI key |
| OpenRouter (many models, one key) | `https://openrouter.ai/api/v1` | OpenRouter key |
| Ollama (runs locally, free) | `http://localhost:11434/v1` | none needed |

### Deploying

On the server (Render, Railway, etc.), don't upload a config file. Set `GEMINI_API_KEY`
in the host's environment variable settings. For GitHub Actions, add it under the repo's
**Settings → Secrets and variables → Actions** as `GEMINI_API_KEY`.

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
