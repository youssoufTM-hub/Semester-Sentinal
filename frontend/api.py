"""All calls to the backend live here.

Route used (feat/ai-parser branch):
    POST {API_URL}/api/parse/syllabi
        files        : 3 to 6 files (PDF, .docx or .txt)
        course_names : JSON list of names, in the same order as the files
        term         : JSON {start, end, term_name, breaks}
    Response: {"courses": [...], "review_rows": [...], "events": [...], "errors": [...]}

The server address is set with the API_URL environment variable
(default: http://localhost:8000).
"""
import json
import os
from datetime import timedelta

import requests

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT_SECONDS = 180  # the parser calls an AI model: it can take a while


class ApiError(Exception):
    """A readable error to show with st.error."""


def row_to_deadline(row):
    """Parser review_rows -> frontend format (same as Analytics)."""
    return {
        "course": row.get("course"),
        "title": row.get("title"),
        "kind": row.get("kind"),
        "due": row.get("due_date"),       # may be empty: to fill in on the Review tab
        "weight": row.get("weight_pct") or 0,
    }


def parse_syllabi(files, course_names, term_start):
    """Sends the syllabi to the parser. Returns (deadlines, errors per file)."""
    term = {
        "start": term_start.isoformat(),
        "end": (term_start + timedelta(weeks=15)).isoformat(),
        "term_name": "",
        "breaks": [],
    }

    # One ("files", (name, content, type)) entry per uploaded file
    multipart = []
    for f in files:
        multipart.append(("files", (f.name, f.getvalue(), f.type or "application/octet-stream")))
    data = {"course_names": json.dumps(course_names), "term": json.dumps(term)}

    try:
        resp = requests.post(API_URL + "/api/parse/syllabi", files=multipart, data=data, timeout=TIMEOUT_SECONDS)
    except requests.ConnectionError:
        raise ApiError("Server offline (" + API_URL + "). Use \"Load demo\" for now.")
    except requests.Timeout:
        raise ApiError("The server took too long to respond.")

    if resp.status_code == 422:
        raise ApiError("No syllabus could be read (scanned PDF?). Details: " + resp.text[:300])
    if not resp.ok:
        raise ApiError("Server error (" + str(resp.status_code) + "): " + resp.text[:200])

    body = resp.json()
    deadlines = []
    for row in body.get("review_rows", []):
        deadlines.append(row_to_deadline(row))
    return deadlines, body.get("errors", [])
