"""Tests for output formatters."""

from __future__ import annotations

import json
from pathlib import Path

from mddoctor.engine import LintResult
from mddoctor.models import Diagnostic, Severity
from mddoctor.reporters import FORMATTERS, display_path, format_github, format_json, format_text


def make(base: Path) -> LintResult:
    return LintResult(
        diagnostics=[
            Diagnostic(
                path=base / "docs" / "a.md",
                line=3,
                column=5,
                code="MDD001",
                name="broken-link",
                message="Link target 'x.md' does not exist",
                severity=Severity.ERROR,
            ),
            Diagnostic(
                path=base / "docs" / "a.md",
                line=9,
                column=1,
                code="MDD040",
                name="trailing-whitespace",
                message="Trailing whitespace (1 chars)",
                severity=Severity.WARNING,
            ),
        ],
        files_checked=2,
    )


def test_text_format(tmp_path: Path) -> None:
    base = tmp_path.resolve()
    output = format_text(make(base), base)
    assert output.splitlines()[0] == (
        "docs/a.md:3:5: error MDD001 broken-link: Link target 'x.md' does not exist"
    )
    assert output.splitlines()[1].startswith("docs/a.md:9:1: warning MDD040 trailing-whitespace")
    assert output.splitlines()[-1] == "Checked 2 files: 1 error, 1 warning"


def test_text_format_clean_run(tmp_path: Path) -> None:
    clean = LintResult(diagnostics=[], files_checked=1)
    assert format_text(clean, tmp_path) == "Checked 1 file: no problems found"


def test_json_format(tmp_path: Path) -> None:
    base = tmp_path.resolve()
    payload = json.loads(format_json(make(base), base))
    assert payload["files_checked"] == 2
    assert payload["summary"] == {"errors": 1, "warnings": 1}
    first = payload["diagnostics"][0]
    assert first == {
        "path": "docs/a.md",
        "line": 3,
        "column": 5,
        "code": "MDD001",
        "name": "broken-link",
        "severity": "error",
        "message": "Link target 'x.md' does not exist",
    }


def test_github_format_escapes_special_characters(tmp_path: Path) -> None:
    base = tmp_path.resolve()
    result = make(base)
    result.diagnostics[0] = Diagnostic(
        path=base / "a,b.md",
        line=1,
        column=1,
        code="MDD001",
        name="broken-link",
        message="100% bad\nnewline",
        severity=Severity.ERROR,
    )
    lines = format_github(result, base).splitlines()
    assert lines[0] == (
        "::error file=a%2Cb.md,line=1,col=1,title=MDD001 broken-link::100%25 bad%0Anewline"
    )
    assert lines[1].startswith("::warning file=docs/a.md,line=9,col=1,")


def test_display_path_outside_base(tmp_path: Path) -> None:
    other = tmp_path / "x" / "a.md"
    assert display_path(other, tmp_path / "elsewhere") == other.as_posix()


def test_formatters_registry() -> None:
    assert set(FORMATTERS) == {"text", "json", "github"}
