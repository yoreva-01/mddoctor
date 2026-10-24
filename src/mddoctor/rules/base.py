"""Rule base class and the shared context handed to every rule."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from mddoctor.documents import DocumentCache
from mddoctor.models import Diagnostic, Document, Severity

if TYPE_CHECKING:
    from mddoctor.config import Config


@dataclass
class Context:
    """Everything a rule may need besides the document being checked."""

    root: Path
    documents: DocumentCache
    config: Config


class Rule:
    """Base class for lint rules.

    Subclasses set ``code``, ``name``, ``description`` and ``severity`` and implement
    :meth:`check`. Decorate the subclass with :func:`mddoctor.rules.registry.register`.
    """

    code: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    severity: ClassVar[Severity] = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        raise NotImplementedError

    def diagnostic(self, doc: Document, line: int, column: int, message: str) -> Diagnostic:
        return Diagnostic(
            path=doc.path,
            line=line,
            column=column,
            code=self.code,
            name=self.name,
            message=message,
            severity=self.severity,
        )
