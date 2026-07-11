"""
sparcli.core.cursor
==================

Hides and restores the terminal hardware cursor around in-place redraws.

During spinner and progress animations, and during interactive prompts, the
library rewrites frames in place; a blinking hardware cursor at the end of a
frame is distracting, and prompts draw their own styled cursor anyway. These
helpers hide the cursor on the first request and restore it on the last, both
idempotently, and register an :mod:`atexit` handler so the cursor is always
shown again when the process exits (even after an unhandled exception).
"""

from __future__ import annotations

import atexit
import sys

_HIDE = "\x1b[?25l"
_SHOW = "\x1b[?25h"

_hidden = False
_atexit_registered = False


def hide() -> None:
    """Hides the terminal cursor once; a no-op if already hidden."""
    global _hidden, _atexit_registered
    if _hidden:
        return
    _write(_HIDE)
    _hidden = True
    if not _atexit_registered:
        atexit.register(show)
        _atexit_registered = True


def show() -> None:
    """Restores the terminal cursor if it was hidden; a no-op otherwise."""
    global _hidden
    if not _hidden:
        return
    _write(_SHOW)
    _hidden = False


def is_hidden() -> bool:
    """Returns whether the cursor is currently hidden by this module."""
    return _hidden


def _write(escape: str) -> None:
    """Writes an escape to stdout, ignoring closed-stream errors at shutdown."""
    try:
        sys.stdout.write(escape)
        sys.stdout.flush()
    except (OSError, ValueError):
        pass
