# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `core.command`, holding the quote-aware `split_command` and the `resolve_from_env` precedence rule. Both `input/editor.py` and `output/pager.py` had carried their own private copy of the splitter. Mirrors the Rust port.
- `terminal.is_error_tty`, `terminal.output_width` and `terminal.UNCONSTRAINED_WIDTH` expose which stream a widget draws to and how wide printed output should be laid out. Mirrors the Rust port.

### Changed

- Progress indicators (`ProgressBar`, `Spinner`, `MultiProgress`) now draw on standard error rather than standard output, and only when standard error is itself a terminal. A caller piping standard output onward no longer receives animation frames in the payload. Interactive prompts and `Live` continue to draw on standard output. Mirrors the Rust port.
- `Renderable.print` and `print_to` no longer truncate when standard output is not a terminal. Previously they laid out for an invented 80 columns, so piping a wide table clipped its cells with `…` and lost data without saying so. An explicit `render(max_width)` is unaffected. Mirrors the Rust port.
- A `Card` without an explicit `width` now lays out at its natural content width when the available width is unconstrained, instead of filling it. Mirrors the Rust port.
- A blank `Pager` command override now falls through to `$PAGER` and the platform default instead of raising `ConfigError`. Blank counts as unset everywhere, which is how `$EDITOR` already behaved. An unparsable command still raises `ConfigError`. Mirrors the Rust port.

### Fixed

- `History.load` keeps only the newest `max_entries` lines instead of reading the whole file into memory. The file is foreign input and may have been written by a build with a larger limit. Mirrors the Rust port.

- `Card`, a filled counterpart to `Panel`: a colored surface with its own title and footer rows instead of a title embedded in the border. A single `accent()` derives the whole palette through HSL – the title keeps the accent saturated, the body text and both backgrounds become desaturated, darker shades of the same hue. The border is opt-in, the card fills the width it is rendered into, content wraps, and title, body and footer each take their own padding and alignment. The style setters patch the derived values rather than replacing them. Below truecolor support the backgrounds are dropped and the card renders as accented text, because the derived shades would collapse onto one ANSI-16 color. Ported from the Rust original, whose output it matches byte for byte.
- `BorderType.TALL`, a thin block border around a card's filled surface: the side bars ink a quarter of their cell's width and the top and bottom lines an eighth of their cell's height, which comes out equally thick because a terminal cell is about twice as tall as it is wide, and the horizontal lines run across the corner cells so the corners close. Only `Card` draws it natively – the bars need a filled surface to read against, all four edges use a different glyph, and the right-hand one is painted with foreground and background swapped, none of which `BorderChars` can express. Every other widget receives the `BorderType.THICK` glyphs from `BorderType.chars`.
- `Color.to_rgb` returns the 24-bit value of any color: named colors and palette indices resolve through the standard xterm palette (fixed table, 6x6x6 cube, grayscale ramp). `Color.RESET` has no fixed value and returns `None`.
- `width.wrap_line` and `width.truncate_line` are style-preserving counterparts to `wrap` and `truncate`. They keep each span's style and hyperlink, and a word straddling a span boundary stays whole instead of being wrapped apart.
- Coverage gate: `pytest` now measures branch coverage of `sparcli` and fails below the configured threshold.
- `justfile` with the full quality gate (`just check` runs lint, format, types, tests and `pip-audit`).
- Direct test coverage for `output/box.py`, `output/table/plan.py`, the key decoding primitives, persisted history and the external editor/pager command handling.

### Changed

- `sparcli.core.width` is a package: `measure` holds the plain-string helpers, `line` the style-preserving ones. Every importer keeps writing `from sparcli.core.width import ...`, and the `sparcli.width` namespace is unchanged.
- The Ruff rule set now covers the full documented list (docstrings, annotations, complexity, security, pathlib, pytest and more) instead of nine groups; every exception carries a comment explaining why.
- `InPlace` moved from `sparcli.output.live` to `sparcli.core.inplace` so that `input` no longer depends on `output`. It is still re-exported from `sparcli.output.live` and the flat `sparcli` namespace, so imports keep working.
- `TextInput` delegates suggestion handling to `sparcli.input.completion.Completion` and history recall to `sparcli.input.recall.HistoryRecall`. Public behavior and the builder API are unchanged.
- The list prompts share `sparcli.input.selection` for cursor movement, scrolling and result collection; the free-text prompts share the Ctrl-key tables and the caret keys from `sparcli.input.line_edit`.
- `ProgressBar` keeps its appearance in a `ProgressOpts` value object, mirroring how `Table` uses `TableOpts`.
- The byte-level primitives behind the terminal event source live in `sparcli.input.keydecode`.

