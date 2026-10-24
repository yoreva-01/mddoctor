# Architecture

A short tour of how `mddoctor` is put together. For goals and roadmap see
[PLAN.md](PLAN.md).

## Data flow

```text
CLI args ─► config.load_config ─► discovery.find_markdown_files
                                         │
                                         ▼
                       engine.lint_files(files, config)
                         │        │
                         │        └─► DocumentCache ─► parser.parse_document ─► Document
                         ▼
                 for each rule in registry:
                     rule.check(document, context) ─► Diagnostic*
                         │
                         ├─► suppress.Suppressions  (inline disable comments)
                         └─► severity overrides from config
                         ▼
                 LintResult ─► reporters.FORMATTERS[format] ─► stdout
```

## Modules

| Module | Responsibility |
| --- | --- |
| `models.py` | Plain dataclasses: `Severity`, `Diagnostic`, `Document`, `Heading`, `Link`, ... |
| `parser.py` | Line-based Markdown parser producing a `Document` with exact positions |
| `slugs.py` | GitHub-compatible heading slugs, including `-1`, `-2` duplicate suffixes |
| `documents.py` | Read files (UTF-8, BOM tolerant, CRLF preserved) and cache parsed documents |
| `config.py` | Load and validate `.mddoctor.toml` / `[tool.mddoctor]` |
| `discovery.py` | Walk directories, skip tooling folders, apply `exclude` patterns |
| `rules/` | One module per rule family; a registry maps codes and names to classes |
| `suppress.py` | `<!-- mddoctor-disable ... -->` directives |
| `engine.py` | Orchestrates rules, suppression, and severity overrides |
| `reporters.py` | `text`, `json`, and `github` (Actions annotations) formatters |
| `toc.py` | Table-of-contents generation between markers |
| `cli.py` | `argparse` front-end with `check`, `toc`, and `rules` commands |

## Key design decisions

- **Mask, don't remove.** The parser blanks fenced code, inline code spans, and HTML
  comments with spaces in `Document.masked`. Columns therefore stay accurate and rules
  never mistake code samples for real links or headings.
- **Parse once.** `DocumentCache` memoises parsed files so a link rule that needs
  the headings of another file does not re-read it.
- **Rules are tiny and independent.** A rule is a class with a code, a name, a default
  severity, and a `check(doc, ctx)` generator.
- **Engine owns policy.** Rules always report; the engine decides what is enabled,
  suppressed, or promoted/demoted in severity.
- **No runtime dependencies.** Everything is standard library.

## Adding a rule

1. Pick a module in `src/mddoctor/rules/` (or create one and import it in
   `rules/__init__.py`).
2. Subclass `Rule`, set `code`, `name`, `description`, and `severity`, and implement
   `check`:

   ```python
   @register
   class NoTodo(Rule):
       code = "MDD050"
       name = "no-todo"
       description = "TODO markers should not be committed."
       severity = Severity.WARNING

       def check(self, doc, ctx):
           for number, line in enumerate(doc.masked, start=1):
               if "TODO" in line:
                   yield self.diagnostic(doc, number, line.index("TODO") + 1, "TODO found")
   ```

3. Add tests using the `run_rule` fixture from `tests/conftest.py`.
4. Run `mddoctor rules` to check that the rule shows up.

## Testing strategy

- Parser, slugs, rules, config, discovery, engine, reporters, and TOC each have a
  dedicated test module.
- `tests/test_cli.py` drives the real entry point end to end, including a subprocess
  test of `python -m mddoctor`.
- Coverage is enforced at 85% in `pyproject.toml`.
