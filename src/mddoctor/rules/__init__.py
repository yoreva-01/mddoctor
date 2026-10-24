"""Lint rules. Importing this package registers every built-in rule."""

from mddoctor.rules import fences, headings, links, references, whitespace  # noqa: F401
from mddoctor.rules.base import Context, Rule
from mddoctor.rules.registry import all_rules, register, resolve_rule_id

__all__ = ["Context", "Rule", "all_rules", "register", "resolve_rule_id"]
