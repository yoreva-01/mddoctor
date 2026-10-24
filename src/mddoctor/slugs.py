"""GitHub-compatible heading slugs.

GitHub turns a heading into an anchor by rendering it to plain text, lower-casing it, dropping
punctuation, and replacing spaces with hyphens. Repeated headings get ``-1``, ``-2``... suffixes.
"""

from __future__ import annotations

import re

_LINK_OR_IMAGE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_REF_LINK_OR_IMAGE = re.compile(r"!?\[([^\]]*)\]\[[^\]]*\]")
_CODE_SPLIT = re.compile(r"(`+[^`]*`+)")
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
_EMPHASIS_STAR = re.compile(r"(?<!\\)\*+")
_EMPHASIS_UNDERSCORE_OPEN = re.compile(r"(?<![\w\\])_+(?=\S)")
_EMPHASIS_UNDERSCORE_CLOSE = re.compile(r"(?<=\S)_+(?![\w])")
_STRIKE = re.compile(r"(?<!\\)~~")
_DISALLOWED = re.compile(r"[^\w\- ]")


def strip_inline(text: str) -> str:
    """Remove inline Markdown (links, emphasis, code ticks, HTML tags) from heading text."""
    text = _LINK_OR_IMAGE.sub(r"\1", text)
    text = _REF_LINK_OR_IMAGE.sub(r"\1", text)
    parts = _CODE_SPLIT.split(text)
    cleaned: list[str] = []
    for index, part in enumerate(parts):
        if index % 2 == 1:  # a code span: keep the content verbatim
            cleaned.append(part.strip("`"))
            continue
        part = _HTML_TAG.sub("", part)
        part = _EMPHASIS_STAR.sub("", part)
        part = _EMPHASIS_UNDERSCORE_OPEN.sub("", part)
        part = _EMPHASIS_UNDERSCORE_CLOSE.sub("", part)
        part = _STRIKE.sub("", part)
        part = _ESCAPE.sub(r"\1", part)
        cleaned.append(part)
    return "".join(cleaned).strip()


def slugify(plain: str) -> str:
    """Convert already-plain heading text to a GitHub-style slug."""
    lowered = plain.strip().lower()
    return _DISALLOWED.sub("", lowered).replace(" ", "-")


class Slugger:
    """Generates unique slugs for the headings of one document, in document order."""

    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def slug(self, plain: str) -> str:
        base = slugify(plain)
        if not base:
            return ""
        count = self._seen.get(base)
        if count is None:
            self._seen[base] = 0
            return base
        count += 1
        self._seen[base] = count
        return f"{base}-{count}"
