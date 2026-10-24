"""Shared test helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from mddoctor.config import Config
from mddoctor.documents import DocumentCache
from mddoctor.models import Diagnostic
from mddoctor.rules import Context, all_rules


def write(base: Path, relative: str, content: str) -> Path:
    """Write ``content`` verbatim (no newline translation) under ``base``."""
    path = base / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")
    return path


@pytest.fixture
def run_rule(tmp_path: Path) -> Callable[..., list[Diagnostic]]:
    """Run a single rule (by code) on ``text`` saved as ``doc.md`` and return its diagnostics."""

    def _run(
        code: str,
        text: str,
        files: dict[str, str] | None = None,
        name: str = "doc.md",
    ) -> list[Diagnostic]:
        for relative, content in (files or {}).items():
            write(tmp_path, relative, content)
        path = write(tmp_path, name, text)
        ctx = Context(root=tmp_path, documents=DocumentCache(), config=Config(root=tmp_path))
        doc = ctx.documents.get(path)
        rule = next(r for r in all_rules() if r.code == code)
        return list(rule.check(doc, ctx))

    return _run
