"""Output formatting for lint results."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from mddoctor.engine import LintResult
from mddoctor.models import Diagnostic, Severity


def display_path(path: Path, base: Path) -> str:
    """Path relative to ``base`` when possible, always with forward slashes."""
    try:
        return path.relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def format_text(result: LintResult, base: Path) -> str:
    lines = [
        f"{display_path(d.path, base)}:{d.line}:{d.column}: "
        f"{d.severity.value} {d.code} {d.name}: {d.message}"
        for d in result.diagnostics
    ]
    errors = result.count(Severity.ERROR)
    warnings = result.count(Severity.WARNING)
    checked = _plural(result.files_checked, "file")
    if errors or warnings:
        lines.append("")
        lines.append(
            f"Checked {checked}: {_plural(errors, 'error')}, {_plural(warnings, 'warning')}"
        )
    else:
        lines.append(f"Checked {checked}: no problems found")
    return "\n".join(lines)


def _as_dict(diagnostic: Diagnostic, base: Path) -> dict[str, object]:
    return {
        "path": display_path(diagnostic.path, base),
        "line": diagnostic.line,
        "column": diagnostic.column,
        "code": diagnostic.code,
        "name": diagnostic.name,
        "severity": diagnostic.severity.value,
        "message": diagnostic.message,
    }


def format_json(result: LintResult, base: Path) -> str:
    payload = {
        "files_checked": result.files_checked,
        "summary": {
            "errors": result.count(Severity.ERROR),
            "warnings": result.count(Severity.WARNING),
        },
        "diagnostics": [_as_dict(d, base) for d in result.diagnostics],
    }
    return json.dumps(payload, indent=2)


def _escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    return _escape_data(value).replace(":", "%3A").replace(",", "%2C")


def format_github(result: LintResult, base: Path) -> str:
    """GitHub Actions workflow commands, rendered as inline annotations on pull requests."""
    lines = []
    for d in result.diagnostics:
        title = _escape_property(f"{d.code} {d.name}")
        file = _escape_property(display_path(d.path, base))
        lines.append(
            f"::{d.severity.value} file={file},line={d.line},col={d.column},title={title}"
            f"::{_escape_data(d.message)}"
        )
    return "\n".join(lines)


FORMATTERS: dict[str, Callable[[LintResult, Path], str]] = {
    "text": format_text,
    "json": format_json,
    "github": format_github,
}
