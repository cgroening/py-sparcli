# Development

How to build, test and work on `sparcli`. This is a dependency-free Python library, so the toolchain is small and everything runs headless.

## Prerequisites

- Python 3.12 or newer (the code uses PEP 695 generics and `type` statements).
- The dev tools `ruff`, `basedpyright`, `pytest` and `pytest-cov`, plus `pip-audit` and `pre-commit`. No runtime dependencies and no system dependencies beyond a terminal.
- Optionally [`just`](https://github.com/casey/just), which runs the whole gate in one command.

Install the package in editable mode together with the dev tools:

```bash
pip install -e .
pip install --group dev
```

## The quality gate

The `justfile` is the single definition of what has to pass:

```bash
just check      # lint, format, types, tests and pip-audit
just fix        # apply what ruff can repair on its own
just hooks      # install the pre-commit hooks once per clone
```

Everything below spells out the individual steps that `just check` bundles.

## Test

The whole suite is headless: output widgets render to an in-memory `Rendered` block and are asserted on their visible text, and input prompts are driven by a scripted fake event source. No test needs a real terminal, so it is safe to run in CI.

```bash
python -m pytest -q
```

The pytest configuration in `pyproject.toml` also runs docstring examples (`--doctest-modules`) across the package, ignores the `examples/` directory, turns warnings into errors and measures branch coverage. The run fails if coverage drops below the `fail_under` threshold in `[tool.coverage.report]`. A few focused runs:

```bash
python -m pytest tests/test_table.py       # one test module
python -m pytest -k fuzzy                   # tests whose name contains "fuzzy"
python -m pytest --no-header -q             # quieter output
```

## Lint and type-check

```bash
ruff check .                  # lint
ruff format --check .         # formatting (drop --check to apply)
basedpyright sparcli examples # strict type checking
```

Both `ruff check` and `basedpyright` must be clean. The project targets strict typing: every public item is annotated, and `ruff` runs the full documented rule set, including docstring style (NumPy convention), annotations, complexity, security (`flake8-bandit`), `pathlib` usage and import ordering. Line length is enforced at 80 columns.

Every entry in the `ignore` list in `pyproject.toml` carries a comment saying why it is there. The two that most often surprise newcomers: `D401` is off because the style guide mandates third-person docstring summaries ("Returns ...") where that rule wants the imperative, and `FBT001`/`FBT002` are off because the fluent builder API takes booleans by design (`Table.striped(True)`) to mirror the Rust port.

Dependencies are audited separately:

```bash
pip-audit .
```

## Run the examples

```bash
python examples/output_gallery.py   # every static output widget
python examples/output_dynamic.py   # spinner, progress, multi-progress, live, pager
python examples/prompts.py          # every interactive prompt (needs a real TTY)
python examples/output_readme.py    # the output showcase collage
python examples/prompt_readme.py    # the input showcase, via frame()
```

Piping the static examples (`| cat`, `> file`) or setting `NO_COLOR=1` yields plain text with no escape codes. The `output_dynamic.py` animations become no-ops off a terminal, printing only the final frame.

## Project layout

```text
sparcli/
  core/     Foundation: color, style, text, markup, theme, border, geometry,
            width, terminal, render, inplace. No widget logic.
  output/   Printable widgets implementing Renderable.
  input/    Interactive prompts over an EventSource, plus the shared line
            editor, terminal guard, prompt driver and the collaborators the
            prompts are composed from: completion, recall, selection and the
            keydecode primitives.
  errors.py The SparcliError hierarchy.
examples/   Runnable demos (output_gallery, output_dynamic, prompts,
            output_readme, prompt_readme).
tests/      Headless tests over the public API; shared helpers and fixtures
            live in tests/conftest.py.
docs/       This document.
```

The public API is the curated set re-exported at the package root (`sparcli/__init__.py`), plus the facade submodules `sparcli.markup`, `sparcli.validate`, `sparcli.event`, `sparcli.shortcut`, `sparcli.width` and `sparcli.terminal`.

## Dependency direction

The dependency direction is strictly one-way: `output` and `input` depend on `core`, never the reverse, and `core` depends on nothing internal. `input` must not depend on `output` either, which is why the in-place redraw engine `InPlace` lives in `sparcli.core.inplace` rather than next to `Live`. Keep it that way when adding code – a `core` module must not import from `output` or `input`. This keeps the foundation reusable and the layering easy to reason about.

## Environment variables

sparcli honors the common terminal environment variables plus one test override:

- `NO_COLOR` disables all color output.
- `CLICOLOR_FORCE` forces color even when output is not a terminal.
- `SPARCLI_NO_TTY` forces "no terminal" behavior; used to produce deterministic captures and to exercise the non-interactive paths in tests.

## Testing patterns

There are two patterns, one per layer.

Output widgets render to a `Rendered` block and are asserted on their plain text (or on span styles). No terminal is involved:

```python
from sparcli import Table

def test_table_has_a_header_row() -> None:
    rendered = Table().columns(["A", "B"]).row(["1", "2"]).render(80)
    lines = [line.plain() for line in rendered.lines]
    assert "A" in lines[1]
    assert "B" in lines[1]
```

Input prompts are driven headlessly through `run_with(source)`, where the source is a `ScriptedSource` of queued keys. The scripted source auto-cancels on exhaustion, so a prompt can never loop forever in a test:

```python
from sparcli.input.event import KeyCode, ScriptedSource
from sparcli import TextInput

def test_types_and_submits() -> None:
    source = ScriptedSource.keys(
        [KeyCode.char("h"), KeyCode.char("i"), KeyCode.ENTER]
    )
    outcome = TextInput("Name").run_with(source)
    assert outcome.value == "hi"
```

## Adding a widget

1. Add the module under `sparcli/output/` (a `Renderable`) or `sparcli/input/` (a prompt with a `run` / `run_with` / `frame` trio built on the shared `run_prompt` driver).
2. Keep the dependency direction: import only from `core` (and, within a layer, sibling helpers). Never import `output` or `input` from `core`.
3. Add unit tests under `tests/`, following the patterns above. Name tests for the behavior they assert.
4. Re-export the public type from `sparcli/__init__.py` and add it to `__all__`; free-function utilities go into the relevant facade submodule.
5. Run `just check` until clean (or the individual commands above).
6. Add a docstring to every public item (with a `# Examples` doctest where the usage is not obvious) and update `README.md` and, if relevant, the example gallery.
