"""Command-line interface: ``mddoctor check | toc | rules``."""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from mddoctor import __version__
from mddoctor.config import Config, ConfigError, load_config, resolve_rule_ids
from mddoctor.discovery import DiscoveryError, find_markdown_files
from mddoctor.documents import DocumentLoadError, load_document
from mddoctor.engine import lint_files
from mddoctor.reporters import FORMATTERS, display_path
from mddoctor.rules import all_rules
from mddoctor.toc import TocError, build_toc, update_toc_file

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2

_EPILOG = """\
exit codes:
  0  no problems (or only warnings, unless --strict)
  1  problems found
  2  usage or configuration error
"""


def _split_csv(values: list[str] | None) -> list[str]:
    items: list[str] = []
    for value in values or []:
        items.extend(part.strip() for part in value.split(",") if part.strip())
    return items


def _effective_config(args: argparse.Namespace) -> Config:
    config = load_config(args.config)
    select = _split_csv(getattr(args, "select", None))
    ignore = _split_csv(getattr(args, "ignore", None))
    if select:
        config = replace(config, select=resolve_rule_ids(select, "--select"))
    if ignore:
        config = replace(config, ignore=config.ignore | resolve_rule_ids(ignore, "--ignore"))
    return config


def _error(message: str) -> int:
    print(f"mddoctor: error: {message}", file=sys.stderr)
    return EXIT_USAGE


def _cmd_check(args: argparse.Namespace) -> int:
    config = _effective_config(args)
    files = find_markdown_files([Path(p) for p in args.paths or ["."]], config)
    if not files:
        print("mddoctor: no Markdown files found", file=sys.stderr)
        return EXIT_OK
    if getattr(args, "fix", False):
        from mddoctor.engine import apply_fixes

        fixed = apply_fixes(files, config)
        for item in fixed:
            if item.changed:
                print(f"fixed: {item.path}")
    result = lint_files(files, config)
    output = FORMATTERS[args.format](result, Path.cwd())
    if output:
        print(output)
    return EXIT_FINDINGS if result.failed(strict=args.strict) else EXIT_OK


def _cmd_toc(args: argparse.Namespace) -> int:
    config = _effective_config(args)
    min_level = args.min_level or config.toc_min_level
    max_level = args.max_level or config.toc_max_level
    if min_level > max_level:
        return _error("--min-level must not exceed --max-level")
    paths = [Path(p) for p in args.files]
    cwd = Path.cwd()

    if not (args.write or args.check):
        if len(paths) != 1:
            return _error("pass exactly one file to print its TOC (or use --write / --check)")
        try:
            doc = load_document(paths[0])
            toc = build_toc(doc, min_level, max_level)
        except (DocumentLoadError, TocError) as exc:
            return _error(str(exc))
        print("\n".join(toc))
        return EXIT_OK

    outdated = 0
    for path in paths:
        try:
            result = update_toc_file(path, min_level, max_level, write=args.write)
        except TocError as exc:
            return _error(str(exc))
        shown = display_path(path.resolve(), cwd)
        if args.write:
            state = "updated" if result.changed else "already up to date"
            print(f"{shown}: {state} ({result.entries} entries)")
        elif result.changed:
            outdated += 1
            print(f"{shown}: table of contents is out of date")
        else:
            print(f"{shown}: table of contents is up to date")
    return EXIT_FINDINGS if outdated else EXIT_OK


def _cmd_rules(_: argparse.Namespace) -> int:
    rules = all_rules()
    name_width = max(len(r.name) for r in rules)
    for rule in rules:
        print(
            f"{rule.code}  {rule.severity.value:<7}  {rule.name:<{name_width}}  {rule.description}"
        )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mddoctor",
        description="Offline Markdown docs linter and TOC generator.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"mddoctor {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    check = commands.add_parser(
        "check",
        help="lint Markdown files and directories",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    check.add_argument("paths", nargs="*", help="files or directories (default: current directory)")
    check.add_argument("--config", type=Path, help="path to a .mddoctor.toml or pyproject.toml")
    check.add_argument("--select", action="append", metavar="RULES", help="only run these rules")
    check.add_argument("--ignore", action="append", metavar="RULES", help="skip these rules")
    check.add_argument(
        "--format", choices=sorted(FORMATTERS), default="text", help="output format (default: text)"
    )
    check.add_argument("--strict", action="store_true", help="exit with 1 on warnings too")
    check.add_argument(
        "--fix",
        action="store_true",
        help="auto-correct trailing whitespace, hard tabs, and final newline",
    )
    check.set_defaults(handler=_cmd_check)

    toc = commands.add_parser(
        "toc",
        help="generate or verify a table of contents",
        description=(
            "Print a table of contents, or (--write / --check) maintain the one between "
            "'<!-- toc -->' and '<!-- tocstop -->' markers."
        ),
    )
    toc.add_argument("files", nargs="+", help="Markdown files")
    toc.add_argument("--config", type=Path, help="path to a .mddoctor.toml or pyproject.toml")
    toc.add_argument("--min-level", type=int, choices=range(1, 7), help="shallowest heading level")
    toc.add_argument("--max-level", type=int, choices=range(1, 7), help="deepest heading level")
    mode = toc.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="update the files in place")
    mode.add_argument("--check", action="store_true", help="exit 1 if any TOC is out of date")
    toc.set_defaults(handler=_cmd_toc)

    rules = commands.add_parser("rules", help="list available rules")
    rules.set_defaults(handler=_cmd_rules)
    return parser


def _use_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError, OSError):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    _use_utf8_streams()
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (ConfigError, DiscoveryError) as exc:
        return _error(str(exc))
