"""
sparcli.errors
==============

Defines the exception hierarchy raised across the library.

All errors derive from :class:`SparcliError`, so callers can catch the whole
family with a single ``except SparcliError``. More specific subclasses carry
context about what went wrong: terminal I/O, a missing interactive terminal or
invalid configuration.
"""

from __future__ import annotations


class SparcliError(Exception):
    """Base class for every error raised by sparcli."""


class TerminalError(SparcliError):
    """Raised when reading from or writing to the terminal fails."""


class NoTerminalError(SparcliError):
    """Raised when an interactive prompt runs without a usable terminal."""

    def __init__(
        self, message: str = "no interactive terminal available"
    ) -> None:
        super().__init__(message)


class ConfigError(SparcliError):
    """Raised when a widget or prompt is configured with invalid options."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"invalid configuration: {detail}")
        self.detail = detail
