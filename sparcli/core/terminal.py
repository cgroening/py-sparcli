"""
sparcli.core.terminal
=====================

Detects terminal capabilities and size.

The functions here answer three questions the renderer and prompts need: how
wide is the terminal, is standard output (or input) an interactive TTY, and how
much color can be emitted. Behaviour honours the widely supported environment
variables ``NO_COLOR``, ``CLICOLOR_FORCE`` and ``COLORTERM``, plus the test-only
override ``SPARCLI_NO_TTY``.
"""

from __future__ import annotations

import enum
import os
import shutil
import sys

DEFAULT_WIDTH = 80
DEFAULT_HEIGHT = 24

_NO_COLOR = "NO_COLOR"
_CLICOLOR_FORCE = "CLICOLOR_FORCE"
_COLORTERM = "COLORTERM"
_NO_TTY_OVERRIDE = "SPARCLI_NO_TTY"

#: Width standing for "no limit at all": widgets lay out at their natural
#: content width, because there is no terminal to fit into.
UNCONSTRAINED_WIDTH = 2**31 - 1


class ColorSupport(enum.Enum):
    """How much color the current output stream can display."""

    NONE = enum.auto()
    ANSI16 = enum.auto()
    TRUECOLOR = enum.auto()


def terminal_size() -> tuple[int, int]:
    """
    Returns the terminal size as a ``(width, height)`` column/row pair.

    Returns
    -------
    tuple[int, int]
        The terminal width and height, falling back to ``(80, 24)`` when the
        size cannot be determined.
    """
    try:
        size = shutil.get_terminal_size(
            fallback=(DEFAULT_WIDTH, DEFAULT_HEIGHT)
        )
    except (ValueError, OSError):
        return (DEFAULT_WIDTH, DEFAULT_HEIGHT)
    return (size.columns, size.lines)


def term_width() -> int:
    """Returns the terminal width in columns."""
    return terminal_size()[0]


def term_height() -> int:
    """Returns the terminal height in rows."""
    return terminal_size()[1]


def is_output_tty() -> bool:
    """Returns whether standard output is an interactive terminal."""
    return not _no_tty_override() and _isatty(sys.stdout)


def is_error_tty() -> bool:
    """Returns whether standard error is an interactive terminal."""
    return not _no_tty_override() and _isatty(sys.stderr)


def output_width() -> int:
    """
    Returns the width printed output should be laid out for.

    At a terminal this is its width. Without one there is no width to respect,
    and clipping to an invented default would drop data from a pipe silently,
    so layout is left unconstrained.

    Returns
    -------
    int
        The terminal width, or :data:`UNCONSTRAINED_WIDTH` off a terminal.
    """
    return term_width() if is_output_tty() else UNCONSTRAINED_WIDTH


def is_input_tty() -> bool:
    """
    Returns whether both standard input and output are interactive terminals.

    Prompts require input and output to be a TTY; either being redirected means
    the prompt cannot run interactively.
    """
    return not _no_tty_override() and _isatty(sys.stdin) and _isatty(sys.stdout)


def color_support() -> ColorSupport:
    """
    Returns the color support level for the current output stream.

    Returns
    -------
    ColorSupport
        ``NONE`` when color is disabled (``NO_COLOR`` or a non-TTY without
        ``CLICOLOR_FORCE``), ``TRUECOLOR`` when ``COLORTERM`` advertises 24-bit
        color, otherwise ``ANSI16``.
    """
    if _NO_COLOR in os.environ:
        return ColorSupport.NONE
    if not _env_enabled(_CLICOLOR_FORCE) and not is_output_tty():
        return ColorSupport.NONE
    if _colorterm_truecolor():
        return ColorSupport.TRUECOLOR
    return ColorSupport.ANSI16


def _isatty(stream: object) -> bool:
    """Returns whether a stream reports itself as a TTY, defensively."""
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except (ValueError, OSError):
        return False


def _no_tty_override() -> bool:
    """Returns whether the SPARCLI_NO_TTY test override forces a non-TTY."""
    return _env_enabled(_NO_TTY_OVERRIDE)


def _env_enabled(key: str) -> bool:
    """Returns whether an env var is set to a non-empty value other than '0'."""
    value = os.environ.get(key)
    return value is not None and value not in {"", "0"}


def _colorterm_truecolor() -> bool:
    """Returns whether COLORTERM advertises truecolor / 24-bit support."""
    value = os.environ.get(_COLORTERM, "").lower()
    return "truecolor" in value or "24bit" in value
