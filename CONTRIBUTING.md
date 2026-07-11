# Contributing to sparcli

Thanks for your interest in improving `sparcli`. This is a small, dependency-free library, so the workflow is deliberately lightweight.

## Getting started

The full build, test and lint workflow lives in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md). In short:

```bash
pip install -e .
pip install ruff basedpyright pytest   # or: uv sync --group dev

python -m pytest -q            # tests + doctests
ruff check .                   # lint
ruff format --check .          # formatting (drop --check to apply)
basedpyright sparcli examples  # strict type checking
```

All three checks must be clean before a change is ready. Optionally, install the pre-commit hooks to run linting, formatting and type checks automatically:

```bash
pre-commit install          # once
pre-commit run --all-files  # on demand
```

## Ground rules

- **Target Python 3.12+.** The code uses PEP 695 generics and `type` statements.
- **Zero runtime dependencies.** Do not add a runtime dependency; the standard library only. Open an issue first if you think one is unavoidable.
- **Style gates** (enforced by `ruff` and `basedpyright`): 80-column lines, double-quoted strings, isort-ordered imports, complete modern type hints, and `basedpyright` strict with zero errors.
- **Layering.** `output/` and `input/` depend on `core/`, never the reverse, and `core/` depends on nothing internal.
- **Tests are mandatory.** Add headless tests under `tests/` following the patterns in `docs/DEVELOPMENT.md`; doctests in `# Examples` count as tests.
- **Docs travel with code.** Update `README.md`, `CHANGELOG.md`, docstrings and, where relevant, the `examples/` gallery in the same change.

The "Adding a widget" checklist in `docs/DEVELOPMENT.md` walks through a typical contribution end to end.

## Rust parity

`sparcli` is an idiomatic port of the Rust library at a matching version (the two ports keep their **minor version in sync**). The Rust original is the source of truth for behavior. When a change affects behavior, API or docs, note in your PR whether the same change should be mirrored to the Rust port.

## Commits and pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org/) for commit titles (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`), imperative mood, English.
- Add a `CHANGELOG.md` entry under `## [Unreleased]` (Keep a Changelog format).
- Keep pull requests focused; describe the behavior change and how you verified it.

## Reporting bugs and security issues

- Regular bugs and feature requests: open a [GitHub issue](https://github.com/cgroening/py-sparcli/issues).
- Security vulnerabilities: **do not** open a public issue; follow [`SECURITY.md`](SECURITY.md).

By contributing you agree that your contributions are licensed under the project's [MIT license](LICENSE).
