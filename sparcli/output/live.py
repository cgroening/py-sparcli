"""
sparcli.output.live
===================

Defines the :class:`Live` view for updating a renderable in place.

:class:`Live` is the public wrapper around
:class:`~sparcli.core.inplace.InPlace`, the redraw engine that lives in
``core`` so that ``input`` can use it without depending on ``output``.
``InPlace`` is re-exported here for backwards compatibility with the flat
public API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sparcli.core.inplace import InPlace
from sparcli.core.terminal import term_width

if TYPE_CHECKING:
    from sparcli.core.render import Renderable

__all__ = ["InPlace", "Live"]


class Live:
    """Updates an arbitrary renderable in place on the terminal."""

    __slots__ = ("_inplace",)

    def __init__(self, inplace: InPlace | None = None) -> None:
        self._inplace = inplace or InPlace.create(always=False)

    @classmethod
    def always(cls) -> Live:
        """Returns a live view that redraws even when off a terminal."""
        return cls(InPlace.create(always=True))

    def update(self, widget: Renderable) -> None:
        """Renders ``widget`` at the terminal width and draws it in place."""
        self._inplace.draw(widget.render(term_width()))

    def finish(self) -> None:
        """Leaves the final frame and ends the live session."""
        self._inplace.finish()

    def clear(self) -> None:
        """Erases the live frame from the terminal."""
        self._inplace.clear()
