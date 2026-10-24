"""Tests for file discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from mddoctor.config import Config
from mddoctor.discovery import DiscoveryError, find_markdown_files, is_excluded
from tests.conftest import write


def names(paths: list[Path], base: Path) -> list[str]:
    return [p.relative_to(base.resolve()).as_posix() for p in paths]


def test_walks_directories_for_markdown_only(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "# R\n")
    write(tmp_path, "docs/guide.markdown", "# G\n")
    write(tmp_path, "docs/notes.txt", "x")
    write(tmp_path, "docs/UPPER.MD", "# U\n")
    found = find_markdown_files([tmp_path], Config(root=tmp_path))
    assert names(found, tmp_path) == ["README.md", "docs/UPPER.MD", "docs/guide.markdown"]


def test_default_excluded_directories_are_skipped(tmp_path: Path) -> None:
    write(tmp_path, "a.md", "# A\n")
    write(tmp_path, "node_modules/pkg/readme.md", "# N\n")
    write(tmp_path, ".git/info.md", "# G\n")
    write(tmp_path, ".venv/lib/x.md", "# V\n")
    found = find_markdown_files([tmp_path], Config(root=tmp_path))
    assert names(found, tmp_path) == ["a.md"]


def test_exclude_patterns_apply_to_files_and_directories(tmp_path: Path) -> None:
    write(tmp_path, "keep.md", "# K\n")
    write(tmp_path, "CHANGELOG.md", "# C\n")
    write(tmp_path, "vendor/deep/x.md", "# X\n")
    write(tmp_path, "docs/draft-1.md", "# D\n")
    config = Config(root=tmp_path, exclude=("CHANGELOG.md", "vendor", "docs/draft-*"))
    found = find_markdown_files([tmp_path], config)
    assert names(found, tmp_path) == ["keep.md"]


def test_explicit_files_are_always_included(tmp_path: Path) -> None:
    path = write(tmp_path, "CHANGELOG.md", "# C\n")
    other = write(tmp_path, "notes.txt", "text")
    config = Config(root=tmp_path, exclude=("CHANGELOG.md",))
    assert find_markdown_files([path, other], config) == [path.resolve(), other.resolve()]


def test_results_are_deduplicated(tmp_path: Path) -> None:
    path = write(tmp_path, "a.md", "# A\n")
    found = find_markdown_files([path, tmp_path, path], Config(root=tmp_path))
    assert found == [path.resolve()]


def test_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(DiscoveryError, match="does not exist"):
        find_markdown_files([tmp_path / "nope"], Config(root=tmp_path))


def test_is_excluded_outside_root_uses_absolute_path(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = write(tmp_path, "outside.md", "# O\n")
    assert not is_excluded(outside, Config(root=root, exclude=("root/*",)))
    assert is_excluded(outside, Config(root=root, exclude=("*outside.md",)))
