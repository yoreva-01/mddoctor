# Contributing to mddoctor

Thanks for your interest! This is a small, friendly project.

## Development setup

Requires Python 3.11 or newer.

```bash
git clone https://github.com/baldeaguirre/mddoctor.git
cd mddoctor
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Checks to run before opening a pull request

```bash
ruff check .
ruff format --check .
pytest --cov
python -m mddoctor check README.md docs CONTRIBUTING.md
```

CI runs the same commands on Linux, macOS, and Windows.

## Guidelines

- Use [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `ci:`, `chore:`.
- Add or update tests for every behavior change.
- Keep the project dependency-free at runtime unless there is a strong reason.
- Prefer small, readable code over clever code.
- New lint rules live in `src/mddoctor/rules/`; see
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#adding-a-rule).

## Reporting bugs

Please include the Markdown snippet that triggers the problem, the command you
ran, the output you expected, and the output you got.
