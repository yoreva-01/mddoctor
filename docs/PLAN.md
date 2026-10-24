# mddoctor – Project Plan

## Ideas considered

| Idea | Summary | Verdict |
| --- | --- | --- |
| **mddoctor** | Offline Markdown documentation linter: broken relative links, broken `#anchors`, heading structure, fences, reference links, whitespace; plus a TOC generator | **Chosen** – bounded scope, modular rule architecture, immediately useful |
| taskgraph | Dependency-aware task runner driven by TOML | Crowded space (make, just, task) |
| envdiff | Compare `.env` and `.env.example` files | Too close to secrets handling; small scope |

mddoctor has the best scope-to-value ratio. It is stdlib-only (zero runtime
dependencies), runs anywhere Python runs, and its rule-per-module design
leaves clear room for new rules, reporters, and auto-fixes.

## Problem statement

Documentation rots quietly. Files are renamed, headings are reworded, and
relative links and `#anchor` fragments silently break. Existing Markdown
linters mostly focus on style; checking that *links between files and
headings are valid* usually requires a site generator or network-based link
checkers. `mddoctor` validates a docs tree **offline and fast**, in a way that
matches how GitHub renders Markdown, and is easy to wire into CI.

## Target users

- Maintainers of open-source repos with `README.md` + `docs/` trees.
- Teams that keep Markdown docs in a monorepo and want a quick CI gate.
- Writers who want an auto-generated, always-correct table of contents.

## Features

### MVP (this repository's first release)

- `mddoctor check [PATHS...]` – lint files and directories.
  - Rules: broken links, broken anchors, empty links, heading increments,
    multiple/missing H1, duplicate headings, empty headings, unclosed fences,
    fences without language, undefined/unused/duplicate reference
    definitions, trailing whitespace, hard tabs, final newline.
  - Output formats: `text`, `json`, `github` (Actions annotations).
  - Exit codes: `0` clean, `1` findings, `2` usage/config error.
- `mddoctor toc FILE` – generate / update / verify a table of contents
  between `<!-- toc -->` and `<!-- tocstop -->` markers.
- `mddoctor rules` – list available rules.
- Configuration via `.mddoctor.toml` or `[tool.mddoctor]` in `pyproject.toml`
  (select, ignore, exclude, per-rule severity, TOC levels).
- Inline suppression comments (`<!-- mddoctor-disable-next-line MDD001 -->`).

### Later (tracked as GitHub issues)

- `--fix` for auto-fixable rules.
- Opt-in external URL checking.
- SARIF output.
- Setext headings, indented code blocks.
- Case-exact path checks on case-insensitive filesystems.
- Per-rule documentation pages and a rule-authoring guide.

## Architecture overview

```text
paths ─► discovery ─► DocumentCache ─► parser ─► Document
                                          │
config ─► engine ─► rules (registry) ─────┘
             │
             ├─► suppression filter
             └─► reporters (text / json / github)
```

- **parser** turns raw text into an immutable `Document` (headings, links,
  reference definitions/uses, fences, HTML anchors). Fenced code and inline
  code are masked so rules never see "links" inside code.
- **rules** are small classes registered in a central registry; each yields
  `Diagnostic` objects. Rules that need other files (links/anchors) ask the
  shared `DocumentCache`.
- **engine** wires config, discovery, rules, suppression, and severity
  overrides together.
- **reporters** render diagnostics; they are pure functions of the list.

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Directory layout

```text
mddoctor/
├── src/mddoctor/
│   ├── cli.py            # argparse front-end
│   ├── config.py         # config loading & validation
│   ├── discovery.py      # find Markdown files
│   ├── engine.py         # run rules, apply suppression/severity
│   ├── models.py         # Severity, Diagnostic, Document, ...
│   ├── parser.py         # Markdown -> Document
│   ├── reporters.py      # text / json / github output
│   ├── slugs.py          # GitHub-style heading slugs
│   ├── suppress.py       # inline disable comments
│   ├── toc.py            # TOC generation
│   └── rules/            # one module per rule family
├── tests/
├── docs/
└── .github/workflows/ci.yml
```

## Tech choices

| Choice | Reason |
| --- | --- |
| Python ≥ 3.11 | `tomllib` in the stdlib; ubiquitous on dev machines |
| Zero runtime deps | Easy install, nothing to audit |
| `argparse` | Stdlib; sufficient for 3 sub-commands |
| `hatchling` build backend (MIT) | Simple, standards-based `pyproject.toml` builds |
| `pytest` + `pytest-cov` (MIT) | De-facto standard test stack |
| `ruff` (MIT) | One tool for lint + format, fast |
| Hand-written line-based parser | Full CommonMark is overkill; we need only a handful of constructs and exact line/column positions |

## Known limitations (by design for the MVP)

- Setext (`===` / `---`) headings are not recognised.
- Indented (4-space) code blocks are not masked.
- Multi-line link destinations / code spans are not handled.
- Path existence checks use the host filesystem's case rules.

## Roadmap

Status legend: **done** = in the repository now, **planned** = tracked as a GitHub issue.

| Release | Scope | Status |
| --- | --- | --- |
| v0.1 | Parser, 16 rules, `check` / `toc` / `rules` commands, config, suppression, text/json/github output, CI | done |
| v0.2 | `--fix` for auto-fixable rules, SARIF output, Setext headings, case-exact path checks | planned |
| v0.3 | Opt-in external link checking, parallel file processing, indented code block masking | planned |
| v1.0 | Stable rule IDs, per-rule documentation pages, plugin entry points for third-party rules | planned |
