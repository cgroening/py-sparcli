# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
