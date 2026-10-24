"""Tests for heading, fence, reference, and whitespace rules."""

from __future__ import annotations


def lines(diags) -> list[int]:
    return [d.line for d in diags]


# --- headings -----------------------------------------------------------------


def test_heading_increment(run_rule) -> None:
    diags = run_rule("MDD010", "# A\n\n#### Deep\n\n## Back\n\n#### Deep2\n")
    assert lines(diags) == [3, 7]
    assert "H1 to H4" in diags[0].message


def test_heading_increment_allows_decreases(run_rule) -> None:
    assert run_rule("MDD010", "# A\n## B\n### C\n# D\n") == []


def test_multiple_h1(run_rule) -> None:
    diags = run_rule("MDD011", "# A\n\n# B\n\n# C\n")
    assert lines(diags) == [3, 5]
    assert "line 1" in diags[0].message


def test_missing_h1(run_rule) -> None:
    assert lines(run_rule("MDD012", "text\n\n## Only sub\n")) == [1]
    assert run_rule("MDD012", "# Ok\n") == []
    assert run_rule("MDD012", "") == []
    assert run_rule("MDD012", "\n\n") == []


def test_duplicate_headings_only_among_siblings(run_rule) -> None:
    text = "# T\n\n## A\n\n### Usage\n\n## B\n\n### Usage\n\n### Usage\n"
    diags = run_rule("MDD013", text)
    assert lines(diags) == [11]
    assert "first on line 9" in diags[0].message


def test_duplicate_headings_are_case_insensitive(run_rule) -> None:
    assert lines(run_rule("MDD013", "# T\n## Usage\n## usage\n")) == [3]


def test_empty_heading(run_rule) -> None:
    assert lines(run_rule("MDD014", "# T\n\n##\n\n### ###\n")) == [3, 5]


# --- fences -------------------------------------------------------------------


def test_unclosed_fence(run_rule) -> None:
    diags = run_rule("MDD020", "# T\n\n```python\nx = 1\n")
    assert lines(diags) == [3]
    assert "```" in diags[0].message


def test_closed_fence_is_fine(run_rule) -> None:
    assert run_rule("MDD020", "```py\nx\n```\n") == []


def test_fence_language(run_rule) -> None:
    text = "```\nno lang\n```\n\n```text\nplain\n```\n\n~~~\nx\n~~~\n"
    assert lines(run_rule("MDD021", text)) == [1, 9]


# --- references ---------------------------------------------------------------


def test_undefined_reference(run_rule) -> None:
    text = "See [text][nope] and [ok][ref] and [ref][] and [shortcut].\n\n[ref]: x.md\n"
    diags = run_rule("MDD030", text)
    assert len(diags) == 1
    assert "[nope]" in diags[0].message


def test_collapsed_reference_to_missing_label(run_rule) -> None:
    assert len(run_rule("MDD030", "See [missing][].\n")) == 1


def test_unused_definition(run_rule) -> None:
    text = "[a][one] [two]\n\n[one]: a.md\n[two]: b.md\n[three]: c.md\n"
    diags = run_rule("MDD031", text)
    assert lines(diags) == [5]


def test_image_reference_counts_as_use(run_rule) -> None:
    assert run_rule("MDD031", "![alt][logo]\n\n[logo]: logo.png\n") == []


def test_duplicate_definition(run_rule) -> None:
    diags = run_rule("MDD032", "[a]: x.md\n[A]: y.md\n")
    assert lines(diags) == [2]
    assert "line 1" in diags[0].message


# --- whitespace ---------------------------------------------------------------


def test_trailing_whitespace(run_rule) -> None:
    text = "ok\nbad \nworse\t\nhard break  \n   \n"
    diags = run_rule("MDD040", text)
    assert lines(diags) == [2, 3, 5]
    assert diags[0].column == 4


def test_trailing_whitespace_inside_fence_is_ignored(run_rule) -> None:
    assert run_rule("MDD040", "```text\nspaces   \n```\n") == []


def test_trailing_whitespace_handles_crlf(run_rule) -> None:
    assert run_rule("MDD040", "line\r\nnext\r\n") == []


def test_hard_tab(run_rule) -> None:
    diags = run_rule("MDD041", "ok\n\tindented\n```\n\tcode\n```\n")
    assert [(d.line, d.column) for d in diags] == [(2, 1)]


def test_final_newline(run_rule) -> None:
    assert run_rule("MDD042", "# T\n") == []
    assert run_rule("MDD042", "") == []
    missing = run_rule("MDD042", "# T")
    assert "does not end" in missing[0].message
    extra = run_rule("MDD042", "# T\n\n\n")
    assert "extra blank" in extra[0].message
    assert extra[0].line == 3
