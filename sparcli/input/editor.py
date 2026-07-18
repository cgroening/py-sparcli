"""
sparcli.input.editor
====================

Defines external-editor integration (``$VISUAL`` / ``$EDITOR``).

:func:`edit_file` opens an editor on a path; :func:`edit_text` round-trips a
string through a temp file. The editor command comes from an explicit override,
then ``$VISUAL``, then ``$EDITOR``, then a platform default (``vi`` on POSIX,
``notepad`` on Windows). The command is split on whitespace and spawned as an
argument list - never through a shell - so no input is ever interpreted by one.
:func:`suspended_raw_mode` cooks the terminal around such a spawn, so the child
editor sees a canonical terminal rather than the prompt's raw mode.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sparcli.errors import ConfigError, SparcliError, TerminalError

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)

# Indices into a termios attribute list ``[iflag, oflag, cflag, lflag, ...]``.
_IFLAG = 0
_OFLAG = 1
_LFLAG = 3


def edit_file(command: str | None, path: Path) -> None:
    """
    Opens an external editor on ``path``, blocking until it exits.

    Parameters
    ----------
    command : str | None
        An explicit editor command, or ``None`` to resolve from the
        environment. Split on whitespace; the path is appended as a final
        argument.
    path : Path
        The file to edit.

    Raises
    ------
    ConfigError
        If the resolved editor command is empty.
    TerminalError
        If the editor cannot be spawned.
    """
    parts = _split_command(_resolve_command(command))
    if not parts:
        raise ConfigError("empty editor command")
    argv = [*parts, str(path)]
    try:
        subprocess.run(argv, check=False)  # noqa: S603
    except OSError as error:
        raise TerminalError(f"could not launch editor: {error}") from error


def edit_text(command: str | None, initial: str, suffix: str) -> str:
    """
    Edits ``initial`` in an external editor via a temp file.

    Parameters
    ----------
    command : str | None
        An explicit editor command, or ``None`` to resolve from the
        environment.
    initial : str
        The starting contents.
    suffix : str
        The temp-file extension (e.g. ``.md``) for editor syntax detection.

    Returns
    -------
    str
        The edited contents.

    Raises
    ------
    ConfigError
        If the resolved editor command is empty.
    TerminalError
        If the editor cannot be spawned or the temp file cannot be handled.
    """
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="sparcli-")
    path = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(initial)
        edit_file(command, path)
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise TerminalError(f"could not edit temp file: {error}") from error
    finally:
        _remove_quietly(path)


def _split_command(command: str) -> list[str]:
    """
    Splits a command line into argv, honoring quotes.

    Uses :func:`shlex.split` rather than :meth:`str.split` so an editor path
    containing spaces (``/Applications/Sublime Text/subl``) survives intact.
    The result feeds :func:`subprocess.run` as an argument list, never a
    shell, so no quoting can turn into command injection.

    Parameters
    ----------
    command : str
        The command line as configured or taken from the environment.

    Returns
    -------
    list[str]
        The argv parts, empty when the command is blank or unbalanced.
    """
    try:
        return shlex.split(command)
    except ValueError:
        logger.debug("could not parse editor command: %r", command)
        return []


def _resolve_command(command: str | None) -> str:
    """Resolves the editor command from the override or environment."""
    if command is not None and command.strip():
        return command
    for key in ("VISUAL", "EDITOR"):
        value = os.environ.get(key)
        if value is not None and value.strip():
            return value
    return _default_editor()


def _default_editor() -> str:
    """Returns the platform's fallback editor."""
    return "notepad" if sys.platform == "win32" else "vi"


def _remove_quietly(path: Path) -> None:
    """Removes a temp file, logging (not raising) on failure."""
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        logger.debug("could not remove temp file %s: %s", path, error)


@contextlib.contextmanager
def suspended_raw_mode() -> Generator[None]:
    """
    Cooks the terminal for the duration of the ``with`` block.

    Restores canonical input, echo and signal handling so a spawned child
    process (such as ``$EDITOR``) sees a normal terminal, then reinstates the
    prompt's raw mode on exit. A no-op off POSIX or when the terminal state
    cannot be read.

    Examples
    --------
    >>> with suspended_raw_mode():
    ...     pass
    """
    saved = _suspend_raw()
    try:
        yield
    finally:
        _resume_raw(saved)


def _suspend_raw() -> tuple[int, list[Any]] | None:
    """Switches the terminal to cooked mode, returning the saved state."""
    if sys.platform == "win32":
        return None
    import termios  # available on every non-win32 platform

    try:
        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        termios.tcsetattr(fd, termios.TCSADRAIN, _cooked_mode(saved))
    except (OSError, ValueError, termios.error):
        return None
    return (fd, saved)


def edit_or_none(command: str | None, text: str, suffix: str) -> str | None:
    """
    Round-trips ``text`` through the external editor, swallowing failures.

    Raw mode is suspended for the duration so the editor owns the terminal.
    A failing editor must never take the prompt down with it, so any
    :class:`~sparcli.errors.SparcliError` is logged at debug level and
    reported as "no change".

    Parameters
    ----------
    command : str | None
        The editor command, or ``None`` to fall back to the environment.
    text : str
        The text handed to the editor.
    suffix : str
        The temporary file suffix, which selects the editor's syntax mode.

    Returns
    -------
    str | None
        The edited text, or ``None`` when the editor failed.
    """
    try:
        with suspended_raw_mode():
            return edit_text(command, text, suffix)
    except SparcliError as error:
        logger.debug("external editor failed: %s", error)
        return None


def _cooked_mode(mode: list[Any]) -> list[Any]:
    """Returns a copy of ``mode`` with canonical input and echo enabled."""
    import termios

    cooked = list(mode)
    cooked[_IFLAG] |= termios.ICRNL
    cooked[_OFLAG] |= termios.OPOST
    cooked[_LFLAG] |= termios.ICANON | termios.ECHO | termios.ISIG
    return cooked


def _resume_raw(saved: tuple[int, list[Any]] | None) -> None:
    """Restores the terminal state captured by :func:`_suspend_raw`."""
    if saved is None:
        return
    fd, mode = saved
    import termios  # available on every non-win32 platform

    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, mode)
    except (OSError, ValueError, termios.error):
        logger.debug("could not restore raw mode after the editor")
