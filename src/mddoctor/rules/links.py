"""Link rules: broken file links, broken ``#anchors``, and empty destinations."""

from __future__ import annotations

import difflib
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from mddoctor.models import Diagnostic, Document, Severity
from mddoctor.rules.base import Context, Rule
from mddoctor.rules.registry import register

_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
_LINE_ANCHOR = re.compile(r"^L\d+(?:C\d+)?(?:-L\d+(?:C\d+)?)?$")
_MARKDOWN_SUFFIXES = {".md", ".markdown"}
_ALWAYS_VALID_FRAGMENTS = {"top"}


@dataclass(frozen=True)
class LocalTarget:
    """A link destination that points at a path in the local project."""

    path: Path
    fragment: str  # percent-decoded, without the leading ``#``; may be empty


def parse_local_target(target: str, doc: Document, ctx: Context) -> LocalTarget | None:
    """Resolve ``target`` against ``doc``; return None for external or non-file destinations."""
    target = target.strip()
    if not target or _SCHEME.match(target) or target.startswith("//"):
        return None
    path_part, _, fragment = target.partition("#")
    path_part = path_part.partition("?")[0]
    path_part = unquote(path_part)
    if not path_part:
        resolved = doc.path
    elif path_part.startswith("/"):
        resolved = Path(os.path.normpath(ctx.root / path_part.lstrip("/")))
    else:
        resolved = Path(os.path.normpath(doc.path.parent / path_part))
    return LocalTarget(path=resolved, fragment=unquote(fragment))


@register
class BrokenLink(Rule):
    code = "MDD001"
    name = "broken-link"
    description = "A relative link or image points to a file or directory that does not exist."
    severity = Severity.ERROR

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        for link in doc.links:
            local = parse_local_target(link.target, doc, ctx)
            if local is None or local.path == doc.path:
                continue
            if not local.path.exists():
                what = "Image" if link.is_image else "Link"
                yield self.diagnostic(
                    doc, link.line, link.column, f"{what} target '{link.target}' does not exist"
                )


@register
class BrokenAnchor(Rule):
    code = "MDD002"
    name = "broken-anchor"
    description = "A link's #fragment does not match any heading or HTML anchor in the target file."
    severity = Severity.ERROR

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        for link in doc.links:
            local = parse_local_target(link.target, doc, ctx)
            if local is None or not local.fragment:
                continue
            fragment = local.fragment.lower()
            if fragment in _ALWAYS_VALID_FRAGMENTS or _LINE_ANCHOR.match(local.fragment):
                continue
            if local.path.suffix.lower() not in _MARKDOWN_SUFFIXES or not local.path.is_file():
                continue
            target_doc = doc if local.path == doc.path else ctx.documents.try_get(local.path)
            if target_doc is None or fragment in target_doc.anchors:
                continue
            message = f"Anchor '#{local.fragment}' not found"
            if local.path != doc.path:
                message += f" in '{link.target.partition('#')[0]}'"
            close = difflib.get_close_matches(fragment, sorted(target_doc.anchors), n=1)
            if close:
                message += f" (did you mean '#{close[0]}'?)"
            yield self.diagnostic(doc, link.line, link.column, message)


@register
class EmptyLink(Rule):
    code = "MDD003"
    name = "empty-link"
    description = "A link has an empty destination (``[text]()`` or ``[text](#)``)."
    severity = Severity.WARNING

    def check(self, doc: Document, ctx: Context) -> Iterator[Diagnostic]:
        for link in doc.links:
            if link.target.strip() in ("", "#"):
                yield self.diagnostic(doc, link.line, link.column, "Link has an empty destination")
