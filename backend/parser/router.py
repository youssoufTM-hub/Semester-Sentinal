"""Parser endpoints.

Integration (backend, app/main.py):
    from parser.router import router as parser_router
    app.include_router(parser_router)

Integration (frontend): frontend/api.py parse_syllabi() posts to /api/parse/syllabi
and reads "review_rows" and "errors" from the response.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from .convert import to_deadline_rows, to_event_inputs, to_review_rows
from .integration import analytics_available, analyze
from .models import ParseResult, TermContext
from .syllabus_parser import ParserError, SyllabusInput, SyllabusParser

router = APIRouter(prefix="/api/parse", tags=["parser"])

MAX_FILES = 8

_parser: Optional[SyllabusParser] = None


def get_parser() -> SyllabusParser:
    global _parser
    if _parser is None:
        try:
            _parser = SyllabusParser()
        except ParserError as err:
            raise HTTPException(503, f"Parser is not set up: {err}")
    return _parser


@router.get("/status")
def status():
    try:
        p = get_parser()
    except HTTPException as err:
        return {"ready": False, "error": err.detail}
    return {"ready": True, "provider": p.provider.name, "model": p.provider.model}


@router.post("/syllabi")
async def parse_syllabi(
    files: list[UploadFile] = File(..., description="3 to 6 syllabi (PDF, .docx or .txt)"),
    course_names: Optional[str] = Form(None, description="JSON list of names, same order as files"),
    term: Optional[str] = Form(None, description="JSON TermContext: {start, end, term_name, breaks}"),
):
    if not 1 <= len(files) <= MAX_FILES:
        raise HTTPException(400, f"Upload between 1 and {MAX_FILES} syllabi.")
    try:
        names = json.loads(course_names) if course_names else []
        term_ctx = TermContext.model_validate_json(term) if term else None
    except ValueError as err:
        raise HTTPException(400, f"Bad form field: {err}")

    inputs = []
    for i, f in enumerate(files):
        inputs.append(SyllabusInput(
            data=await f.read(),
            filename=f.filename,
            course_hint=names[i] if i < len(names) else None,
        ))

    parser = get_parser()
    # all files at once so 6 syllabi still finish inside the frontend's 180s timeout
    outcomes = await run_in_threadpool(parser.parse_many, inputs, term_ctx, len(inputs))
    parsed: list[ParseResult] = []
    errors = []
    for f, outcome in zip(files, outcomes):
        if isinstance(outcome, ParserError):
            errors.append({"file": f.filename, "error": str(outcome)})
        else:
            parsed.append(outcome)

    if not parsed:
        raise HTTPException(422, {"message": "No syllabus could be parsed.", "errors": errors})

    return {
        "courses": [r.model_dump() for r in parsed],
        "review_rows": to_review_rows(parsed),
        # Integration (analytics): same fields as analytics.models.Deadline, due as YYYY-MM-DD
        "deadlines": [
            {**row, "due": row["due"].isoformat()} for row in to_deadline_rows(parsed)
        ],
        # Integration (heatmap): POST this list to the heatmap endpoint as is
        "events": to_event_inputs(parsed, term_ctx),
        # Integration (analytics): weekly scores, collisions, hours, start dates.
        # null until backend/analytics is merged in.
        "analysis": analyze(parsed) if analytics_available() else None,
        "errors": errors,
    }
