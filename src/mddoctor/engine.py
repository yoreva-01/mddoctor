"""The lint engine: run enabled rules over files and post-process their diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from mddoctor.config import Config
from mddoctor.documents import DocumentCache, DocumentLoadError
from mddoctor.models import Diagnostic, Severity
from mddoctor.parser import parse_document
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


@dataclass
class FixResult:
    path: Path
    changed: bool
    fixes_applied: int = 0


def apply_fixes(
    files: Sequence[Path],
    config: Config,
    cache: DocumentCache | None = None,
    rules: Sequence[Rule] | None = None,
) -> list[FixResult]:
    """Apply every rule's ``fix`` hook and rewrite files that changed (preserve CRLF/BOM)."""
    import codecs

    cache = cache or DocumentCache()
    active = [r for r in (rules if rules is not None else all_rules()) if config.is_enabled(r.code)]
    results: list[FixResult] = []

    for file in files:
        try:
            raw = file.read_bytes()
            text = raw.decode("utf-8-sig")
        except (OSError, UnicodeDecodeError):
            results.append(FixResult(path=file, changed=False))
            continue
        doc = cache.get(file)
        suppressions = Suppressions.from_document(doc)
        current = text
        fixes_applied = 0
        for rule in active:
            doc = parse_document(file, current)
            suppressions = Suppressions.from_document(doc)
            fixed = rule.fix(doc, suppressions)
            if fixed is not None:
                current = fixed
                fixes_applied += 1
        if current == text:
            results.append(FixResult(path=file, changed=False))
            continue
        prefix = codecs.BOM_UTF8 if raw.startswith(codecs.BOM_UTF8) else b""
        file.write_bytes(prefix + current.encode("utf-8"))
        results.append(FixResult(path=file, changed=True, fixes_applied=fixes_applied))
    return results