### Fixed

- `$EDITOR`, `$VISUAL` and `$PAGER` are split with `shlex` instead of `str.split`, so an editor or pager path containing spaces no longer breaks into invalid arguments.
- A pager that cannot be spawned now raises `TerminalError` instead of a bare `FileNotFoundError`, matching how the editor already behaved.
- The history state directory is resolved to an absolute path, and an application name containing a path separator or `..` is rejected instead of being written outside the state directory.

## [0.3.0] – 2026-07-11

### Added

- `Style.remove_modifier` clears one or more attributes from a layered style (the counterpart to `add_modifier`).
- `TextInput` and `PasswordInput` gained keyword-only constructor options mirroring their fluent setters, so they configure like every other widget.
- `OutcomeKind` is re-exported from the flat `sparcli` namespace.

### Changed

- Hide the terminal hardware cursor during in-place redraws (spinner, progress, multi-progress, live) and interactive prompts, and restore it reliably on finish, on prompt exit and at interpreter exit.

### Fixed

- `DatePicker` navigation past the representable date range (before year 1 or after year 9999) no longer raises; it clamps to `date.min` / `date.max`.
- Inline markup no longer swallows a closed bracket that names no known style or attribute (such as `array[0]`); such text is emitted literally.
- `char_width` no longer raises on an empty or multi-character string.
- A negative `NumberInput.decimals` setting is clamped to zero instead of raising when the value is formatted.
- The raw-mode paths in `TerminalGuard` and the external-editor suspension now also catch `termios.error`, so a non-terminal stdin falls back to the documented no-op instead of raising (`termios.error` is not an `OSError`).
- `TextInput`'s Ctrl-G external editor now runs with raw mode suspended (cooked), matching `Textarea` and the Rust original; previously the editor launched while the terminal was still in raw mode.
- `KeyValue` rows are no longer padded with trailing spaces when there is no right margin; shorter rows stay ragged, matching the Rust original.
- Word wrapping splits on runs of whitespace (tabs, repeated spaces), matching Rust's `split_whitespace`, instead of on a single space only.
- History files are split into entries on newlines only (like Rust's `str::lines`), so an entry containing an exotic line separator is no longer split in two.

### Security

- Control characters (C0, DEL and C1, except tab) are stripped from span content and OSC-8 link URLs before they reach the terminal, so untrusted text can no longer inject escape sequences or terminate a hyperlink early.
- History files are written atomically (temp file plus rename), so a crash or a concurrent writer can no longer truncate the file.

### Documentation

- Align the minor version with the Rust `sparcli` port (both at 0.3.x); the two ports now track the same minor number.
- Add `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `TODO.md`, README badges and editor/VCS tooling configs (`.editorconfig`, `.gitattributes`); migrate packaging metadata to an SPDX license expression and expand the project URLs for PyPI.

### Notes

- `DatePicker`'s initial "today" uses the local date here, while the Rust original uses UTC (it stays dependency-free). This one-point divergence is intentional; near midnight the default day can differ by one between the two ports.

## [0.1.0] – 2026-07-10

### Added

- Initial release: idiomatic Python port of the Rust `sparcli` library.
- Styled output widgets: `Panel`, `Table`, `List`, `Rule`, `Alert`, `Badge`, `Columns`, `Tree`, `KeyValue`, `Diff`, `Spinner`, `ProgressBar`, `MultiProgress`, `Live`, `Pager`.
- Interactive input widgets: `TextInput`, `PasswordInput`, `NumberInput`, `Confirm`, `Select`, `FuzzySelect`, `DatePicker`, `Textarea`.
- Unified `Theme`, inline `markup`, width utilities, terminal capability detection, validators, shortcuts and command history.
- Dependency-free (standard library only).

[Unreleased]: https://github.com/cgroening/py-sparcli/compare/v0.3.0...HEAD [0.3.0]: https://github.com/cgroening/py-sparcli/compare/v0.1.0...v0.3.0 [0.1.0]: https://github.com/cgroening/py-sparcli/releases/tag/v0.1.0
