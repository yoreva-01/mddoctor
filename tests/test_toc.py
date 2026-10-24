"""Tests for TOC generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from mddoctor.parser import parse_document
from mddoctor.toc import TocError, build_toc, update_toc_file, update_toc_text
from tests.conftest import write

DOC = """\
# Title

<!-- toc -->

<!-- tocstop -->

## Install

### From PyPI

### From `source`

## Usage [beta]

#### Too deep
"""


def test_build_toc_levels_and_indentation() -> None:
    doc = parse_document(Path("d.md"), DOC)
    assert build_toc(doc) == [
        "- [Install](#install)",
        "  - [From PyPI](#from-pypi)",
        "  - [From source](#from-source)",
        "- [Usage \\[beta\\]](#usage-beta)",
    ]
    assert build_toc(doc, min_level=1, max_level=2) == [
        "- [Title](#title)",
        "  - [Install](#install)",
        "  - [Usage \\[beta\\]](#usage-beta)",
    ]


def test_update_inserts_toc_between_markers() -> None:
    result = update_toc_text(DOC, Path("d.md"))
    assert result.changed
    assert result.entries == 4
    assert result.text.splitlines()[2:10] == [
        "<!-- toc -->",
        "",
        "- [Install](#install)",
        "  - [From PyPI](#from-pypi)",
        "  - [From source](#from-source)",
        "- [Usage \\[beta\\]](#usage-beta)",
        "",
        "<!-- tocstop -->",
    ]


def test_update_is_idempotent() -> None:
    once = update_toc_text(DOC, Path("d.md"))
    twice = update_toc_text(once.text, Path("d.md"))
    assert not twice.changed
    assert twice.text == once.text


def test_toc_does_not_list_itself_when_placed_under_a_heading() -> None:
    text = "# T\n\n## Contents\n\n<!-- toc -->\n<!-- tocstop -->\n\n## A\n"
    result = update_toc_text(text, Path("d.md"), min_level=2, max_level=2)
    assert "- [Contents](#contents)" in result.text
    assert "- [A](#a)" in result.text


def test_empty_toc_leaves_single_blank_line() -> None:
    result = update_toc_text("# T\n\n<!-- toc -->\n<!-- tocstop -->\n", Path("d.md"))
    assert result.text == "# T\n\n<!-- toc -->\n\n<!-- tocstop -->\n"
    assert result.entries == 0


def test_crlf_and_missing_final_newline_are_preserved() -> None:
    text = "# T\r\n<!-- toc -->\r\n<!-- tocstop -->\r\n## A\r\ntext"
    result = update_toc_text(text, Path("d.md"))
    assert (
        result.text
        == "# T\r\n<!-- toc -->\r\n\r\n- [A](#a)\r\n\r\n<!-- tocstop -->\r\n## A\r\ntext"
    )


@pytest.mark.parametrize(
    "text",
    [
        "# T\n## A\n",
        "# T\n<!-- toc -->\n## A\n",
        "# T\n<!-- tocstop -->\n<!-- toc -->\n",
        "<!-- toc -->\n<!-- toc -->\n<!-- tocstop -->\n",
    ],
)
def test_update_requires_well_formed_markers(text: str) -> None:
    with pytest.raises(TocError):
        update_toc_text(text, Path("d.md"))


def test_markers_inside_code_fences_are_ignored() -> None:
    text = "# T\n\n```md\n<!-- toc -->\n<!-- tocstop -->\n```\n"
    with pytest.raises(TocError):
        update_toc_text(text, Path("d.md"))


def test_update_file_write_and_dry_run(tmp_path: Path) -> None:
    path = write(tmp_path, "d.md", DOC)
    dry = update_toc_file(path, 2, 3, write=False)
    assert dry.changed
    assert path.read_text(encoding="utf-8") == DOC
    done = update_toc_file(path, 2, 3, write=True)
    assert done.changed
    assert "- [Install](#install)" in path.read_text(encoding="utf-8")
    assert not update_toc_file(path, 2, 3, write=True).changed


def test_update_file_preserves_bom(tmp_path: Path) -> None:
    path = tmp_path / "d.md"
    path.write_bytes(b"\xef\xbb\xbf" + DOC.encode("utf-8"))
    update_toc_file(path, 2, 3, write=True)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_update_file_errors(tmp_path: Path) -> None:
    with pytest.raises(TocError, match="No such file|cannot find"):
        update_toc_file(tmp_path / "missing.md", 2, 3, write=False)
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"\xff\xfe\x80")
    with pytest.raises(TocError, match="UTF-8"):
        update_toc_file(bad, 2, 3, write=False)
    no_markers = write(tmp_path, "n.md", "# T\n")
    with pytest.raises(TocError, match="n.md"):
        update_toc_file(no_markers, 2, 3, write=False)
