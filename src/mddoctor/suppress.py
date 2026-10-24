"""Inline suppression comments.

Supported directives (each is an HTML comment on its own or at the end of a line)::

    <!-- mddoctor-disable-file [RULE ...] -->
    <!-- mddoctor-disable-next-line [RULE ...] -->
    <!-- mddoctor-disable [RULE ...] -->   ...   <!-- mddoctor-enable [RULE ...] -->

``RULE`` is a rule code (``MDD001``) or name (``broken-link``). With no rules, a directive
applies to all rules. Directives inside code blocks or code spans are ignored.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from mddoctor.models import Document
from mddoctor.rules import resolve_rule_id

ALL = "*"
_DIRECTIVE = re.compile(
    r"<!--\s*mddoctor-(?P<kind>disable-file|disable-next-line|disable|enable)"
    r"(?P<args>(?:\s+[A-Za-z0-9_-]+)*)\s*-->"
)


def _tokens(args: str) -> set[str]:
    names = args.split()
    if not names:
        return {ALL}
    return {resolve_rule_id(name) or name.lower() for name in names}


@dataclass
class Suppressions:
    """Which diagnostics are silenced in one document."""

    file_wide: set[str] = field(default_factory=set)
    next_line: dict[int, set[str]] = field(default_factory=dict)
    ranges: list[tuple[str, int, int]] = field(default_factory=list)  # (token, first, last)

    @classmethod
    def from_document(cls, doc: Document) -> Suppressions:
        result = cls()
        open_ranges: dict[str, int] = {}
        for lineno in sorted(doc.comments):
            for match in _DIRECTIVE.finditer(doc.comments[lineno]):
                kind = match.group("kind")
                tokens = _tokens(match.group("args"))
                if kind == "disable-file":
                    result.file_wide |= tokens
                elif kind == "disable-next-line":
                    result.next_line.setdefault(lineno + 1, set()).update(tokens)
                elif kind == "disable":
                    for token in tokens:
                        open_ranges.setdefault(token, lineno)
                else:  # enable
                    to_close = set(open_ranges) if ALL in tokens else tokens & set(open_ranges)
                    for token in to_close:
                        result.ranges.append((token, open_ranges.pop(token), lineno))
        for token, start in open_ranges.items():
            result.ranges.append((token, start, sys.maxsize))
        return result

    def is_suppressed(self, code: str, line: int) -> bool:
        if code in self.file_wide or ALL in self.file_wide:
            return True
        if self.next_line.get(line, set()) & {code, ALL}:
            return True
        return any(
            token in (code, ALL) and first <= line <= last for token, first, last in self.ranges
        )
