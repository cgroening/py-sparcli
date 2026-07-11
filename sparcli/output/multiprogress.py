"""
sparcli.output.multiprogress
=============================

Defines :class:`MultiProgress`, several progress bars updated together.

A :class:`MultiProgress` owns a list of :class:`~sparcli.output.progress.
ProgressBar` widgets, renders them as one block (one line per bar) and redraws
the whole group in place whenever a single bar is updated. A transient group
erases itself when the session ends instead of leaving the final bars behind.
"""

from __future__ import annotations

from dataclasses import dataclass

from sparcli.core.render import Rendered
from sparcli.core.text import Line
from sparcli.output.live import InPlace
from sparcli.output.progress import ProgressBar


@dataclass(slots=True)
class _BarState:
    """The live state of one bar within a :class:`MultiProgress`."""

    bar: ProgressBar
    value: float
    total: float


class MultiProgress:
    """A group of progress bars rendered as one block and updated in place."""

    __slots__ = ("_bars", "_inplace", "_transient")

    def __init__(self, *, inplace: InPlace | None = None) -> None:
        self._bars: list[_BarState] = []
        self._inplace = inplace or InPlace.create()
        self._transient = False

    def transient(self) -> MultiProgress:
        """Erases all bars when the session ends and returns the group."""
        self._transient = True
        return self

    def add(self, bar: ProgressBar) -> int:
        """Adds a bar with default progress and returns its index."""
        self._bars.append(_BarState(bar=bar, value=0.0, total=1.0))
        return len(self._bars) - 1

    def update(self, index: int, value: float, total: float) -> None:
        """Updates the bar at ``index`` and redraws the whole group."""
        if 0 <= index < len(self._bars):
            state = self._bars[index]
            state.value = value
            state.total = total
        self._inplace.draw(self.frame())

    def finish(self) -> None:
        """Ends the session, leaving or erasing the bars."""
        if self._transient:
            self._inplace.clear()
        else:
            self._inplace.finish()

    def frame(self) -> Rendered:
        """Builds the combined frame of all bars."""
        lines: list[Line] = []
        for state in self._bars:
            rendered = state.bar.bar(state.value, state.total)
            lines.extend(rendered.lines)
        return Rendered(lines)
