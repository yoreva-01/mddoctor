"""A small line-based Markdown parser that extracts only what the rules need.

This is intentionally not a full CommonMark implementation. It recognises ATX headings, fenced
code blocks, inline code spans, HTML comments, inline links/images, reference definitions and
uses, and explicit HTML anchors, while preserving exact line/column positions.
"""

from __future__ import annotations

import re
from pathlib import Path

from mddoctor.models import Document, Fence, Heading, Link, RefDefinition, RefUse
from mddoctor.slugs import Slugger, strip_inline

_FENCE_OPEN = re.compile(r"^(?P<prefix>\s*(?:>\s*)*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
_FENCE_CLOSE = re.compile(r"^\s*(?:>\s*)*(?P<fence>`{3,}|~{3,})\s*$")
_HEADING = re.compile(r"^ {0,3}(?P<hashes>#{1,6})(?:[ \t]+(?P<text>.*?))?[ \t]*$")
_HEADING_CLOSER = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
_REF_DEFINITION = re.compile(r"^ {0,3}\[(?P<label>[^\]]+)\]:[ \t]*(?P<dest><[^>]*>|\S+)")
_INLINE_LINK = re.compile(
    r"""
    (?P<bang>!?)\[(?P<text>(?:[^\[\]\\]|\\.|\[[^\[\]]*\])*)\]
    \(\s*(?P<dest><[^<>\n]*>|(?:[^\s()\\]|\\.|\([^\s()]*\))*)
    (?:\s+(?:"[^"]*"|'[^']*'|\([^()]*\)))?\s*\)
    """,
    re.VERBOSE,
)
_REF_FULL = re.compile(r"(?<!\\)\[(?P<text>(?:[^\[\]\\]|\\.)*)\]\[(?P<label>[^\[\]]*)\]")
_REF_SHORTCUT = re.compile(r"(?<!\\)\[(?P<label>[^\[\]]+)\](?![\[(])")
_HTML_NAME_ANCHOR = re.compile(r"<a\s[^>]*?\bname\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_HTML_ID_ATTR = re.compile(r"<[A-Za-z][^>]*?\bid\s*=\s*[\"']([^\"']+)[\"']")


def normalize_label(label: str) -> str:
    """Normalise a reference label the way CommonMark matches them."""
    return " ".join(label.split()).casefold()


def mask_code_spans(line: str) -> str:
    """Blank out inline code spans, keeping every other character at the same column."""
    return _CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)


def split_comments(line: str, in_comment: bool) -> tuple[str, str, bool]:
    """Blank HTML comments in ``line``.

    Returns ``(visible, comment_text, still_in_comment)``. ``visible`` keeps the original
    columns; ``comment_text`` is the concatenation of the comment fragments on this line.
    """
    visible: list[str] = []
    comments: list[str] = []
    pos = 0
    while pos < len(line):
        if in_comment:
            search_from = pos
        else:
            start = line.find("<!--", pos)
            if start == -1:
                visible.append(line[pos:])
                break
            visible.append(line[pos:start])
            pos = start
            in_comment = True
            search_from = start + 4
        end = line.find("-->", search_from)
        if end == -1:
            comments.append(line[pos:])
            visible.append(" " * (len(line) - pos))
            pos = len(line)
        else:
            comments.append(line[pos : end + 3])
            visible.append(" " * (end + 3 - pos))
            pos = end + 3
            in_comment = False
    return "".join(visible), " ".join(comments), in_comment


def _split_lines(text: str) -> list[str]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def _unescape(value: str) -> str:
    return re.sub(r"\\(.)", r"\1", value)


def _clean_destination(dest: str) -> str:
    dest = dest.strip()
    if dest.startswith("<") and dest.endswith(">"):
        dest = dest[1:-1]
    return _unescape(dest)


def _find_inline_links(scan: str, lineno: int, offset: int = 0) -> tuple[list[Link], str]:
    """Find inline links/images (including ones nested in link text).

    Returns the links plus ``scan`` with every matched span blanked out.
    """
    links: list[Link] = []
    blanked = scan
    for match in _INLINE_LINK.finditer(scan):
        links.append(
            Link(
                target=_clean_destination(match.group("dest")),
                line=lineno,
                column=offset + match.start() + 1,
                is_image=bool(match.group("bang")),
            )
        )
        inner_start = match.start("text")
        inner, _ = _find_inline_links(match.group("text"), lineno, offset + inner_start)
        links.extend(inner)
        span = match.span()
        blanked = blanked[: span[0]] + " " * (span[1] - span[0]) + blanked[span[1] :]
    return links, blanked


def _find_reference_uses(scan: str, lineno: int) -> list[RefUse]:
    uses: list[RefUse] = []
    working = scan
    for match in _REF_FULL.finditer(scan):
        raw = match.group("label") or match.group("text")
        if raw.startswith("^") or not raw.strip():
            continue
        uses.append(
            RefUse(
                label=normalize_label(raw),
                raw_label=raw,
                line=lineno,
                column=match.start() + 1,
                explicit=True,
            )
        )
    working = _REF_FULL.sub(lambda m: " " * len(m.group(0)), working)
    for match in _REF_SHORTCUT.finditer(working):
        raw = match.group("label")
        if raw.startswith("^") or not raw.strip():
            continue
        uses.append(
            RefUse(
                label=normalize_label(raw),
                raw_label=raw,
                line=lineno,
                column=match.start() + 1,
                explicit=False,
            )
        )
    return uses


def parse_document(path: Path, text: str) -> Document:
    """Parse ``text`` (the contents of ``path``) into a :class:`Document`."""
    lines = _split_lines(text)
    count = len(lines)
    doc = Document(
        path=path,
        text=text,
        lines=lines,
        masked=list(lines),
        in_fence=[False] * count,
        comments={},
        ends_with_newline=(text == "" or text.endswith("\n")),
    )
    slugger = Slugger()
    open_fence: tuple[int, str, int, str] | None = None
    in_comment = False

    for index, line in enumerate(lines):
        lineno = index + 1

        if open_fence is not None:
            doc.in_fence[index] = True
            doc.masked[index] = ""
            closer = _FENCE_CLOSE.match(line)
            start_line, marker, length, info = open_fence
            fence_text = closer.group("fence") if closer else ""
            if fence_text and fence_text[0] == marker and len(fence_text) >= length:
                doc.fences.append(Fence(start_line, marker, length, info, True, lineno))
                open_fence = None
            continue

        if not in_comment:
            opener = _FENCE_OPEN.match(line)
            if opener:
                fence = opener.group("fence")
                info = opener.group("info").strip()
                if not (fence[0] == "`" and "`" in info):
                    open_fence = (lineno, fence[0], len(fence), info)
                    doc.in_fence[index] = True
                    doc.masked[index] = ""
                    continue

        started_in_comment = in_comment
        code_masked = mask_code_spans(line)
        scan, comment_text, in_comment = split_comments(code_masked, in_comment)
        doc.masked[index] = scan
        if comment_text:
            doc.comments[lineno] = comment_text

        if not started_in_comment:
            heading = _HEADING.match(line)
            if heading:
                raw = _HEADING_CLOSER.sub("", heading.group("text") or "").strip()
                plain = strip_inline(raw)
                doc.headings.append(
                    Heading(
                        level=len(heading.group("hashes")),
                        text=raw,
                        plain=plain,
                        slug=slugger.slug(plain),
                        line=lineno,
                    )
                )

        for pattern in (_HTML_NAME_ANCHOR, _HTML_ID_ATTR):
            doc.html_anchors.update(m.group(1) for m in pattern.finditer(scan))

        definition = _REF_DEFINITION.match(scan)
        if definition and not definition.group("label").startswith("^"):
            raw_label = definition.group("label")
            target = _clean_destination(definition.group("dest"))
            doc.ref_definitions.append(
                RefDefinition(
                    label=normalize_label(raw_label),
                    raw_label=raw_label,
                    target=target,
                    line=lineno,
                    column=definition.start("dest") + 1,
                )
            )
            doc.links.append(
                Link(
                    target=target,
                    line=lineno,
                    column=definition.start("dest") + 1,
                    kind="definition",
                )
            )
            continue

        links, blanked = _find_inline_links(scan, lineno)
        doc.links.extend(links)
        doc.ref_uses.extend(_find_reference_uses(blanked, lineno))

    if open_fence is not None:
        start_line, marker, length, info = open_fence
        doc.fences.append(Fence(start_line, marker, length, info, False, count))
    return doc
