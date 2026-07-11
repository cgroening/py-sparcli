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

# Default maximum number of retained entries.
DEFAULT_MAX = 500


class History:
    """A bounded list of past input lines, optionally backed by a file."""

    __slots__ = ("_entries", "_max", "_path", "_keep_duplicates")

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
            history._path = directory / app / "history"
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
    """Writes ``content`` to ``path`` atomically via a temp file and rename.

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
        os.replace(temp, path)
    except OSError:
        _remove_quietly(temp)
        raise


def _remove_quietly(path: str) -> None:
    """Removes ``path``, ignoring a missing file."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def _split_lines(text: str) -> list[str]:
    """Splits ``text`` into lines the way Rust's ``str::lines`` does."""
    if not text:
        return []
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts.pop()
    return [part.removesuffix("\r") for part in parts]


def _state_dir() -> Path | None:
    """Resolves the platform state directory for persisted history."""
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg)
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        return Path(local) if local else None
    home = os.environ.get("HOME")
    return Path(home) / ".local" / "state" if home else None
