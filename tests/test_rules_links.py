"""Tests for MDD001-MDD003 (link rules)."""

from __future__ import annotations

from pathlib import Path

from mddoctor.rules.links import parse_local_target
from tests.conftest import write


def messages(diags) -> list[str]:
    return [d.message for d in diags]


def test_broken_link_reports_missing_file(run_rule) -> None:
    diags = run_rule("MDD001", "# T\n\nSee [guide](docs/guide.md).\n")
    assert len(diags) == 1
    assert (diags[0].line, diags[0].column) == (3, 5)
    assert "docs/guide.md" in diags[0].message


def test_valid_relative_links_pass(run_rule) -> None:
    files = {"docs/guide.md": "# Guide\n", "img/a.png": "x"}
    text = "[g](docs/guide.md) [i](./img/a.png) ![i](img/a.png) [d](docs)\n"
    assert run_rule("MDD001", text, files) == []


def test_external_and_special_links_are_ignored(run_rule) -> None:
    text = "[a](https://x.io) [b](mailto:a@b.c) [c](//cdn.x.io/a.js) [d](#top) [e](tel:123)\n"
    assert run_rule("MDD001", text) == []


def test_percent_encoded_and_query_are_handled(run_rule) -> None:
    files = {"my docs/a b.md": "# A\n"}
    assert run_rule("MDD001", "[x](my%20docs/a%20b.md?plain=1)\n", files) == []


def test_root_relative_link_uses_project_root(run_rule) -> None:
    files = {"docs/guide.md": "# Guide\n"}
    assert run_rule("MDD001", "[x](/docs/guide.md)\n", files) == []
    assert len(run_rule("MDD001", "[x](/docs/nope.md)\n", files)) == 1


def test_broken_image_message(run_rule) -> None:
    diags = run_rule("MDD001", "![alt](missing.png)\n")
    assert diags[0].message.startswith("Image target")


def test_reference_definition_targets_are_checked(run_rule) -> None:
    diags = run_rule("MDD001", "[a][x]\n\n[x]: ./gone.md\n")
    assert len(diags) == 1
    assert diags[0].line == 3


def test_broken_anchor_in_same_file(run_rule) -> None:
    text = "# Title\n\n## Install\n\n[ok](#install) [bad](#instal)\n"
    diags = run_rule("MDD002", text)
    assert len(diags) == 1
    assert "did you mean '#install'" in diags[0].message


def test_anchor_matching_is_case_insensitive_and_decodes(run_rule) -> None:
    text = "# Hello World\n\n[a](#Hello-World) [b](#hello%2Dworld)\n"
    assert run_rule("MDD002", text) == []


def test_anchor_in_other_markdown_file(run_rule) -> None:
    files = {"other.md": "# Other\n\n## Part One\n"}
    assert run_rule("MDD002", "[a](other.md#part-one)\n", files) == []
    diags = run_rule("MDD002", "[a](other.md#part-two)\n", files)
    assert len(diags) == 1
    assert "in 'other.md'" in diags[0].message


def test_duplicate_heading_anchor_suffix_is_valid(run_rule) -> None:
    text = "# T\n\n## Usage\n\n## Usage\n\n[x](#usage-1)\n"
    assert run_rule("MDD002", text) == []


def test_html_anchor_counts(run_rule) -> None:
    text = '# T\n\n<a name="legacy"></a>\n\n[x](#legacy)\n'
    assert run_rule("MDD002", text) == []


def test_special_fragments_and_non_markdown_targets_are_skipped(run_rule) -> None:
    files = {"code.py": "x = 1\n", "other.md": "# O\n"}
    text = "[a](#top) [b](code.py#L10) [c](other.md#L5-L9) [d](code.py#whatever)\n"
    assert run_rule("MDD002", text, files) == []


def test_anchor_to_missing_file_is_left_to_broken_link(run_rule) -> None:
    assert run_rule("MDD002", "[a](nope.md#x)\n") == []


def test_anchor_to_unreadable_file_is_skipped(run_rule, tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe\x00bad\x80")
    assert run_rule("MDD002", "[a](bad.md#x)\n") == []


def test_anchor_ignored_for_directory_target(run_rule) -> None:
    files = {"docs/a.md": "# A\n"}
    assert run_rule("MDD002", "[a](docs#whatever)\n", files) == []


def test_empty_link_destinations(run_rule) -> None:
    diags = run_rule("MDD003", "[a]() [b](#) [c](<>) [d](ok.md)\n")
    assert [d.column for d in diags] == [1, 7, 14]


def test_parse_local_target_none_for_external(tmp_path: Path) -> None:
    from mddoctor.config import Config
    from mddoctor.documents import DocumentCache
    from mddoctor.rules import Context

    doc_path = write(tmp_path, "a.md", "# A\n")
    ctx = Context(root=tmp_path, documents=DocumentCache(), config=Config(root=tmp_path))
    doc = ctx.documents.get(doc_path)
    assert parse_local_target("https://x.io", doc, ctx) is None
    assert parse_local_target("  ", doc, ctx) is None
    local = parse_local_target("sub/../b.md#frag", doc, ctx)
    assert local is not None
    assert local.path == (tmp_path / "b.md").resolve()
    assert local.fragment == "frag"
