"""Configuration loading (``.mddoctor.toml`` or ``[tool.mddoctor]`` in ``pyproject.toml``)."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mddoctor.models import Severity
from mddoctor.rules import resolve_rule_id

CONFIG_FILENAMES = (".mddoctor.toml", "pyproject.toml")
_KNOWN_KEYS = {"select", "ignore", "exclude", "severity", "toc"}
_KNOWN_TOC_KEYS = {"min_level", "max_level"}


class ConfigError(Exception):
    """Raised for unreadable or invalid configuration."""


@dataclass(frozen=True)
class Config:
    """Effective configuration for a run. ``root`` anchors ``/``-prefixed links and excludes."""

    root: Path
    select: frozenset[str] | None = None  # None means "all rules"
    ignore: frozenset[str] = frozenset()
    exclude: tuple[str, ...] = ()
    severity: Mapping[str, Severity] = field(default_factory=dict)
    toc_min_level: int = 2
    toc_max_level: int = 3
    source: Path | None = None

    def is_enabled(self, code: str) -> bool:
        if code in self.ignore:
            return False
        return self.select is None or code in self.select

    def severity_for(self, code: str, default: Severity) -> Severity:
        return self.severity.get(code, default)


def resolve_rule_ids(tokens: list[str], where: str) -> frozenset[str]:
    """Convert user-provided rule codes/names to canonical codes, rejecting unknown ones."""
    codes: set[str] = set()
    for token in tokens:
        code = resolve_rule_id(token)
        if code is None:
            raise ConfigError(f"{where}: unknown rule {token!r}")
        codes.add(code)
    return frozenset(codes)


def _string_list(table: Mapping[str, Any], key: str, source: Path) -> list[str]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{source}: '{key}' must be a list of strings")
    return value


def _build(table: Mapping[str, Any], root: Path, source: Path) -> Config:
    unknown = sorted(set(table) - _KNOWN_KEYS)
    if unknown:
        raise ConfigError(f"{source}: unknown option(s): {', '.join(unknown)}")

    select = None
    if "select" in table:
        select = resolve_rule_ids(_string_list(table, "select", source), f"{source}: select")
    ignore = resolve_rule_ids(_string_list(table, "ignore", source), f"{source}: ignore")
    exclude = tuple(_string_list(table, "exclude", source))

    severity: dict[str, Severity] = {}
    raw_severity = table.get("severity", {})
    if not isinstance(raw_severity, dict):
        raise ConfigError(f"{source}: 'severity' must be a table of rule = level")
    for token, level in raw_severity.items():
        code = resolve_rule_id(token)
        if code is None:
            raise ConfigError(f"{source}: severity: unknown rule {token!r}")
        try:
            severity[code] = Severity.parse(str(level))
        except ValueError as exc:
            raise ConfigError(f"{source}: severity.{token}: {exc}") from None

    raw_toc = table.get("toc", {})
    if not isinstance(raw_toc, dict):
        raise ConfigError(f"{source}: 'toc' must be a table")
    unknown_toc = sorted(set(raw_toc) - _KNOWN_TOC_KEYS)
    if unknown_toc:
        raise ConfigError(f"{source}: unknown toc option(s): {', '.join(unknown_toc)}")
    min_level = raw_toc.get("min_level", 2)
    max_level = raw_toc.get("max_level", 3)
    valid = all(
        isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 6
        for v in (min_level, max_level)
    )
    if not valid or min_level > max_level:
        raise ConfigError(f"{source}: toc levels must be integers 1-6 with min_level <= max_level")

    return Config(
        root=root,
        select=select,
        ignore=ignore,
        exclude=exclude,
        severity=severity,
        toc_min_level=min_level,
        toc_max_level=max_level,
        source=source,
    )


def _read_table(path: Path, *, explicit: bool) -> dict[str, Any] | None:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: invalid TOML ({exc})") from exc
    except OSError as exc:
        raise ConfigError(f"{path}: {exc.strerror or exc}") from exc
    if path.name == "pyproject.toml":
        tool = data.get("tool", {})
        table = tool.get("mddoctor") if isinstance(tool, dict) else None
        if table is None:
            return {} if explicit else None
        return table
    return data


def load_config(explicit: Path | None = None, start: Path | None = None) -> Config:
    """Load configuration from ``explicit`` or by searching upward from ``start`` (default: cwd)."""
    if explicit is not None:
        path = explicit.resolve()
        if not path.is_file():
            raise ConfigError(f"config file not found: {explicit}")
        table = _read_table(path, explicit=True) or {}
        return _build(table, path.parent, path)

    origin = (start or Path.cwd()).resolve()
    for directory in (origin, *origin.parents):
        for name in CONFIG_FILENAMES:
            candidate = directory / name
            if candidate.is_file():
                table = _read_table(candidate, explicit=False)
                if table is not None:
                    return _build(table, directory, candidate)
    return Config(root=origin)
