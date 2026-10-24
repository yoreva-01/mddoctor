"""End-to-end tests for the command-line interface."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from mddoctor import __version__
from mddoctor.cli import main
from tests.conftest import write

GOOD = "# Project\n\nSee [guide](docs/guide.md#setup).\n"
GUIDE = "# Guide\n\n## Setup\n\nDone.\n"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_check_clean_project(project: Path, capsys) -> None:
    write(project, "README.md", GOOD)
    write(project, "docs/guide.md", GUIDE)
    code, out, _ = run(capsys, "check")
    assert code == 0
    assert out.strip() == "Checked 2 files: no problems found"


def test_check_reports_problems_and_exit_code(project: Path, capsys) -> None:
    write(project, "README.md", "# Project\n\n[x](docs/missing.md)\n")
    code, out, _ = run(capsys, "check", "README.md")
    assert code == 1
    assert "README.md:3:1: error MDD001 broken-link" in out
    assert out.strip().endswith("Checked 1 file: 1 error, 0 warnings")


def test_warnings_pass_unless_strict(project: Path, capsys) -> None:
    write(project, "README.md", "# Project\n\ntrailing \n")
    assert run(capsys, "check")[0] == 0
    assert run(capsys, "check", "--strict")[0] == 1


def test_json_format(project: Path, capsys) -> None:
    write(project, "README.md", "# Project\n\n[x](nope.md)\n")
    code, out, _ = run(capsys, "check", "--format", "json")
    payload = json.loads(out)
    assert code == 1
    assert payload["summary"] == {"errors": 1, "warnings": 0}
    assert payload["diagnostics"][0]["code"] == "MDD001"


def test_github_format(project: Path, capsys) -> None:
    write(project, "README.md", "# Project\n\n[x](nope.md)\n")
    code, out, _ = run(capsys, "check", "--format", "github")
    assert code == 1
    assert out.startswith("::error file=README.md,line=3,col=1,title=MDD001 broken-link::")


def test_select_and_ignore_options(project: Path, capsys) -> None:
    write(project, "README.md", "# Project\n\n[x](nope.md)\ntrailing \n")
    _, out, _ = run(capsys, "check", "--select", "MDD040", "--strict")
    assert "MDD040" in out
    assert "MDD001" not in out
    code, out, _ = run(capsys, "check", "--ignore", "broken-link,trailing-whitespace")
    assert code == 0
    assert "no problems" in out


def test_unknown_rule_is_usage_error(project: Path, capsys) -> None:
    write(project, "README.md", GOOD)
    code, _, err = run(capsys, "check", "--select", "MDD999")
    assert code == 2
    assert "unknown rule 'MDD999'" in err


def test_missing_path_is_usage_error(project: Path, capsys) -> None:
    code, _, err = run(capsys, "check", "nope")
    assert code == 2
    assert "does not exist" in err


def test_no_files_found_is_ok(project: Path, capsys) -> None:
    code, out, err = run(capsys, "check")
    assert code == 0
    assert out == ""
    assert "no Markdown files found" in err


def test_config_file_is_discovered(project: Path, capsys) -> None:
    write(project, ".mddoctor.toml", 'ignore = ["MDD001"]\nexclude = ["skipped"]\n')
    write(project, "README.md", "# Project\n\n[x](nope.md)\n")
    write(project, "skipped/bad.md", "no heading [y](gone.md)\n")
    code, out, _ = run(capsys, "check")
    assert code == 0
    assert "Checked 1 file" in out


def test_invalid_config_is_usage_error(project: Path, capsys) -> None:
    write(project, ".mddoctor.toml", "bogus = 1\n")
    write(project, "README.md", GOOD)
    code, _, err = run(capsys, "check")
    assert code == 2
    assert "unknown option" in err


def test_explicit_config_option(project: Path, capsys) -> None:
    write(project, "custom.toml", 'ignore = ["MDD001"]\n')
    write(project, "README.md", "# Project\n\n[x](nope.md)\n")
    assert run(capsys, "check", "--config", "custom.toml")[0] == 0
    code, _, err = run(capsys, "check", "--config", "absent.toml")
    assert code == 2
    assert "not found" in err


def test_toc_print(project: Path, capsys) -> None:
    write(project, "README.md", "# T\n\n## One\n\n### Two\n")
    code, out, _ = run(capsys, "toc", "README.md")
    assert code == 0
    assert out.splitlines() == ["- [One](#one)", "  - [Two](#two)"]


def test_toc_print_options_and_errors(project: Path, capsys) -> None:
    write(project, "README.md", "# T\n\n## One\n\n### Two\n")
    write(project, "B.md", "# B\n")
    _, out, _ = run(capsys, "toc", "README.md", "--min-level", "3", "--max-level", "3")
    assert out.splitlines() == ["- [Two](#two)"]
    assert run(capsys, "toc", "README.md", "B.md")[0] == 2
    code, _, err = run(capsys, "toc", "README.md", "--min-level", "3", "--max-level", "2")
    assert code == 2
    assert "must not exceed" in err
    code, _, err = run(capsys, "toc", "missing.md")
    assert code == 2
    assert "missing.md" in err


def test_toc_write_then_check(project: Path, capsys) -> None:
    write(project, "README.md", "# T\n\n<!-- toc -->\n<!-- tocstop -->\n\n## One\n")
    code, out, _ = run(capsys, "toc", "README.md", "--check")
    assert code == 1
    assert "out of date" in out
    code, out, _ = run(capsys, "toc", "README.md", "--write")
    assert code == 0
    assert out.strip() == "README.md: updated (1 entries)"
    assert "- [One](#one)" in (project / "README.md").read_text(encoding="utf-8")
    code, out, _ = run(capsys, "toc", "README.md", "--check")
    assert (code, out.strip()) == (0, "README.md: table of contents is up to date")
    _, out, _ = run(capsys, "toc", "README.md", "--write")
    assert "already up to date" in out


def test_toc_without_markers_fails(project: Path, capsys) -> None:
    write(project, "README.md", "# T\n\n## One\n")
    code, _, err = run(capsys, "toc", "README.md", "--write")
    assert code == 2
    assert "marker" in err


def test_toc_write_and_check_are_mutually_exclusive(project: Path, capsys) -> None:
    write(project, "README.md", "# T\n")
    with pytest.raises(SystemExit) as info:
        main(["toc", "README.md", "--write", "--check"])
    assert info.value.code == 2


def test_rules_command_lists_every_rule(project: Path, capsys) -> None:
    code, out, _ = run(capsys, "rules")
    assert code == 0
    assert "MDD001  error" in out
    assert "broken-anchor" in out
    assert len(out.strip().splitlines()) >= 14


def test_version_and_missing_command(capsys) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0
    assert f"mddoctor {__version__}" in capsys.readouterr().out
    with pytest.raises(SystemExit) as info:
        main([])
    assert info.value.code == 2


def test_module_entry_point(tmp_path: Path) -> None:
    write(tmp_path, "a.md", "# A\n\n[x](gone.md)\n")
    completed = subprocess.run(
        [sys.executable, "-m", "mddoctor", "check", "a.md"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "MDD001" in completed.stdout


def test_nearest_config_wins_over_parent_excludes(project: Path, capsys, monkeypatch) -> None:
    write(project, ".mddoctor.toml", 'exclude = ["sub/*"]\n')
    write(project, "sub/.mddoctor.toml", "")
    write(project, "sub/a.md", "# A\n\n[x](gone.md)\n")
    monkeypatch.chdir(project / "sub")
    code, out, _ = run(capsys, "check")
    assert code == 1
    assert "MDD001" in out


def test_check_fix_trailing_whitespace_and_tabs(project: Path, capsys) -> None:
    write(project, "README.md", "# Title   \n\nfoo\tbar\n")
    code, out, err = run(capsys, "check", "--fix")
    assert "Applied" in out or "fixed:" in err
    text = (project / "README.md").read_text(encoding="utf-8")
    assert text == "# Title\n\nfoo    bar\n"
    # re-lint is clean
    code, out, _ = run(capsys, "check")
    assert code == 0


def test_check_fix_final_newline(project: Path, capsys) -> None:
    write(project, "README.md", "# Title\n\n\n")
    run(capsys, "check", "--fix")
    text = (project / "README.md").read_text(encoding="utf-8")
    assert text == "# Title\n"

def test_check_fix_preserves_crlf_and_bom(project: Path, capsys) -> None:
    bom = b"\xef\xbb\xbf"
    (project / "README.md").write_bytes(bom + b"# Title   \r\n\r\nok\r\n")
    run(capsys, "check", "--fix")
    raw = (project / "README.md").read_bytes()
    assert raw.startswith(bom)
    assert b"\r\n" in raw and b"# Title\r\n" in raw


def test_check_fix_is_idempotent(project: Path, capsys) -> None:
    write(project, "README.md", "# Title   \n\nfoo\tbar\n")
    run(capsys, "check", "--fix")
    first = (project / "README.md").read_bytes()
    run(capsys, "check", "--fix")
    assert (project / "README.md").read_bytes() == first


def test_check_fix_skips_fenced_code(project: Path, capsys) -> None:
    write(project, "README.md", "# T\n\n```\nkeep   \n```\n")
    run(capsys, "check", "--fix")
    text = (project / "README.md").read_text(encoding="utf-8")
    assert "keep   " in text


def test_check_fix_honours_suppressions(project: Path, capsys) -> None:
    write(project, "README.md", "<!-- mddoctor-disable MDD040 -->\n# T   \n<!-- mddoctor-enable MDD040 -->\n")
    run(capsys, "check", "--fix")
    text = (project / "README.md").read_text(encoding="utf-8")
    assert "# T   " in text


def test_check_fix_blank_only_file(project: Path, capsys) -> None:
    write(project, "README.md", "\n\n\n")
    run(capsys, "check", "--fix")
    assert (project / "README.md").read_text(encoding="utf-8") == ""


def test_check_fix_json_is_valid_json(project: Path, capsys) -> None:
    write(project, "README.md", "# Title   \n")
    code, out, _ = run(capsys, "check", "--fix", "--format", "json")
    import json
    json.loads(out)
