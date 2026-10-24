"""Core data models shared by the parser, rules, engine, and reporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from pathlib import Path


class Severity(Enum):
    """How serious a diagnostic is. Errors always fail a run; warnings only with ``--strict``."""

    ERROR = "error"
    WARNING = "warning"

    @classmethod
    def parse(cls, value: str) -> Severity:
        try:
            return cls(value.strip().lower())
        except ValueError:
            valid = ", ".join(s.value for s in cls)
            raise ValueError(f"invalid severity {value!r} (expected one of: {valid})") from None


@dataclass(frozen=True)
class Diagnostic:
    """A single problem found in a Markdown file. Lines and columns are 1-based."""

    path: Path
    line: int
    column: int
    code: str
    name: str
    message: str
    severity: Severity

    def sort_key(self) -> tuple[str, int, int, str]:
        return (self.path.as_posix(), self.line, self.column, self.code)


@dataclass(frozen=True)
class Heading:
    level: int
    text: str  # raw heading text, without the leading/closing ``#`` markers
    plain: str  # text with inline Markdown removed
    slug: str  # GitHub-style anchor, unique within the document ("" for empty headings)
    line: int


@dataclass(frozen=True)
class Link:
    """A link destination found in the document (inline link, image, or reference definition)."""

    target: str
    line: int
    column: int
    is_image: bool = False
    kind: str = "inline"  # "inline" or "definition"


@dataclass(frozen=True)
class RefDefinition:
    label: str  # normalised (case-folded, whitespace-collapsed)
    raw_label: str
    target: str
    line: int
    column: int


@dataclass(frozen=True)
class RefUse:
    label: str  # normalised
    raw_label: str
    line: int
    column: int
    explicit: bool  # True for ``[text][label]`` / ``[label][]``; False for shortcut ``[label]``


@dataclass(frozen=True)
class Fence:
    line: int
    marker: str  # "`" or "~"
    length: int
    info: str
    closed: bool
    end_line: int


@dataclass
class Document:
    """A parsed Markdown file.

    ``lines`` are the raw lines (without line endings). ``masked`` has the same length but
    fenced code, inline code spans, and HTML comments are blanked out, so rules can scan it
    for Markdown syntax without false positives. Column positions are preserved.
    """

    path: Path
    text: str
    lines: list[str]
    masked: list[str]
    in_fence: list[bool]
    comments: dict[int, str]  # 1-based line -> HTML comment text found on that line
    headings: list[Heading] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    ref_definitions: list[RefDefinition] = field(default_factory=list)
    ref_uses: list[RefUse] = field(default_factory=list)
    fences: list[Fence] = field(default_factory=list)
    html_anchors: set[str] = field(default_factory=set)
    ends_with_newline: bool = True

    @cached_property
    def anchors(self) -> frozenset[str]:
        """Every fragment a link may legally target in this document (lower-cased)."""
        slugs = {h.slug.lower() for h in self.headings if h.slug}
        return frozenset(slugs | {a.lower() for a in self.html_anchors})
