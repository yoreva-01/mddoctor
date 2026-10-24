"""Fenced code block rules."""

from __future__ import annotations

from collections.abc import Iterator

from mddoctor.models import Diagnostic, Document, Severity
from mddoctor.rules.base import Context, Rule
from mddoctor.rules.registry import register


@register
class UnclosedFence(Rule):
    code = "MDD020"
    name = "unclosed-fence"
    description = "A fenced code block is opened but never closed, swallowing the rest of the file."
    severity = Severity.ERROR

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        for fence in doc.fences:
            if not fence.closed:
                marker = fence.marker * fence.length
                yield self.diagnostic(doc, fence.line, 1, f"Code fence '{marker}' is never closed")


@register
class FenceLanguage(Rule):
    code = "MDD021"
    name = "fence-language"
    description = "Fenced code blocks should declare a language (use 'text' for plain output)."
    severity = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        for fence in doc.fences:
            if not fence.info:
                yield self.diagnostic(
                    doc, fence.line, 1, "Fenced code block has no language specified"
                )
