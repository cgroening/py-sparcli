# CLAUDE.md – sparcli (Python)

Requirements for all future sessions in this project. On conflict, this file takes precedence over general conventions, but not over explicit user instructions. The global style guide (`~/.claude/CLAUDE.md` → §12 Python) applies additionally; this file refines and overrides it wherever it is more specific.

## What is this?

`sparcli` is a **lightweight, cross-platform** toolkit (macOS, Windows, Linux) for **styled CLI output** and **interactive single-input widgets** – an **idiomatic, dependency-free Python reimplementation** of the Rust library `sparcli`. Guiding idea: small, for little CLI tools. No async, no rich/textual/prompt_toolkit, minimal footprint.

- **Foundation:** a custom ANSI renderer built directly on the standard library (no framework).
- **API feel:** ratatui-familiar vocabulary (`Style`, `Color`, `Span`, `Line`, `Text`, `Modifier`); **both** a keyword constructor **and** fluent builder methods per widget.
- **Scope:** output is complete; input covers single widgets only (no form/app/args). Fuzzy is only an inline select.
- **Rust original is the SSOT for behavior:** `/Users/cgroening/Developer/Rust/ libs/sparcli`. For behavior questions, check there and preserve parity.

## Rust parity (mandatory)

- The Rust version lives at `/Users/cgroening/Developer/Rust/libs/sparcli`.
- **On every change, check whether the same change also has to be made in the Rust version** (behavior, API, docs, examples) to keep both in parity.
- When such a change might be needed, **ask the user** whether it should be carried over to the Rust version instead of deciding silently.
- **Version sync:** the Python and Rust ports keep their **minor version in sync** (at minimum the minor number matches). On a release, bump this port to the Rust port's minor. This is why the Python port jumped 0.1.0 -> 0.3.0 to meet Rust `sparcli` v0.3.
- **Known intentional divergence:** `DatePicker`'s initial "today" uses the **local** date here (`datetime.date.today`), while the Rust version uses **UTC** (it has no local-time API without a dependency, and both stay dependency-free). Near midnight the default day can differ by one between the two ports. Do not "fix" this into parity without user sign-off.

## Distribution & import

- PyPI distribution name: **`py-sparcli`** (the name `sparcli` is taken).
- Import name: **`import sparcli`**.
- Build backend: hatchling, static version in `pyproject.toml`, `[tool.hatch.build.targets.wheel] packages = ["sparcli"]`, ships `py.typed`.

## Architecture (keep the layers strictly separated)

- `core/` – foundation: style, color, text, render, geometry, border, theme, width, terminal, markup, `inplace` (the redraw engine). No widget logic.
- `output/` – printable widgets, subclass `Renderable` (`render(max_width) -> Rendered`). Shared helpers: `layout`, `compose`, `box`, `live`.
- `input/` – interactive prompts over `EventSource` (DI) + the `prompt.run_prompt` loop and `prompt.run_on_terminal` guard + `line_edit.LineEditor` (SSOT for text editing, plus the shared `CTRL_ACTIONS` tables and `apply_caret_key`) + `field` (rendering). The prompts are composed from small collaborators: `completion.Completion`, `recall.HistoryRecall`, `selection.SelectionCursor` and the `keydecode` byte primitives.
- **Dependency direction:** `output`/`input` → `core`. Never cyclic, never `core` → widget layer, and never `input` → `output` (this is why `InPlace` lives in `core/inplace.py`; `output/live.py` re-exports it for the public API).
- **A single unified theme** in `core/theme.py` drives both input and output.
- The public API is re-exported flat (`from sparcli import ...`, 81 symbols) plus the namespaces `sparcli.width/terminal/markup/event/validate/shortcut`. Every `__init__.py` carries an explicit `__all__` list.

## Dependencies

- **Zero runtime dependencies – standard library only.** Do not add a new runtime dependency without first checking with the user.
- Deliberate stdlib decisions (do not soften them):
  - Display width via `unicodedata` (no `wcwidth`).
  - DatePicker via `datetime.date`/`calendar` (no hand-rolled date class).
  - Fuzzy scorer written by hand (no `nucleo`/`rapidfuzz`).
  - Terminal raw mode / key parsing via `termios`/`tty` + `msvcrt`.
- `markup`, `fuzzy` and `pager` are always included (no feature flags/extras).

## Style & tooling

- Target Python: **3.12+** (`requires-python = ">=3.12"`).
- **Strings: double quotes `"..."`** everywhere, including nested inside f-strings (PEP 701). Enforced via the `Q` lint rules with `inline-quotes = "double"` and `avoid-escape = false`; the formatter uses `quote-style = "preserve"` so it cannot rewrite the nested case back to single quotes. `repr` outputs in doctests keep their single quotes, because that is what Python prints.
- **Formatting/linting:** `ruff` (format + lint), running the full rule set from the style guide. 80-character lines, enforced (`E501` is on). Imports isort-sorted (stdlib → third-party → local). `from __future__ import annotations` as the first line of every module. Every entry in the `ignore` list carries a comment saying why.
- **Docstrings:** NumPy convention. The fluent builder setters keep a single-line docstring instead of full `Parameters`/`Returns` blocks – they take one argument and return `self`, so the blocks would add length without information. Full blocks are required everywhere else.
- **Type checking:** `basedpyright` in **strict** mode must report 0 errors. Complete, modern type hints (`X | None`, builtin generics, PEP 695).
- No em dash; straight quotes/apostrophes; named constants instead of magic numbers/strings.

