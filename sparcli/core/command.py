"""
Splitting a configured command line into an argument vector.

``$EDITOR``, ``$VISUAL`` and ``$PAGER`` are command *lines*, not program
names, so they have to be split before they can be handed to
:mod:`subprocess`. Splitting on whitespace loses any path containing a space,
which is common on macOS (``/Applications/Sublime Text/subl``), so
:func:`split_command` honors quotes the way a POSIX shell would.

This is a lexer only. The result is always passed to :mod:`subprocess` as an
argument list and never to a shell, so quoting cannot become injection.
"""

from __future__ import annotations

import logging
import os
import shlex

__all__ = ["resolve_from_env", "split_command"]

logger = logging.getLogger(__name__)


def split_command(command: str) -> list[str]:
    """
    Splits a command line into argv, honoring quotes.

    Uses :func:`shlex.split` rather than :meth:`str.split` so a program path
    containing spaces survives intact. The result feeds :mod:`subprocess` as
    an argument list, never a shell, so no quoting can turn into command
    injection.

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
        logger.debug("could not parse command: %r", command)
        return []


def resolve_from_env(
    override: str | None,
    keys: tuple[str, ...],
    default: str,
) -> str:
    """
    Resolves a command line from an override, the environment or a default.

    ``$EDITOR``, ``$VISUAL`` and ``$PAGER`` all follow the same precedence: an
    explicit override wins, then the first of ``keys`` naming a non-blank
    variable, then ``default``. Blank and whitespace-only values count as
    unset throughout, so ``EDITOR=""`` falls through instead of yielding an
    unusable empty command.

    Parameters
    ----------
    override : str | None
        An explicitly configured command, or ``None`` to consult the
        environment.
    keys : tuple[str, ...]
        Environment variable names to try, in order of precedence.
    default : str
        The built-in fallback used when nothing else yields a value.

    Returns
    -------
    str
        The resolved command line.
    """
    if override is not None and override.strip():
        return override
    for key in keys:
        value = os.environ.get(key)
        if value is not None and value.strip():
            return value
    return default
