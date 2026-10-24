"""Heading structure rules."""

from __future__ import annotations

from collections.abc import Iterator

from mddoctor.models import Diagnostic, Document, Severity
from mddoctor.rules.base import Context, Rule
from mddoctor.rules.registry import register


@register
class HeadingIncrement(Rule):
    code = "MDD010"
    name = "heading-increment"
    description = "Heading levels should increase by one at a time (no jump from H2 to H4)."
    severity = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        previous = 0
        for heading in doc.headings:
            if previous and heading.level > previous + 1:
                yield self.diagnostic(
                    doc,
                    heading.line,
                    1,
                    f"Heading level jumps from H{previous} to H{heading.level}",
                )
            previous = heading.level


@register
class MultipleH1(Rule):
    code = "MDD011"
    name = "multiple-h1"
    description = "A document should have a single top-level heading."
    severity = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        h1s = [h for h in doc.headings if h.level == 1]
        for heading in h1s[1:]:
            yield self.diagnostic(
                doc,
                heading.line,
                1,
                f"Multiple top-level headings (first H1 is on line {h1s[0].line})",
            )


@register
class MissingH1(Rule):
    code = "MDD012"
    name = "missing-h1"
    description = "A non-empty document should contain a top-level heading."
    severity = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        if doc.text.strip() and not any(h.level == 1 for h in doc.headings):
            yield self.diagnostic(doc, 1, 1, "Document has no top-level (H1) heading")


@register
class DuplicateHeading(Rule):
    code = "MDD013"
    name = "duplicate-heading"
    description = "Sibling headings under the same parent should have distinct text."
    severity = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        stack: list[tuple[int, str]] = []
        seen: dict[tuple[tuple[str, ...], int, str], int] = {}
        for heading in doc.headings:
            while stack and stack[-1][0] >= heading.level:
                stack.pop()
            key = heading.plain.casefold()
            parents = tuple(text for _, text in stack)
            if key:
                identity = (parents, heading.level, key)
                if identity in seen:
                    yield self.diagnostic(
                        doc,
                        heading.line,
                        1,
                        f"Duplicate heading '{heading.plain}' (first on line {seen[identity]})",
                    )
                else:
                    seen[identity] = heading.line
            stack.append((heading.level, key))


@register
class EmptyHeading(Rule):
    code = "MDD014"
    name = "empty-heading"
    description = "Headings must contain text."
    severity = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        for heading in doc.headings:
            if not heading.plain:
                yield self.diagnostic(doc, heading.line, 1, "Heading is empty")
