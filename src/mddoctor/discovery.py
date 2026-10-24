"""Finding Markdown files on disk."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Sequence
from pathlib import Path

from mddoctor.config import Config

DEFAULT_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".tox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".idea",
        ".vscode",
    }
)
MARKDOWN_SUFFIXES = (".md", ".markdown")


class DiscoveryError(Exception):
    """Raised when a requested path does not exist."""


def _relative_posix(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def is_excluded(path: Path, config: Config) -> bool:
    """True if ``path`` matches a configured ``exclude`` pattern (fnmatch, relative to root).

    A pattern that names a directory also excludes everything beneath it.
    """
    relative = _relative_posix(path, config.root)
    for pattern in config.exclude:
        pattern = pattern.replace("\\", "/")
        if fnmatch.fnmatchcase(relative, pattern):
            return True
        if fnmatch.fnmatchcase(relative, pattern.rstrip("/") + "/*"):
            return True
    return False


def find_markdown_files(paths: Sequence[Path], config: Config) -> list[Path]:
    """Expand files and directories into a sorted, de-duplicated list of Markdown files.

    Files named explicitly are always included. Directories are walked recursively, skipping
    well-known tooling directories and anything matching ``config.exclude``.
    """
    found: dict[Path, None] = {}
    for path in paths:
        if not path.exists():
            raise DiscoveryError(f"path does not exist: {path}")
        if path.is_file():
            found[path.resolve()] = None
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            current = Path(dirpath)
            dirnames[:] = sorted(
                d
                for d in dirnames
                if d not in DEFAULT_EXCLUDED_DIRS and not is_excluded(current / d, config)
            )
            for name in sorted(filenames):
                candidate = current / name
                if name.lower().endswith(MARKDOWN_SUFFIXES) and not is_excluded(candidate, config):
                    found[candidate.resolve()] = None
    return sorted(found, key=lambda p: p.as_posix())
