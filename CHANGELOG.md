# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Hide the terminal hardware cursor during in-place redraws (spinner, progress,
  multi-progress, live) and interactive prompts, and restore it reliably on
  finish, on prompt exit and at interpreter exit.

### Fixed

- `TextInput`'s Ctrl-G external editor now runs with raw mode suspended
  (cooked), matching `Textarea` and the Rust original; previously the editor
  launched while the terminal was still in raw mode.
- `KeyValue` rows are no longer padded with trailing spaces when there is no
  right margin; shorter rows stay ragged, matching the Rust original.
- Word wrapping splits on runs of whitespace (tabs, repeated spaces), matching
  Rust's `split_whitespace`, instead of on a single space only.
- History files are split into entries on newlines only (like Rust's
  `str::lines`), so an entry containing an exotic line separator is no longer
  split in two.

### Notes

- `DatePicker`'s initial "today" uses the local date here, while the Rust
  original uses UTC (it stays dependency-free). This one-point divergence is
  intentional; near midnight the default day can differ by one between the two
  ports.

## [0.1.0] – 2026-07-10

### Added

- Initial release: idiomatic Python port of the Rust `sparcli` library.
- Styled output widgets: `Panel`, `Table`, `List`, `Rule`, `Alert`, `Badge`,
  `Columns`, `Tree`, `KeyValue`, `Diff`, `Spinner`, `ProgressBar`,
  `MultiProgress`, `Live`, `Pager`.
- Interactive input widgets: `TextInput`, `PasswordInput`, `NumberInput`,
  `Confirm`, `Select`, `FuzzySelect`, `DatePicker`, `Textarea`.
- Unified `Theme`, inline `markup`, width utilities, terminal capability
  detection, validators, shortcuts and command history.
- Dependency-free (standard library only).

[Unreleased]: https://github.com/cgroening/py-sparcli/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cgroening/py-sparcli/releases/tag/v0.1.0
