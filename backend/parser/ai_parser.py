"""Send a syllabus to the configured AI provider and get back a validated `ParseResult`.

The parser does not care which AI reads the syllabus: it hands a `Document`, the
instructions in `prompts.py` and a JSON schema to whatever provider
`providers.get_provider()` returns (Gemini by default), then validates the JSON
that comes back.
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

from pydantic import ValidationError

from .documents import Document, DocumentError, load_document
from .models import ParseResult, TermContext, parse_iso_date, parse_result_json_schema
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .providers import AIProvider, ProviderError, get_provider

log = logging.getLogger(__name__)


class ParserError(Exception):
    """The syllabus could not be parsed. The message is safe to show the student."""


@dataclass
class SyllabusInput:
    data: bytes
    filename: Optional[str] = None
    course_hint: Optional[str] = None
    mime_type: Optional[str] = None  # guessed from the bytes/filename when omitted


class SyllabusParser:
    def __init__(
        self,
        provider: Optional[AIProvider] = None,
        retries: int = 1,
        transient_retries: int = 3,
        backoff_seconds: float = 5.0,
    ):
        try:
            self.provider = provider or get_provider()
        except ProviderError as err:
            raise ParserError(str(err)) from err
        self.retries = retries  # extra attempts when the JSON is malformed
        self.transient_retries = transient_retries  # extra attempts on 429/5xx
        self.backoff_seconds = backoff_seconds
        self._schema = parse_result_json_schema()

    def parse(
        self,
        syllabus: SyllabusInput,
        term: Optional[TermContext] = None,
        extra_context: Optional[str] = None,
    ) -> ParseResult:
        try:
            document = load_document(syllabus.data, syllabus.filename, syllabus.mime_type)
        except DocumentError as err:
            raise ParserError(str(err)) from err

        prompt = build_user_prompt(syllabus.course_hint, _term_block(term), extra_context)
        result = self._ask(document, prompt)

        if syllabus.course_hint and not result.course.code and not result.course.name:
            result.course.name = syllabus.course_hint
        return check_result(result, term)

    def parse_many(
        self,
        syllabi: list[SyllabusInput],
        term: Optional[TermContext] = None,
        max_workers: int = 4,
    ) -> list[ParseResult | ParserError]:
        """Parse several syllabi at once. Failures come back in place as ParserError
        so one bad upload does not lose the others."""
        def one(s: SyllabusInput):
            try:
                return self.parse(s, term)
            except ParserError as err:
                return err

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            return list(pool.map(one, syllabi))

    def _call_provider(self, document: Document, prompt: str) -> str:
        """Retry temporary failures (overloaded / rate limited) with backoff."""
        delay = self.backoff_seconds
        for attempt in range(self.transient_retries + 1):
            try:
                return self.provider.generate_json(document, SYSTEM_PROMPT, prompt, self._schema)
            except ProviderError as err:
                if not err.retryable or attempt == self.transient_retries:
                    raise ParserError(str(err)) from err
                log.warning("%s: %s; retrying in %.0fs", self.provider.name, err, delay)
                time.sleep(delay)
                delay *= 2
        raise AssertionError("unreachable")

    def _ask(self, document: Document, prompt: str) -> ParseResult:
        """Call the provider; retry once if the JSON comes back malformed."""
        last_error: Exception | None = None
        for _ in range(self.retries + 1):
            text = self._call_provider(document, prompt)
            try:
                return ParseResult.model_validate(json.loads(text))
            except (json.JSONDecodeError, ValidationError) as err:
                log.warning("%s returned JSON that does not match ParseResult: %s", self.provider.name, err)
                last_error = err
        raise ParserError("The AI result was malformed. Try again.") from last_error


def _term_block(term: Optional[TermContext]) -> Optional[str]:
    if term is None:
        return None
    lines = []
    if term.term_name:
        lines.append(f"- Term: {term.term_name}")
    if term.start:
        lines.append(f"- First day of classes: {term.start}")
    if term.end:
        lines.append(f"- Last day of term/exams: {term.end}")
    for b in term.breaks:
        lines.append(f"- No classes ({b.name}): {b.start} to {b.end}")
    return "\n".join(lines) or None


def check_result(result: ParseResult, term: Optional[TermContext] = None) -> ParseResult:
    """Sanity checks on what the model returned. These do not change the model's
    reading of the syllabus; they only flag rows the student should look at."""
    start = parse_iso_date((term.start if term else None) or result.course.term_start)
    end = parse_iso_date((term.end if term else None) or result.course.term_end)

    for d in result.deadlines:
        if d.due_date is not None and parse_iso_date(d.due_date) is None:
            d.note = f"Unreadable date '{d.due_date}'. " + (d.note or "")
            d.due_date = None
            d.needs_review = True
        due = parse_iso_date(d.due_date)
        if due and ((start and due < start) or (end and due > end)):
            d.needs_review = True
            d.note = ((d.note or "") + " Date falls outside the term.").strip()
        if due is None:
            d.needs_review = True

    total = sum(c.weight_pct for c in result.grading_scheme)
    if result.grading_scheme and abs(total - 100) > 0.5:
        msg = f"Grade components add up to {total:g}%, not 100%."
        if msg not in result.warnings:
            result.warnings.append(msg)
    return result
