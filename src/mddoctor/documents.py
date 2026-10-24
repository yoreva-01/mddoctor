"""Loading and caching parsed documents from disk."""

from __future__ import annotations

from pathlib import Path

from mddoctor.models import Document
from mddoctor.parser import parse_document


class DocumentLoadError(Exception):
    """Raised when a Markdown file cannot be read or decoded."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


def load_document(path: Path) -> Document:
    """Read ``path`` as UTF-8 (a leading BOM is tolerated) and parse it."""
    resolved = path.resolve()
    try:
        text = resolved.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentLoadError(resolved, f"not valid UTF-8 ({exc.reason})") from exc
    except OSError as exc:
        raise DocumentLoadError(resolved, exc.strerror or str(exc)) from exc
    return parse_document(resolved, text)


class DocumentCache:
    """Parses each file at most once, so cross-file rules do not re-read the same targets."""

    def __init__(self) -> None:
        self._documents: dict[Path, Document | DocumentLoadError] = {}

    def get(self, path: Path) -> Document:
        key = path.resolve()
        entry = self._documents.get(key)
        if entry is None:
            try:
                entry = load_document(key)
            except DocumentLoadError as exc:
                entry = exc
            self._documents[key] = entry
        if isinstance(entry, DocumentLoadError):
            raise entry
        return entry

    def try_get(self, path: Path) -> Document | None:
        try:
            return self.get(path)
        except DocumentLoadError:
            return None
