"""Text extraction for knowledge documents: PDF, DOCX, TXT, Markdown, HTML, CSV.

Every format yields `Section(page, heading, text)` blocks so chunks keep page + section
references. Uploaded files are UNTRUSTED: type is checked from magic bytes as well as the
extension, nothing is executed (no macros, no scripts, no external entities), and limits cap
pages and characters. Scanned PDFs (no text layer) are reported, not OCR'd: OCR is not
implemented, and the job fails with `no_text_layer` rather than indexing nothing silently.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser

MAX_PAGES = 600
MAX_CHARS = 3_000_000

FORMATS = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "md": "text/markdown",
    "html": "text/html",
    "csv": "text/csv",
}


class ExtractionError(ValueError):
    """Message is a stable code safe to show (e.g. 'no_text_layer')."""


@dataclass(frozen=True)
class Section:
    page: int | None
    heading: str | None
    text: str


def detect_format(filename: str, data: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    ext = {"htm": "html", "markdown": "md"}.get(ext, ext)
    if ext not in FORMATS:
        raise ExtractionError("unsupported_format")
    if ext == "pdf" and not data.startswith(b"%PDF-"):
        raise ExtractionError("content_does_not_match_extension")
    if ext == "docx" and not data.startswith(b"PK\x03\x04"):
        raise ExtractionError("content_does_not_match_extension")
    if ext in ("txt", "md", "html", "csv") and b"\x00" in data[:4096]:
        raise ExtractionError("content_does_not_match_extension")
    return ext


def clean(text: str) -> str:
    """Normalise unicode, re-join words hyphenated across lines, drop control characters."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


_HEADING = re.compile(
    r"^(?:#{1,4}\s+(.+)"  # markdown heading
    r"|(\d+(?:\.\d+){0,3}\.?\s+[A-Z][^.!?]{2,80})"  # numbered heading "3.2 Irrigation"
    r"|([A-Z][A-Z \-&,]{4,80}))$"  # ALL CAPS line
)


def _split_headings(page: int | None, text: str) -> list[Section]:
    """Split plain text into sections at heading-like lines (markdown #, numbered, ALL CAPS)."""
    out: list[Section] = []
    heading: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        m = _HEADING.match(stripped) if len(stripped) <= 90 else None
        if m:
            if buf and "".join(buf).strip():
                out.append(Section(page, heading, "\n".join(buf).strip()))
            heading = (m.group(1) or m.group(2) or m.group(3)).strip().rstrip(".")[:200]
            buf = []
        else:
            buf.append(line)
    if "".join(buf).strip():
        out.append(Section(page, heading, "\n".join(buf).strip()))
    return out


def _pdf(data: bytes) -> list[Section]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise ExtractionError("encrypted_pdf")
    if len(reader.pages) > MAX_PAGES:
        raise ExtractionError("too_many_pages")
    out: list[Section] = []
    for i, page in enumerate(reader.pages, start=1):
        text = clean(page.extract_text() or "")
        if text:
            out.extend(_split_headings(i, text))
    if not out:
        raise ExtractionError("no_text_layer")  # scanned PDF: OCR not implemented
    return out


def _docx(data: bytes) -> list[Section]:
    import docx

    with zipfile.ZipFile(io.BytesIO(data)) as z:  # zip-bomb guard before parsing
        if sum(i.file_size for i in z.infolist()) > 200 * 1024 * 1024:
            raise ExtractionError("archive_too_large")
    document = docx.Document(io.BytesIO(data))
    out: list[Section] = []
    heading: str | None = None
    buf: list[str] = []
    for p in document.paragraphs:
        style = (p.style.name or "").lower() if p.style is not None else ""
        if style.startswith("heading") or style == "title":
            if buf:
                out.append(Section(None, heading, clean("\n\n".join(buf))))
            heading, buf = p.text.strip()[:200] or None, []
        elif p.text.strip():
            buf.append(p.text)
    if buf:
        out.append(Section(None, heading, clean("\n\n".join(buf))))
    for t_i, table in enumerate(document.tables, start=1):
        rows = [" | ".join(c.text.strip() for c in r.cells) for r in table.rows]
        if rows:
            out.append(Section(None, f"Table {t_i}", clean("\n".join(rows))))
    return out


class _HTMLText(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg", "nav", "footer", "header"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[Section] = []
        self.heading: str | None = None
        self.buf: list[str] = []
        self.skip = 0
        self.in_h = False
        self.h_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self.skip += 1
        elif tag in ("h1", "h2", "h3"):
            self.flush()
            self.in_h, self.h_buf = True, []
        elif tag in ("p", "li", "br", "tr", "div"):
            self.buf.append("\n\n" if tag == "p" else "\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in ("h1", "h2", "h3") and self.in_h:
            self.in_h = False
            self.heading = " ".join("".join(self.h_buf).split())[:200] or None
        elif tag in ("td", "th"):
            self.buf.append(" | ")

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        (self.h_buf if self.in_h else self.buf).append(data)

    def flush(self) -> None:
        text = clean("".join(self.buf))
        if text:
            self.sections.append(Section(None, self.heading, text))
        self.buf = []


def _html(data: bytes) -> list[Section]:
    parser = _HTMLText()
    parser.feed(_decode(data))
    parser.flush()
    return parser.sections


def _csv(data: bytes) -> list[Section]:
    rows = list(csv.reader(io.StringIO(_decode(data))))
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    lines = ["; ".join(f"{h}: {v}" for h, v in zip(header, r, strict=False) if v) for r in body]
    # One section per 40 rows so each chunk keeps the column names (table-aware).
    return [
        Section(None, f"Rows {i + 1}-{min(i + 40, len(lines))}", "\n".join(lines[i : i + 40]))
        for i in range(0, len(lines), 40)
    ]


def extract(fmt: str, data: bytes) -> list[Section]:
    if fmt == "pdf":
        sections = _pdf(data)
    elif fmt == "docx":
        sections = _docx(data)
    elif fmt == "html":
        sections = _html(data)
    elif fmt == "csv":
        sections = _csv(data)
    else:  # txt, md
        sections = _split_headings(None, clean(_decode(data)))
    if sum(len(s.text) for s in sections) > MAX_CHARS:
        raise ExtractionError("document_too_long")
    if not sections:
        raise ExtractionError("no_text_found")
    return sections


def detect_language(text: str) -> str:
    """'ur' when Arabic-script letters dominate, else 'en'. (Urdu uses the Arabic block.)"""
    letters = [c for c in text[:4000] if c.isalpha()]
    if not letters:
        return "en"
    arabic = sum(1 for c in letters if "؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ")
    return "ur" if arabic / len(letters) > 0.3 else "en"
