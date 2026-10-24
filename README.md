# mddoctor

[![CI](https://github.com/baldeaguirre/mddoctor/actions/workflows/ci.yml/badge.svg)](https://github.com/baldeaguirre/mddoctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**An offline Markdown docs linter.** `mddoctor` catches the things that quietly rot in a
documentation tree: relative links to files that were renamed, `#anchors` that no longer match
a heading, skipped heading levels, unclosed code fences, undefined reference links, and more.
It also generates and verifies tables of contents. It needs no network access and has
**zero runtime dependencies**.

<!-- toc -->

- [Features](#features)
- [Install](#install)
- [Usage](#usage)
  - [Check files](#check-files)
  - [Use it in CI](#use-it-in-ci)
  - [JSON output](#json-output)
  - [Table of contents](#table-of-contents)
  - [List rules](#list-rules)
- [Rules](#rules)
- [Configuration](#configuration)
- [Suppressing diagnostics](#suppressing-diagnostics)
- [Project structure](#project-structure)
- [Development](#development)
- [Known limitations](#known-limitations)
- [Contributing](#contributing)
- [License](#license)

<!-- tocstop -->

## Features

- Validates **relative links, images, and `#fragments`** the way GitHub resolves them
  (including `-1`/`-2` suffixes for duplicate headings and explicit `<a name>` anchors),
  with "did you mean" suggestions.
- 16 rules covering links, headings, code fences, reference links, and whitespace.
- Output as plain text, JSON, or **GitHub Actions annotations**.
- `toc` command that writes or verifies a table of contents between markers.
- Configurable via `.mddoctor.toml` or `[tool.mddoctor]` in `pyproject.toml`.
- Inline `<!-- mddoctor-disable ... -->` comments for exceptions.
- Fast and offline; understands CRLF files and UTF-8 BOMs.

## Install

Requires Python 3.11 or newer.

```bash
pip install git+https://github.com/baldeaguirre/mddoctor.git
```

Or from a clone, for development:

```bash
git clone https://github.com/baldeaguirre/mddoctor.git
cd mddoctor
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Usage

### Check files

```text
$ mddoctor check
README.md:3:16: error MDD002 broken-anchor: Anchor '#instalation' not found in 'docs/setup.md' (did you mean '#installation'?)
README.md:3:64: error MDD001 broken-link: Link target 'docs/api.md' does not exist
README.md:4:20: error MDD030 undefined-reference: Reference '[faq]' has no definition
README.md:4:39: error MDD030 undefined-reference: Reference '[roadmap]' has no definition
README.md:8:1: warning MDD021 fence-language: Fenced code block has no language specified
README.md:12:1: warning MDD010 heading-increment: Heading level jumps from H2 to H4
README.md:14:21: warning MDD040 trailing-whitespace: Trailing whitespace (3 chars)
docs/setup.md:7:1: warning MDD013 duplicate-heading: Duplicate heading 'Installation' (first on line 3)
docs/setup.md:9:58: error MDD001 broken-link: Link target 'guide.md' does not exist
docs/setup.md:11:1: warning MDD031 unused-definition: Reference definition '[unused]' is never used

Checked 2 files: 5 errors, 5 warnings
```

That output comes from [examples/broken-docs](examples/broken-docs), a tiny docs tree that is
broken on purpose. Try it yourself:

```bash
cd examples/broken-docs && mddoctor check
```

Paths may be files or directories (default: the current directory). Directories are walked
recursively, skipping `.git`, `node_modules`, virtualenvs, and similar folders.

| Option | Meaning |
| --- | --- |
| `--select RULES` | Only run these rules (codes or names, comma-separated or repeated) |
| `--ignore RULES` | Skip these rules |
| `--format text\|json\|github` | Output format (default `text`) |
| `--strict` | Treat warnings as failures (exit code 1) |
| `--config FILE` | Use a specific `.mddoctor.toml` or `pyproject.toml` |

Exit codes: `0` clean (or warnings only), `1` problems found, `2` usage or configuration error.

### Use it in CI

```yaml
- run: pip install git+https://github.com/baldeaguirre/mddoctor.git
- run: mddoctor check --strict --format github README.md docs
```

With `--format github`, problems appear as inline annotations on the pull request.

### JSON output

```text
$ mddoctor check --format json README.md --select MDD002
{
  "files_checked": 1,
  "summary": {
    "errors": 1,
    "warnings": 0
  },
  "diagnostics": [
    {
      "path": "README.md",
      "line": 3,
      "column": 16,
      "code": "MDD002",
      "name": "broken-anchor",
      "severity": "error",
      "message": "Anchor '#instalation' not found in 'docs/setup.md' (did you mean '#installation'?)"
    }
  ]
}
```

### Table of contents

Put these markers where the TOC should live:

```markdown
<!-- toc -->
<!-- tocstop -->
```

Then:

```bash
mddoctor toc README.md --write     # create or refresh the TOC in place
mddoctor toc README.md --check     # exit 1 if it is out of date (good for CI)
mddoctor toc README.md             # just print the TOC
mddoctor toc README.md --min-level 1 --max-level 4
```

By default headings of level 2 and 3 are listed. Anything between the markers is replaced.

### List rules

```bash
mddoctor rules
```

## Rules

| Code | Name | Severity | Checks |
| --- | --- | --- | --- |
| MDD001 | `broken-link` | error | Relative link or image target does not exist |
| MDD002 | `broken-anchor` | error | `#fragment` matches no heading or HTML anchor in the target file |
| MDD003 | `empty-link` | warning | Empty destination: `[text]()` or `[text](#)` |
| MDD010 | `heading-increment` | warning | Heading level jumps by more than one |
| MDD011 | `multiple-h1` | warning | More than one top-level heading |
| MDD012 | `missing-h1` | warning | No top-level heading in a non-empty file |
| MDD013 | `duplicate-heading` | warning | Same heading text twice under the same parent |
| MDD014 | `empty-heading` | warning | Heading with no text |
| MDD020 | `unclosed-fence` | error | Code fence never closed |
| MDD021 | `fence-language` | warning | Code fence without a language |
| MDD030 | `undefined-reference` | error | `[text][label]` with no definition |
| MDD031 | `unused-definition` | warning | `[label]: url` that nothing uses |
| MDD032 | `duplicate-definition` | warning | Same reference label defined twice |
| MDD040 | `trailing-whitespace` | warning | Trailing spaces or tabs (two spaces for a hard break are allowed) |
| MDD041 | `hard-tab` | warning | Tab characters outside code blocks |
| MDD042 | `final-newline` | warning | Missing final newline or extra trailing blank lines |

Links inside fenced code, inline code, and HTML comments are never checked. Shortcut
references like `[text]` are only treated as references when a matching definition exists.

## Configuration

`mddoctor` looks for `.mddoctor.toml`, then `pyproject.toml` (a `[tool.mddoctor]` table),
starting in the current directory and walking up. The directory containing the config file is
the project root: it anchors `/`-prefixed links and `exclude` patterns.

```toml
# .mddoctor.toml  (in pyproject.toml, put these under [tool.mddoctor])
select = ["MDD001", "MDD002", "heading-increment"]   # default: all rules
ignore = ["fence-language"]                           # codes or names
exclude = ["CHANGELOG.md", "vendor/*", "docs/drafts"] # fnmatch patterns, relative to root

[severity]
heading-increment = "error"                           # promote or demote any rule

[toc]
min_level = 2
max_level = 3
```

Unknown options and unknown rule names are reported as errors (exit code 2) rather than ignored.

## Suppressing diagnostics

```markdown
<!-- mddoctor-disable-next-line MDD001 -->
[a link that is intentionally dangling](generated-at-build-time.md)

<!-- mddoctor-disable MDD040 -->
Lines in this region may have trailing whitespace.
<!-- mddoctor-enable MDD040 -->

<!-- mddoctor-disable-file fence-language -->
```

With no rules listed, a directive applies to every rule. Directives inside code blocks and
code spans are ignored, so they can be documented safely.

## Project structure

```text
src/mddoctor/
├── cli.py          # argparse front-end: check, toc, rules
├── config.py       # .mddoctor.toml / pyproject.toml loading and validation
├── discovery.py    # find Markdown files, apply excludes
├── documents.py    # read + cache parsed documents
├── engine.py       # run rules, apply suppression and severity overrides
├── models.py       # dataclasses: Diagnostic, Document, Heading, Link, ...
├── parser.py       # line-based Markdown parser
├── reporters.py    # text / json / github formatters
├── slugs.py        # GitHub-style heading anchors
├── suppress.py     # inline disable/enable comments
├── toc.py          # table-of-contents generation
└── rules/          # one module per rule family + registry
tests/              # pytest suite (parser, rules, config, CLI, ...)
docs/               # PLAN.md and ARCHITECTURE.md
examples/           # a deliberately broken docs tree
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design notes and how to add a rule.

## Development

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest --cov                                   # fails below 85% coverage
python -m mddoctor check --strict README.md CONTRIBUTING.md docs
```

CI runs these on Linux, macOS, and Windows (Python 3.11 and 3.13).

## Known limitations

- Only ATX headings (`# Title`) are recognised; Setext headings (underlines) are not.
- Indented (four-space) code blocks are not masked.
- Link destinations and code spans that span several lines are not detected.
- Existence checks follow the host filesystem, so a wrong-case path passes on Windows and
  macOS but fails on Linux.

These and other ideas are tracked in the
[issue tracker](https://github.com/baldeaguirre/mddoctor/issues).

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first; it covers the
dev setup, checks, and commit conventions.

## License

[MIT](LICENSE) © 2026 Baldemar Aguirre
