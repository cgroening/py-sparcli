# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Coverage gate: `pytest` now measures branch coverage of `sparcli` and fails below the configured threshold.
- `justfile` with the full quality gate (`just check` runs lint, format, types, tests and `pip-audit`).
- Direct test coverage for `output/box.py`, `output/table/plan.py`, the key decoding primitives, persisted history and the external editor/pager command handling.

### Changed

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
