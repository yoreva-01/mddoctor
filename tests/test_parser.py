"""Tests for the Markdown parser."""

from pathlib import Path

from mddoctor.parser import mask_code_spans, normalize_label, parse_document, split_comments


def parse(text: str):
    return parse_document(Path("doc.md"), text)


def test_headings_levels_text_and_slugs() -> None:
    doc = parse("# Title\n\n## Sub `code`\n\n### Deep ###\n#hashtag\n####### seven\n")
    assert [(h.level, h.text, h.slug, h.line) for h in doc.headings] == [
        (1, "Title", "title", 1),
        (2, "Sub `code`", "sub-code", 3),
        (3, "Deep", "deep", 5),
    ]


def test_duplicate_heading_slugs_get_suffixes() -> None:
    doc = parse("# A\n## Usage\n## Usage\n")
    assert [h.slug for h in doc.headings] == ["a", "usage", "usage-1"]


def test_empty_heading_has_empty_slug() -> None:
    doc = parse("#\n## ##\n")
    assert [(h.level, h.text, h.slug) for h in doc.headings] == [(1, "", ""), (2, "", "")]


def test_fenced_code_is_masked_and_ignored() -> None:
    doc = parse("# T\n\n```md\n# not a heading\n[x](nope.md)\n```\n\n[ok](ok.md)\n")
    assert [h.text for h in doc.headings] == ["T"]
    assert [link.target for link in doc.links] == ["ok.md"]
    assert doc.in_fence == [False, False, True, True, True, True, False, False]
    assert doc.fences[0].info == "md"
    assert doc.fences[0].closed
    assert doc.fences[0].end_line == 6


def test_tilde_fence_and_longer_closing_fence() -> None:
    doc = parse("~~~python\ncode\n~~~~\nafter\n")
    assert doc.fences[0].closed
    assert doc.fences[0].marker == "~"


def test_shorter_closing_fence_does_not_close() -> None:
    doc = parse("````\ncode\n```\nstill code\n")
    assert not doc.fences[0].closed
    assert doc.fences[0].end_line == 4


def test_mismatched_marker_does_not_close() -> None:
    doc = parse("```\ncode\n~~~\n")
    assert not doc.fences[0].closed


def test_inline_triple_backticks_are_not_a_fence() -> None:
    doc = parse("```not a fence```\n")
    assert doc.fences == []


def test_unclosed_fence_is_reported_with_start_line() -> None:
    doc = parse("text\n\n```js\nconst x = 1;\n")
    assert len(doc.fences) == 1
    assert doc.fences[0].line == 3
    assert not doc.fences[0].closed


def test_inline_links_images_and_titles() -> None:
    doc = parse("See [a](a.md), ![img](pic.png \"Title\") and [c](<c d.md> 't').\n")
    assert [(link.target, link.is_image) for link in doc.links] == [
        ("a.md", False),
        ("pic.png", True),
        ("c d.md", False),
    ]
    assert doc.links[0].column == 5


def test_nested_badge_link_yields_both_links() -> None:
    doc = parse("[![CI](https://x.io/b.svg)](https://x.io/ci)\n")
    assert sorted(link.target for link in doc.links) == ["https://x.io/b.svg", "https://x.io/ci"]
    assert any(link.is_image for link in doc.links)


def test_links_in_code_spans_and_comments_are_ignored() -> None:
    doc = parse("`[x](a.md)` and <!-- [y](b.md) --> and [z](c.md)\n")
    assert [link.target for link in doc.links] == ["c.md"]


def test_multiline_comment_is_ignored() -> None:
    doc = parse("<!--\n# hidden\n[x](a.md)\n-->\n# Shown\n")
    assert [h.text for h in doc.headings] == ["Shown"]
    assert doc.links == []


def test_parenthesised_urls() -> None:
    doc = parse("[w](https://en.wikipedia.org/wiki/Foo_(bar))\n")
    assert doc.links[0].target == "https://en.wikipedia.org/wiki/Foo_(bar)"


def test_reference_definitions_and_uses() -> None:
    text = (
        "See [text][Docs], [Docs][] and [Docs] plus [x] and [^1].\n\n"
        "[docs]: ./docs.md\n[^1]: note\n"
    )
    doc = parse(text)
    assert [(d.label, d.target) for d in doc.ref_definitions] == [("docs", "./docs.md")]
    uses = [(u.label, u.explicit) for u in doc.ref_uses]
    assert ("docs", True) in uses
    assert ("docs", False) in uses
    assert ("x", False) in uses
    assert all(label != "^1" for label, _ in uses)
    assert any(link.kind == "definition" and link.target == "./docs.md" for link in doc.links)


def test_reference_labels_are_normalised() -> None:
    assert normalize_label("  Foo   BAR ") == "foo bar"


def test_html_anchors_are_collected() -> None:
    doc = parse('<a name="old-anchor"></a>\n<div id="box">x</div>\n')
    assert doc.html_anchors == {"old-anchor", "box"}
    assert "old-anchor" in doc.anchors
    assert "box" in doc.anchors


def test_anchors_are_lowercase_slugs() -> None:
    doc = parse("# Hello World\n")
    assert doc.anchors == {"hello-world"}


def test_crlf_and_final_newline_detection() -> None:
    doc = parse("# T\r\ntext\r\n")
    assert doc.lines == ["# T", "text"]
    assert doc.ends_with_newline
    assert not parse("no newline").ends_with_newline
    assert parse("").lines == []
    assert parse("").ends_with_newline


def test_mask_code_spans_preserves_columns() -> None:
    assert mask_code_spans("a `b` c") == "a     c"
    assert mask_code_spans("a ``b ` c`` d") == "a" + " " * 11 + "d"


def test_split_comments_state_across_lines() -> None:
    visible, comment, state = split_comments("a <!-- b", False)
    assert (visible, comment, state) == ("a" + " " * 7, "<!-- b", True)
    visible, comment, state = split_comments("c --> d", True)
    assert (visible, comment, state) == ("      d", "c -->", False)
