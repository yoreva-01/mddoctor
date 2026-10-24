"""Table-of-contents generation between ``<!-- toc -->`` and ``<!-- tocstop -->`` markers."""

from __future__ import annotations

import codecs
import re
from dataclasses import dataclass
from pathlib import Path

from mddoctor.models import Document
from mddoctor.parser import parse_document

TOC_START = "<!-- toc -->"
TOC_END = "<!-- tocstop -->"
_BRACKETS = re.compile(r"([\[\]])")


class TocError(Exception):
    """Raised when a file cannot have its TOC generated or updated."""


@dataclass(frozen=True)
class TocResult:
    text: str  # the full file text with the up-to-date TOC
    changed: bool
    entries: int


def build_toc(doc: Document, min_level: int = 2, max_level: int = 3) -> list[str]:
    """Render Markdown list lines for the headings between ``min_level`` and ``max_level``."""
    marker_range = _marker_range(doc, required=False)
    lines: list[str] = []
    for heading in doc.headings:
        if not (min_level <= heading.level <= max_level) or not heading.slug:
            continue
        if marker_range and marker_range[0] <= heading.line <= marker_range[1]:
            continue
        label = _BRACKETS.sub(r"\\\1", heading.plain)
        indent = "  " * (heading.level - min_level)
        lines.append(f"{indent}- [{label}](#{heading.slug})")
    return lines


def _marker_range(doc: Document, *, required: bool) -> tuple[int, int] | None:
    """Return the 1-based line numbers of the TOC start and end markers."""
    starts = _marker_lines(doc, TOC_START)
    ends = _marker_lines(doc, TOC_END)
    if not starts and not ends and not required:
        return None
    if len(starts) != 1 or len(ends) != 1:
        raise TocError(f"expected exactly one '{TOC_START}' and one '{TOC_END}' marker")
    if ends[0] <= starts[0]:
        raise TocError(f"'{TOC_END}' must come after '{TOC_START}'")
    return starts[0], ends[0]


def _marker_lines(doc: Document, marker: str) -> list[int]:
    return [
        number
        for number, line in enumerate(doc.lines, start=1)
        if line.strip() == marker and not doc.in_fence[number - 1]
    ]


def update_toc_text(text: str, path: Path, min_level: int = 2, max_level: int = 3) -> TocResult:
    """Return ``text`` with the TOC between the markers regenerated."""
    doc = parse_document(path, text)
    marker_range = _marker_range(doc, required=True)
    assert marker_range is not None
    start, end = marker_range
    toc = build_toc(doc, min_level, max_level)
    block = ["", *toc, ""] if toc else [""]
    new_lines = doc.lines[:start] + block + doc.lines[end - 1 :]
    eol = "\r\n" if "\r\n" in text else "\n"
    new_text = eol.join(new_lines) + (eol if doc.ends_with_newline else "")
    return TocResult(text=new_text, changed=new_text != text, entries=len(toc))


def update_toc_file(path: Path, min_level: int, max_level: int, *, write: bool) -> TocResult:
    """Regenerate the TOC of ``path``; only touch the file when ``write`` is true."""
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TocError(f"{path}: not valid UTF-8 ({exc.reason})") from exc
    except OSError as exc:
        raise TocError(f"{path}: {exc.strerror or exc}") from exc
    try:
        result = update_toc_text(text, path, min_level, max_level)
    except TocError as exc:
        raise TocError(f"{path}: {exc}") from exc
    if write and result.changed:
        prefix = codecs.BOM_UTF8 if raw.startswith(codecs.BOM_UTF8) else b""
        path.write_bytes(prefix + result.text.encode("utf-8"))
    return result
