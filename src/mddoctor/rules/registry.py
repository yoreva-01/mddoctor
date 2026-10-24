"""Central registry of lint rules."""

from __future__ import annotations

from mddoctor.rules.base import Rule

_REGISTRY: dict[str, type[Rule]] = {}


def register(cls: type[Rule]) -> type[Rule]:
    """Class decorator that adds a rule to the registry (codes must be unique)."""
    if cls.code in _REGISTRY:
        raise ValueError(f"duplicate rule code {cls.code}")
    if any(existing.name == cls.name for existing in _REGISTRY.values()):
        raise ValueError(f"duplicate rule name {cls.name}")
    _REGISTRY[cls.code] = cls
    return cls


def all_rules() -> list[Rule]:
    """Instantiate every registered rule, ordered by code."""
    return [_REGISTRY[code]() for code in sorted(_REGISTRY)]


def resolve_rule_id(token: str) -> str | None:
    """Map a rule code (``MDD001``) or name (``broken-link``) to its canonical code."""
    needle = token.strip().lower()
    for code, cls in _REGISTRY.items():
        if needle in (code.lower(), cls.name.lower()):
            return code
    return None
