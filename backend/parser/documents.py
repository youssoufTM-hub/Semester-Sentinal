"""Loads PDF / docx / txt uploads and pulls out plain text."""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEXT = "text/plain"

MAX_BYTES = 20 * 1024 * 1024


class DocumentError(Exception):
    pass


@dataclass
class Document:
    filename: str
    mime_type: str
    data: bytes
    text: str  # empty for scanned pdfs

    @property
    def is_pdf(self) -> bool:
        return self.mime_type == PDF


def guess_mime_type(filename: Optional[str], data: bytes) -> str:
    name = (filename or "").lower()
    if data.startswith(b"%PDF"):
        return PDF
    if data.startswith(b"PK") and (name.endswith(".docx") or not name):
        return DOCX
    if name.endswith(".txt") or name.endswith(".md"):
        return TEXT
    if name.endswith(".pdf"):
        return PDF
    if name.endswith(".docx"):
        return DOCX
    raise DocumentError(f"Unsupported file type for '{filename or 'upload'}'. Use PDF, .docx or .txt.")


def load_document(data: bytes, filename: Optional[str] = None, mime_type: Optional[str] = None) -> Document:
    if not data:
        raise DocumentError("The uploaded file is empty.")
    if len(data) > MAX_BYTES:
        raise DocumentError("The file is larger than 20 MB.")
    mime = mime_type or guess_mime_type(filename, data)
    name = filename or {PDF: "syllabus.pdf", DOCX: "syllabus.docx"}.get(mime, "syllabus.txt")

    if mime == PDF:
        if not data.startswith(b"%PDF"):
            raise DocumentError("That file is not a valid PDF.")
        return Document(name, mime, data, _pdf_text(data))
    if mime == DOCX:
        return Document(name, mime, data, _docx_text(data))
    if mime == TEXT:
        return Document(name, mime, data, data.decode("utf-8", errors="replace"))
    raise DocumentError(f"Unsupported file type: {mime}")


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [f"[page {i + 1}]\n{page.extract_text() or ''}" for i, page in enumerate(reader.pages)]
        return "\n\n".join(pages).strip()
    except Exception:
        return ""


def _docx_text(data: bytes) -> str:
    # keep tables in order, a lot of syllabi put dates in tables
    try:
        import docx
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as err:
        raise DocumentError("Word files need the python-docx package on the server.") from err
    try:
        doc = docx.Document(io.BytesIO(data))
    except Exception as err:
        raise DocumentError("That Word file could not be opened.") from err

    lines: list[str] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = Paragraph(child, doc).text.strip()
            if text:
                lines.append(text)
        elif tag == "tbl":
            for row in Table(child, doc).rows:
                cells = []
                for cell in row.cells:
                    value = " ".join(cell.text.split())
                    if not cells or cells[-1] != value:  # merged cells
                        cells.append(value)
                lines.append(" | ".join(cells))
            lines.append("")
    return "\n".join(lines).strip()
