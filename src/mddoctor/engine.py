"""The lint engine: run enabled rules over files and post-process their diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from mddoctor.config import Config
from mddoctor.documents import DocumentCache, DocumentLoadError
from mddoctor.models import Diagnostic, Severity
from mddoctor.rules import Context, Rule, all_rules
from mddoctor.suppress import Suppressions

READ_ERROR_CODE = "MDD000"
READ_ERROR_NAME = "read-error"


@dataclass
class LintResult:
    diagnostics: list[Diagnostic]
    files_checked: int

    def count(self, severity: Severity) -> int:
        return sum(1 for d in self.diagnostics if d.severity is severity)

    def failed(self, strict: bool = False) -> bool:
        """Errors always fail; warnings fail only in strict mode."""
        if self.count(Severity.ERROR):
            return True
        return strict and bool(self.count(Severity.WARNING))


def lint_files(
    files: Sequence[Path],
    config: Config,
    cache: DocumentCache | None = None,
    rules: Sequence[Rule] | None = None,
) -> LintResult:
    """Lint ``files`` with every rule enabled by ``config``."""
    cache = cache or DocumentCache()
    active = [r for r in (rules if rules is not None else all_rules()) if config.is_enabled(r.code)]
    ctx = Context(root=config.root, documents=cache, config=config)
    diagnostics: list[Diagnostic] = []

    for file in files:
        try:
            doc = cache.get(file)
        except DocumentLoadError as exc:
            diagnostics.append(
                Diagnostic(
                    path=exc.path,
                    line=1,
                    column=1,
                    code=READ_ERROR_CODE,
                    name=READ_ERROR_NAME,
                    message=f"Cannot read file: {exc.reason}",
                    severity=Severity.ERROR,
                )
            )
            continue
        suppressions = Suppressions.from_document(doc)
        for rule in active:
            for diagnostic in rule.check(doc, ctx):
                if suppressions.is_suppressed(diagnostic.code, diagnostic.line):
                    continue
                severity = config.severity_for(diagnostic.code, diagnostic.severity)
                diagnostics.append(replace(diagnostic, severity=severity))

    diagnostics.sort(key=Diagnostic.sort_key)
    return LintResult(diagnostics=diagnostics, files_checked=len(files))
