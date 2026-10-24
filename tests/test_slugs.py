"""Tests for GitHub-style slug generation."""

import pytest

from mddoctor.slugs import Slugger, slugify, strip_inline


@pytest.mark.parametrize(
    ("plain", "expected"),
    [
        ("Hello World", "hello-world"),
        ("What's new?", "whats-new"),
        ("A & B", "a--b"),
        ("snake_case_name", "snake_case_name"),
        ("  Leading and trailing  ", "leading-and-trailing"),
        ("Already-hyphenated", "already-hyphenated"),
        ("Ünïcode Héading", "ünïcode-héading"),
        ("1. Install", "1-install"),
        ("", ""),
    ],
)
def test_slugify(plain: str, expected: str) -> None:
    assert slugify(plain) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Plain text", "Plain text"),
        ("The `foo` command", "The foo command"),
        ("**Bold** and *italic*", "Bold and italic"),
        ("A [link](http://x.y) here", "A link here"),
        ("An ![image](a.png) here", "An image here"),
        ("A [ref link][label] here", "A ref link here"),
        ("Use `*args` safely", "Use *args safely"),
        ("snake_case stays", "snake_case stays"),
        ("_emphasis_ goes", "emphasis goes"),
        ("~~struck~~ text", "struck text"),
        ("With <b>html</b> tags", "With html tags"),
        (r"Escaped \* star", "Escaped * star"),
    ],
)
def test_strip_inline(raw: str, expected: str) -> None:
    assert strip_inline(raw) == expected


def test_slugger_deduplicates_like_github() -> None:
    slugger = Slugger()
    assert slugger.slug("Usage") == "usage"
    assert slugger.slug("Usage") == "usage-1"
    assert slugger.slug("Usage") == "usage-2"
    assert slugger.slug("Other") == "other"


def test_slugger_returns_empty_for_empty_headings() -> None:
    slugger = Slugger()
    assert slugger.slug("") == ""
    assert slugger.slug("   ") == ""
    assert slugger.slug("!!!") == ""
