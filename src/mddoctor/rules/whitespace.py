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
