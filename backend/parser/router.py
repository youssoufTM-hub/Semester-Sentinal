"""Parser endpoints. Mount with app.include_router(router) in app/main.py."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .syllabus_parser import ParserError, SyllabusInput, SyllabusParser
from .convert import to_event_inputs, to_review_rows
from .models import ParseResult, TermContext

router = APIRouter(prefix="/api/parse", tags=["parser"])

_parser: Optional[SyllabusParser] = None


def get_parser() -> SyllabusParser:
    global _parser
    if _parser is None:
        _parser = SyllabusParser()
    return _parser


@router.post("/syllabi")
async def parse_syllabi(
    files: list[UploadFile] = File(..., description="3 to 6 syllabi (PDF, .docx or .txt)"),
    course_names: Optional[str] = Form(None, description="JSON list of names, same order as files"),
    term: Optional[str] = Form(None, description="JSON TermContext: {start, end, term_name, breaks}"),
):
    if not 1 <= len(files) <= 8:
        raise HTTPException(400, "Upload between 1 and 8 syllabi.")
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

    outcomes = get_parser().parse_many(inputs, term_ctx)
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
        "events": to_event_inputs(parsed, term_ctx),
        "errors": errors,
    }