Commands (from the project root):

```bash
just check      # the full gate: lint, format, types, tests, pip-audit
just fix        # ruff check --fix . && ruff format .
```

Individually, if `just` is unavailable:

```bash
ruff check --fix . && ruff format .
basedpyright sparcli examples
python -m pytest -q          # includes doctests and the branch-coverage gate
pip-audit .
```

## API conventions (idiomatic)

- Widgets: regular classes with `__slots__`, subclass `Renderable`, a keyword constructor (`*` keyword-only options) **and** fluent builder methods that mutate `self` and return it. `Rendered` is itself a `Renderable`.
- Value types (`Style`, `Color`, `Edges`, `Title`, `BorderChars`, `Theme`) as `@dataclass(frozen=True, slots=True)` or `enum.Enum`; enums instead of magic strings.
- Interfaces as `ABC` + `@abstractmethod` (`Renderable`, `EventSource`); DI via constructor/parameters.
- Docstrings in NumPy style with an RST-title module docstring; public items get `Parameters`/`Returns`/`Examples`, third-person present ("Returns…").
- Keep functions small (SRP), ≤ 3 parameters (otherwise bundle into an options/state object), guard clauses, at most 2 levels of nesting.

## Error handling

- Exception hierarchy in `sparcli/errors.py`: `SparcliError` (base) with `TerminalError`, `NoTerminalError`, `ConfigError`. Wrap foreign errors sensibly.
- **No `assert` for validation** (stripped under `-O`). Do not return `None` for "no result"; use an empty collection, a special-case object, or an exception. (Parser optionals such as `Color.from_hex -> Color | None` are the documented exception.)
- Prompts return `Outcome[T]` (`submitted`/`cancelled`/`shortcut`), not a cancel exception.
- `TerminalGuard` (context manager, RAII) restores raw mode / bracketed paste on exit or error.
- **Logging:** only `logging.getLogger(__name__)` and only `warning`/`debug` where a result would otherwise be silently swallowed (terminal restore, history load/save, temp cleanup). Do not ship a logger/backend; nothing in render/event loops; real errors come back via `SparcliError`.
- `subprocess` only with an argument list (never `shell=True`/`os.system`); use `tempfile` safely; honor `NO_COLOR`/non-TTY.

## Look

- Muted look, a single accent tone, `dim` for secondary text. Default border `Rounded`; truncate overflow with `…`.
- Glyphs in two tiers (Unicode + ASCII fallback), selected via the theme.
- Selection lists navigate cyclically; honor `NO_COLOR` and non-TTY (then plain, no ANSI codes, no OSC-8).

## Tests – mandatory

- `pytest`; tests in `tests/`, grouped in `class TestXxx`; test names describe the expected behavior; prefer fakes over mocks.
- **Output:** render to `Rendered` and assert on `plain()` or ANSI-stripped content and styles (no TTY).
- **Input:** drive headlessly via `event.ScriptedSource` (scripted keys) + `run_with(source)` and assert on the `Outcome`.
- Doctests in `# Examples` count as tests (`--doctest-modules`) and must pass. `repr` expected-outputs keep single quotes.
- Test override: `SPARCLI_NO_TTY=1` forces non-TTY.
- **Run all tests after every change** and keep ruff + basedpyright clean.
- Shared helpers and fixtures live in `tests/conftest.py` (`plain_lines`, `joined`, `render_to_string`, the theme reset and the `state_home` fixture). Import them as `from conftest import ...`.
- Branch coverage is measured on every run and gated by `fail_under` in `[tool.coverage.report]`. Do not lower it to make a change pass.

## Environment variables

`NO_COLOR` (disables color), `CLICOLOR_FORCE` (forces color), `COLORTERM` (truecolor/24bit → TrueColor), `SPARCLI_NO_TTY` (test override, non-TTY).

## Docs / maintenance

- On changes, update README.md, `docs/DEVELOPMENT.md`, CHANGELOG.md, docstrings and tests together. The CHANGELOG follows Keep a Changelog + SemVer.
- Keep the `examples/` (five counterparts to the Rust version, including the two README generators `output_readme.py`/`prompt_readme.py` via `frame()`) current on API changes.
- Remove dead/commented-out code; fix the cause, not the symptom.

## Git

- **No commits on your own.** At the end of a change, suggest a commit title (English, imperative, Conventional Commits).
