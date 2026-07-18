"""
sparcli.input.recall
====================

Defines :class:`HistoryRecall`, the Up/Down history walker for text prompts.

Recalling earlier entries is a concern of its own: it owns a cursor into the
entry list, knows that walking past the newest entry clears the field, and
persists a submitted value when the prompt is backed by a
:class:`~sparcli.input.history.History` store. Keeping it here leaves
:class:`~sparcli.input.text.TextInput` with only the wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sparcli.input.history import History

if TYPE_CHECKING:
    from collections.abc import Iterable


class HistoryRecall:
    """
    Walks a list of history entries, newest last.

    Attributes
    ----------
    entries : list[str]
        The recallable entries, oldest first.
    """

    __slots__ = ("_index", "_store", "entries")

    def __init__(
        self, entries: Iterable[str] = (), store: History | None = None
    ) -> None:
        self.entries: list[str] = list(entries)
        self._store = store
        self._index: int | None = None

    @classmethod
    def for_app(cls, app: str | None, fallback: Iterable[str]) -> HistoryRecall:
        """
        Returns a recall backed by the persistent store of ``app``.

        Parameters
        ----------
        app : str | None
            The application name whose history file to load; ``None`` keeps
            the recall in memory only.
        fallback : Iterable[str]
            The entries to use when there is no persistent store.

        Returns
        -------
        HistoryRecall
            A recall over either the loaded or the given entries.
        """
        if app is None:
            return cls(fallback)
        store = History.for_app(app)
        store.load()
        return cls(store.entries(), store)

    def previous(self) -> str | None:
        """
        Returns the previous (older) entry, or ``None`` when there is none.

        Returns
        -------
        str | None
            The recalled text, or ``None`` if the history is empty.
        """
        if not self.entries:
            return None
        if self._index is None:
            index = len(self.entries) - 1
        elif self._index == 0:
            index = 0
        else:
            index = self._index - 1
        self._index = index
        return self.entries[index]

    def following(self) -> str | None:
        """
        Returns the next (newer) entry, or ``""`` past the newest one.

        Returns
        -------
        str | None
            The recalled text, the empty string once the walk runs past the
            newest entry, or ``None`` when no walk is in progress.
        """
        index = self._index
        if index is None:
            return None
        if index + 1 < len(self.entries):
            self._index = index + 1
            return self.entries[index + 1]
        self._index = None
        return ""

    def remember(self, value: str) -> None:
        """
        Persists ``value`` if this recall is backed by a store.

        Parameters
        ----------
        value : str
            The submitted value to append to the history file.
        """
        if self._store is None:
            return
        self._store.add(value)
        self._store.save()
