# Development

How to build, test and work on `sparcli`. This is a dependency-free Python library, so the toolchain is small and everything runs headless.

## Prerequisites

- Python 3.12 or newer (the code uses PEP 695 generics and `type` statements).
- The dev tools `ruff`, `basedpyright` and `pytest`. No runtime dependencies and no system dependencies beyond a terminal.

Install the package in editable mode together with the dev tools:

```bash
pip install -e .
pip install ruff basedpyright pytest
```

## Test

The whole suite is headless: output widgets render to an in-memory `Rendered` block and are asserted on their visible text, and input prompts are driven by a scripted fake event source. No test needs a real terminal, so it is safe to run in CI.

```bash
python -m pytest -q
```

The pytest configuration in `pyproject.toml` also runs docstring examples (`--doctest-modules`) across the package and ignores the `examples/` directory. A few focused runs:

```bash
python -m pytest tests/test_table.py       # one test module
python -m pytest -k fuzzy                   # tests whose name contains "fuzzy"
python -m pytest --no-header -q             # quieter output
```

## Lint and type-check

```bash
ruff check .            # lint
ruff format --check .   # formatting (drop --check to apply)
basedpyright sparcli    # strict type checking
```

Both `ruff check` and `basedpyright` must be clean. The project targets strict typing: every public item is annotated, and `ruff` enforces single quotes, an 80-column line length (the `E501` long-line rule is relaxed because rendered strings and docstrings sometimes exceed it) and an import ordering.

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
            width, terminal, render. No widget logic.
  output/   Printable widgets implementing Renderable.
  input/    Interactive prompts over an EventSource, plus the shared line
            editor, terminal guard and prompt driver.
  errors.py The SparcliError hierarchy.
examples/   Runnable demos (output_gallery, output_dynamic, prompts,
            output_readme, prompt_readme).
tests/      Headless tests over the public API.
docs/       This document.
```

The public API is the curated set re-exported at the package root (`sparcli/__init__.py`), plus the facade submodules `sparcli.markup`, `sparcli.validate`, `sparcli.event`, `sparcli.shortcut`, `sparcli.width` and `sparcli.terminal`.

## Dependency direction

The dependency direction is strictly one-way: `output` and `input` depend on `core`, never the reverse, and `core` depends on nothing internal. Keep it that way when adding code – a `core` module must not import from `output` or `input`. This keeps the foundation reusable and the layering easy to reason about.

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
    rendered = Table().columns(['A', 'B']).row(['1', '2']).render(80)
    lines = [line.plain() for line in rendered.lines]
    assert 'A' in lines[1] and 'B' in lines[1]
```

Input prompts are driven headlessly through `run_with(source)`, where the source is a `ScriptedSource` of queued keys. The scripted source auto-cancels on exhaustion, so a prompt can never loop forever in a test:

```python
from sparcli.input.event import KeyCode, ScriptedSource
from sparcli import TextInput

def test_types_and_submits() -> None:
    source = ScriptedSource.keys([KeyCode.char('h'), KeyCode.char('i'), KeyCode.ENTER])
    outcome = TextInput('Name').run_with(source)
    assert outcome.value == 'hi'
```

## Adding a widget

1. Add the module under `sparcli/output/` (a `Renderable`) or `sparcli/input/` (a prompt with a `run` / `run_with` / `frame` trio built on the shared `run_prompt` driver).
2. Keep the dependency direction: import only from `core` (and, within a layer, sibling helpers). Never import `output` or `input` from `core`.
3. Add unit tests under `tests/`, following the patterns above. Name tests for the behavior they assert.
4. Re-export the public type from `sparcli/__init__.py` and add it to `__all__`; free-function utilities go into the relevant facade submodule.
5. Run `python -m pytest -q`, `ruff check .`, `ruff format .` and `basedpyright sparcli` until clean.
6. Add a docstring to every public item (with a `# Examples` doctest where the usage is not obvious) and update `README.md` and, if relevant, the example gallery.
