"""Tests for inline suppression and the engine."""

from __future__ import annotations

from pathlib import Path

from mddoctor.config import Config
from mddoctor.documents import DocumentCache
from mddoctor.engine import READ_ERROR_CODE, lint_files
from mddoctor.models import Severity
from mddoctor.parser import parse_document
from mddoctor.suppress import Suppressions
from tests.conftest import write


def suppressions(text: str) -> Suppressions:
    return Suppressions.from_document(parse_document(Path("d.md"), text))


def test_disable_next_line() -> None:
    sup = suppressions(
        "a\n<!-- mddoctor-disable-next-line MDD001 -->\n[x](nope.md)\n[y](nope.md)\n"
    )
    assert sup.is_suppressed("MDD001", 3)
    assert not sup.is_suppressed("MDD001", 4)
    assert not sup.is_suppressed("MDD002", 3)


def test_disable_next_line_by_name_and_all() -> None:
    sup = suppressions(
        "<!-- mddoctor-disable-next-line broken-link -->\nx\n"
        "<!-- mddoctor-disable-next-line -->\ny\n"
    )
    assert sup.is_suppressed("MDD001", 2)
    assert sup.is_suppressed("MDD999", 4)


def test_disable_enable_range() -> None:
    sup = suppressions(
        "a\n<!-- mddoctor-disable MDD040 -->\nb\nc\n<!-- mddoctor-enable MDD040 -->\nd\n"
    )
    assert not sup.is_suppressed("MDD040", 1)
    assert sup.is_suppressed("MDD040", 3)
    assert sup.is_suppressed("MDD040", 4)
    assert not sup.is_suppressed("MDD040", 6)


def test_disable_without_enable_runs_to_end_of_file() -> None:
    sup = suppressions("<!-- mddoctor-disable MDD040 -->\nx\ny\n")
    assert sup.is_suppressed("MDD040", 3)


def test_enable_without_args_closes_everything() -> None:
    sup = suppressions("<!-- mddoctor-disable MDD040 MDD041 -->\nx\n<!-- mddoctor-enable -->\ny\n")
    assert sup.is_suppressed("MDD041", 2)
    assert not sup.is_suppressed("MDD040", 4)


def test_disable_file() -> None:
    sup = suppressions("x\ny\n<!-- mddoctor-disable-file MDD021 -->\n")
    assert sup.is_suppressed("MDD021", 1)
    assert not sup.is_suppressed("MDD001", 1)
    assert suppressions("<!-- mddoctor-disable-file -->\n").is_suppressed("MDD001", 99)


def test_directives_in_code_are_ignored() -> None:
    text = "```md\n<!-- mddoctor-disable-file -->\n```\n\n`<!-- mddoctor-disable-file -->`\n"
    sup = suppressions(text)
    assert not sup.is_suppressed("MDD001", 1)


def test_engine_reports_sorted_diagnostics_and_files_checked(tmp_path: Path) -> None:
    a = write(tmp_path, "a.md", "# A\n\n[x](gone.md)\n")
    b = write(tmp_path, "b.md", "# B\ntrailing \n")
    result = lint_files([b, a], Config(root=tmp_path))
    assert result.files_checked == 2
    assert [(d.path.name, d.code) for d in result.diagnostics] == [
        ("a.md", "MDD001"),
        ("b.md", "MDD040"),
    ]


def test_engine_honours_select_ignore_and_severity(tmp_path: Path) -> None:
    path = write(tmp_path, "a.md", "# A\n\n[x](gone.md)\ntrailing \n")
    only = Config(root=tmp_path, select=frozenset({"MDD001"}))
    assert [d.code for d in lint_files([path], only).diagnostics] == ["MDD001"]
    ignoring = Config(root=tmp_path, ignore=frozenset({"MDD001"}))
    assert [d.code for d in lint_files([path], ignoring).diagnostics] == ["MDD040"]
    demoted = Config(root=tmp_path, severity={"MDD001": Severity.WARNING})
    result = lint_files([path], demoted)
    assert result.count(Severity.ERROR) == 0
    assert not result.failed()
    assert result.failed(strict=True)


def test_engine_applies_suppressions(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "a.md",
        "# A\n\n<!-- mddoctor-disable-next-line MDD001 -->\n[x](gone.md)\n[y](gone2.md)\n",
    )
    result = lint_files([path], Config(root=tmp_path))
    assert [d.line for d in result.diagnostics] == [5]


def test_engine_reports_unreadable_files(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"\xff\xfe\x00\x80broken")
    result = lint_files([bad], Config(root=tmp_path))
    assert [d.code for d in result.diagnostics] == [READ_ERROR_CODE]
    assert result.failed()
    assert "UTF-8" in result.diagnostics[0].message


def test_engine_reuses_cache_between_files(tmp_path: Path) -> None:
    a = write(tmp_path, "a.md", "# A\n\n[x](b.md#nope)\n")
    b = write(tmp_path, "b.md", "# B\n")
    cache = DocumentCache()
    result = lint_files([a, b], Config(root=tmp_path), cache=cache)
    assert [d.code for d in result.diagnostics] == ["MDD002"]
    assert cache.get(b) is cache.get(b)


def test_clean_run_does_not_fail(tmp_path: Path) -> None:
    path = write(tmp_path, "a.md", "# A\n\nAll good.\n")
    result = lint_files([path], Config(root=tmp_path))
    assert result.diagnostics == []
    assert not result.failed(strict=True)
