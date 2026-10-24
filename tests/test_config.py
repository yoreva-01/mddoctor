"""Tests for configuration loading and the rule registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from mddoctor.config import Config, ConfigError, load_config
from mddoctor.models import Severity
from mddoctor.rules import all_rules, resolve_rule_id
from mddoctor.rules.registry import register
from tests.conftest import write


def test_registry_codes_and_names_are_unique_and_documented() -> None:
    rules = all_rules()
    assert len(rules) >= 14
    assert len({r.code for r in rules}) == len(rules)
    assert len({r.name for r in rules}) == len(rules)
    assert all(r.code.startswith("MDD") and r.description for r in rules)


def test_resolve_rule_id_by_code_and_name() -> None:
    assert resolve_rule_id("MDD001") == "MDD001"
    assert resolve_rule_id("mdd001") == "MDD001"
    assert resolve_rule_id("broken-link") == "MDD001"
    assert resolve_rule_id("nonsense") is None


def test_register_rejects_duplicates() -> None:
    rule_cls = type(all_rules()[0])
    with pytest.raises(ValueError, match="duplicate rule code"):
        register(rule_cls)


def test_register_rejects_duplicate_names() -> None:
    from mddoctor.rules.base import Rule

    class Clash(Rule):
        code = "MDD999"
        name = "broken-link"
        description = "x"

    with pytest.raises(ValueError, match="duplicate rule name"):
        register(Clash)


def test_defaults_enable_everything(tmp_path: Path) -> None:
    config = load_config(start=tmp_path)
    assert config.select is None
    assert config.is_enabled("MDD001")
    assert (config.toc_min_level, config.toc_max_level) == (2, 3)
    assert config.source is None


def test_load_from_mddoctor_toml(tmp_path: Path) -> None:
    write(
        tmp_path,
        ".mddoctor.toml",
        'ignore = ["MDD021", "trailing-whitespace"]\n'
        'exclude = ["vendor/*"]\n'
        "[severity]\n"
        'MDD010 = "error"\n'
        "[toc]\nmin_level = 1\nmax_level = 4\n",
    )
    config = load_config(start=tmp_path)
    assert config.ignore == {"MDD021", "MDD040"}
    assert not config.is_enabled("MDD040")
    assert config.exclude == ("vendor/*",)
    assert config.severity_for("MDD010", Severity.WARNING) is Severity.ERROR
    assert config.severity_for("MDD011", Severity.WARNING) is Severity.WARNING
    assert (config.toc_min_level, config.toc_max_level) == (1, 4)
    assert config.root == tmp_path.resolve()


def test_load_from_pyproject_and_search_upward(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", '[tool.mddoctor]\nselect = ["MDD001"]\n')
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    config = load_config(start=nested)
    assert config.select == {"MDD001"}
    assert config.is_enabled("MDD001")
    assert not config.is_enabled("MDD002")
    assert config.root == tmp_path.resolve()


def test_pyproject_without_table_is_skipped(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", '[project]\nname = "x"\n')
    assert load_config(start=tmp_path).source is None


def test_explicit_config_path(tmp_path: Path) -> None:
    path = write(tmp_path, "custom.toml", 'ignore = ["MDD001"]\n')
    assert load_config(explicit=path).ignore == {"MDD001"}


def test_explicit_pyproject_without_table_is_empty_config(tmp_path: Path) -> None:
    path = write(tmp_path, "pyproject.toml", '[project]\nname = "x"\n')
    assert load_config(explicit=path).select is None


def test_explicit_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(explicit=tmp_path / "nope.toml")


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("bogus = 1\n", "unknown option"),
        ('ignore = "MDD001"\n', "list of strings"),
        ('ignore = ["MDD999"]\n', "unknown rule"),
        ('select = ["nope"]\n', "unknown rule"),
        ('severity = "error"\n', "table"),
        ('[severity]\nMDD999 = "error"\n', "unknown rule"),
        ('[severity]\nMDD001 = "fatal"\n', "invalid severity"),
        ('toc = "x"\n', "'toc' must be a table"),
        ("[toc]\nfoo = 1\n", "unknown toc option"),
        ("[toc]\nmin_level = 4\nmax_level = 2\n", "toc levels"),
        ("[toc]\nmin_level = 0\n", "toc levels"),
        ('[toc]\nmin_level = "a"\n', "toc levels"),
        ("this is not toml\n", "invalid TOML"),
    ],
)
def test_invalid_config(tmp_path: Path, content: str, message: str) -> None:
    path = write(tmp_path, ".mddoctor.toml", content)
    with pytest.raises(ConfigError, match=message):
        load_config(explicit=path)


def test_config_dataclass_helpers(tmp_path: Path) -> None:
    config = Config(root=tmp_path, select=frozenset({"MDD001"}), ignore=frozenset({"MDD001"}))
    assert not config.is_enabled("MDD001")  # ignore wins over select


def test_severity_parse() -> None:
    assert Severity.parse(" Warning ") is Severity.WARNING
    with pytest.raises(ValueError, match="invalid severity"):
        Severity.parse("fatal")
