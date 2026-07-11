"""
sparcli.input.editor
===================

Defines external-editor integration (``$VISUAL`` / ``$EDITOR``).

:func:`edit_file` opens an editor on a path; :func:`edit_text` round-trips a
string through a temp file. The editor command comes from an explicit override,
then ``$VISUAL``, then ``$EDITOR``, then a platform default (``vi`` on POSIX,
``notepad`` on Windows). The command is split on whitespace and spawned as an
argument list - never through a shell - so no input is ever interpreted by one.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from sparcli.errors import ConfigError, TerminalError

logger = logging.getLogger(__name__)


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
    parts = _resolve_command(command).split()
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
