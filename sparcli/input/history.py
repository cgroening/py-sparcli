"""
sparcli.input.history
=====================

Defines :class:`History`, a bounded list of past input lines.

A history collapses blanks and consecutive duplicates, caps its length, and can
persist to a file under the platform state directory (``XDG_STATE_HOME``,
``~/.local/state`` or ``%LOCALAPPDATA%``). Persistence is best effort: I/O
errors on load or save are logged and swallowed rather than raised, so a prompt
never crashes because its history file is unreadable.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Name of the history file inside the per-app state directory.
_HISTORY_FILE = "history"

# Characters that would let an app name escape its state subdirectory.
_PATH_SEPARATORS = frozenset({"/", "\\", ":"})

# Default maximum number of retained entries.
DEFAULT_MAX = 500


class History:
    """A bounded list of past input lines, optionally backed by a file."""

    __slots__ = ("_entries", "_keep_duplicates", "_max", "_path")

    def __init__(self) -> None:
        self._entries: list[str] = []
        self._max: int = DEFAULT_MAX
        self._path: Path | None = None
        self._keep_duplicates: bool = False

    @classmethod
    def for_app(cls, app: str) -> History:
        """
        Returns a history persisted under the app's state directory.

        Parameters
        ----------
        app : str
            The application name, used as the state subdirectory.

        Returns
        -------
        History
            A history whose backing file is ``<state>/<app>/history``.
        """
        history = cls()
        directory = _state_dir()
        if directory is not None:
            history._path = _history_path(directory, app)
        return history

    def max_entries(self, maximum: int) -> History:
        """Sets the maximum number of entries and returns ``self``."""
        self._max = max(maximum, 1)
        return self

    def keep_duplicates(self) -> History:
        """Keeps consecutive duplicate entries instead of collapsing them."""
        self._keep_duplicates = True
        return self

    def entries(self) -> list[str]:
        """Returns the entries, oldest first."""
        return list(self._entries)

    def __len__(self) -> int:
        """Returns the number of entries."""
        return len(self._entries)

    def add(self, line: str) -> None:
        """Adds a line, skipping blanks and (by default) consecutive dups."""
        if not line.strip():
            return
        if (
            not self._keep_duplicates
            and self._entries
            and self._entries[-1] == line
        ):
            return
        self._entries.append(line)
        overflow = len(self._entries) - self._max
        if overflow > 0:
            del self._entries[:overflow]

    def load(self) -> None:
        """Loads entries from the backing file, if configured."""
        if self._path is None or not self._path.exists():
            return
        try:
            contents = self._path.read_text(encoding="utf-8")
        except OSError as error:
            logger.warning("could not read history file: %s", error)
            return
        self._entries = _split_lines(contents)

    def save(self) -> None:
        """Saves entries to the backing file, creating directories as needed."""
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(self._path, "\n".join(self._entries))
        except OSError as error:
            logger.warning("could not write history file: %s", error)


def _atomic_write(path: Path, content: str) -> None:
    """
    Writes ``content`` to ``path`` atomically via a temp file and rename.

    A crash or a concurrent writer can never leave a half-written history
    file: the content is written to a sibling temp file and then renamed over
    the target in a single step.
    """
    handle, temp = tempfile.mkstemp(
        dir=path.parent, prefix=f"{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
        Path(temp).replace(path)
    except OSError:
        _remove_quietly(temp)
        raise


def _remove_quietly(path: str) -> None:
    """Removes ``path``, ignoring a missing file."""
    Path(path).unlink(missing_ok=True)


def _split_lines(text: str) -> list[str]:
    """Splits ``text`` into lines the way Rust's ``str::lines`` does."""
    if not text:
        return []
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts.pop()
    return [part.removesuffix("\r") for part in parts]


def _state_dir() -> Path | None:
    """
    Resolves the platform state directory for persisted history.

    The directory comes from the environment, so it is resolved to an absolute
    path with symlinks collapsed before anything is written under it.

    Returns
    -------
    Path | None
        The resolved state directory, or ``None`` when the environment names
        none.
    """
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg).resolve()
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        return Path(local).resolve() if local else None
    home = os.environ.get("HOME")
    if not home:
        return None
    return (Path(home) / ".local" / "state").resolve()


def _history_path(directory: Path, app: str) -> Path | None:
    """
    Returns the history file for ``app`` under ``directory``, or ``None``.

    The application name reaches this code from the caller and must never be
    able to escape the state directory, so the joined path is resolved and
    verified to still sit inside it. A name carrying a separator, a drive or
    ``..`` is rejected rather than sanitized.

    Parameters
    ----------
    directory : Path
        The already-resolved state directory.
    app : str
        The application name used as the subdirectory.

    Returns
    -------
    Path | None
        The history file path, or ``None`` when ``app`` is unusable.
    """
    if not app or app in {".", ".."} or set(app) & _PATH_SEPARATORS:
        logger.warning("refusing unsafe history app name: %r", app)
        return None
    candidate = (directory / app / _HISTORY_FILE).resolve()
    if not candidate.is_relative_to(directory):
        logger.warning("refusing history path outside the state dir: %r", app)
        return None
    return candidate
