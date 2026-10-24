"""Reference-style link rules."""

from __future__ import annotations

from collections.abc import Iterator

from mddoctor.models import Diagnostic, Document, Severity
from mddoctor.rules.base import Context, Rule
from mddoctor.rules.registry import register


@register
class UndefinedReference(Rule):
    code = "MDD030"
    name = "undefined-reference"
    description = "A reference link [text][label] uses a label that has no definition."
    severity = Severity.ERROR

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        defined = {d.label for d in doc.ref_definitions}
        for use in doc.ref_uses:
            # Shortcut references ``[text]`` are ordinary brackets unless a definition exists.
            if use.explicit and use.label not in defined:
                yield self.diagnostic(
                    doc,
                    use.line,
                    use.column,
                    f"Reference '[{use.raw_label}]' has no definition",
                )


@register
class UnusedDefinition(Rule):
    code = "MDD031"
    name = "unused-definition"
    description = "A reference definition is never used."
    severity = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        used = {u.label for u in doc.ref_uses}
        for definition in doc.ref_definitions:
            if definition.label not in used:
                yield self.diagnostic(
                    doc,
                    definition.line,
                    1,
                    f"Reference definition '[{definition.raw_label}]' is never used",
                )


@register
class DuplicateDefinition(Rule):
    code = "MDD032"
    name = "duplicate-definition"
    description = "The same reference label is defined more than once (only the first counts)."
    severity = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        first_seen: dict[str, int] = {}
        for definition in doc.ref_definitions:
            if definition.label in first_seen:
                yield self.diagnostic(
                    doc,
                    definition.line,
                    1,
                    f"Reference '[{definition.raw_label}]' is already defined on "
                    f"line {first_seen[definition.label]}",
                )
            else:
                first_seen[definition.label] = definition.line
