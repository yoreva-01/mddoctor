"""Whitespace hygiene rules."""

from __future__ import annotations

from collections.abc import Iterator

from mddoctor.models import Diagnostic, Document, Severity
from mddoctor.rules.base import Context, Rule
from mddoctor.rules.registry import register


@register
class TrailingWhitespace(Rule):
    code = "MDD040"
    name = "trailing-whitespace"
    description = (
        "Lines should not end with spaces or tabs (exactly two spaces, a hard break, is OK)."
    )
    severity = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        for index, line in enumerate(doc.lines):
            if doc.in_fence[index]:
                continue
            stripped = line.rstrip(" \t")
            trailing = line[len(stripped) :]
            if not trailing:
                continue
            if trailing == "  " and stripped:
                continue  # Markdown hard line break
            yield self.diagnostic(
                doc, index + 1, len(stripped) + 1, f"Trailing whitespace ({len(trailing)} chars)"
            )

    def fix(self, doc: Document, suppressions: object | None = None) -> str | None:
        lines = list(doc.lines)
        changed = False
        for index, line in enumerate(lines):
            if doc.in_fence[index]:
                continue
            if suppressions is not None and getattr(suppressions, "is_suppressed", None):
                if suppressions.is_suppressed(self.code, index + 1):
                    continue
            stripped = line.rstrip(" \t")
            trailing = line[len(stripped) :]
            if not trailing:
                continue
            if trailing == "  " and stripped:
                continue
            lines[index] = stripped
            changed = True
        if not changed:
            return None
        eol = "\r\n" if "\r\n" in doc.text else "\n"
        return eol.join(lines) + (eol if doc.ends_with_newline else "")


@register
class HardTab(Rule):
    code = "MDD041"
    name = "hard-tab"
    description = "Use spaces, not tab characters, outside code blocks."
    severity = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        for index, line in enumerate(doc.lines):
            if not doc.in_fence[index] and "\t" in line:
                yield self.diagnostic(
                    doc, index + 1, line.index("\t") + 1, "Hard tab character found"
                )

    def fix(self, doc: Document, suppressions: object | None = None) -> str | None:
        lines = list(doc.lines)
        changed = False
        for index, line in enumerate(lines):
            if doc.in_fence[index] or "\t" not in line:
                continue
            if suppressions is not None and getattr(suppressions, "is_suppressed", None):
                if suppressions.is_suppressed(self.code, index + 1):
                    continue
            lines[index] = line.replace("\t", "    ")
            changed = True
        if not changed:
            return None
        eol = "\r\n" if "\r\n" in doc.text else "\n"
        return eol.join(lines) + (eol if doc.ends_with_newline else "")


@register
class FinalNewline(Rule):
    code = "MDD042"
    name = "final-newline"
    description = "Files should end with exactly one newline."
    severity = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        if not doc.lines:
            return
        last = len(doc.lines)
        if not doc.ends_with_newline:
            yield self.diagnostic(
                doc, last, len(doc.lines[-1]) + 1, "File does not end with a newline"
            )
        elif not doc.lines[-1].strip():
            yield self.diagnostic(doc, last, 1, "File ends with extra blank lines")

    def fix(self, doc: Document, suppressions: object | None = None) -> str | None:
        if suppressions is not None and getattr(suppressions, "is_suppressed", None):
            if suppressions.is_suppressed(self.code, len(doc.lines) or 1):
                return None
        lines = list(doc.lines)
        if not lines:
            return None
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            # Blank-only file: clear it so the next check is clean.
            return ""
        eol = "\r\n" if "\r\n" in doc.text else "\n"
        return eol.join(lines) + eol
