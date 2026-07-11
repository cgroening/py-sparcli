"""
sparcli.output.live
==================

Defines the in-place redraw engine :class:`InPlace` and the :class:`Live` view.

:class:`InPlace` rewinds the cursor and rewrites a frame in place; it powers
spinners, progress bars, multi-progress groups and every interactive prompt.
Off a terminal it emits no control codes and prints only the final frame once,
so piped and captured output stays clean. :class:`Live` is the public wrapper
for updating an arbitrary renderable in place.
"""

from __future__ import annotations

import io
import sys

from sparcli.core.render import Renderable, Rendered, write_line, write_rendered
from sparcli.core.terminal import color_support, is_output_tty


class InPlace:
    """Redraws successive frames in the same terminal region."""

    __slots__ = ("_interactive", "_silent", "_last_height", "_last_frame")

    def __init__(self, interactive: bool, silent: bool) -> None:
        self._interactive = interactive
        self._silent = silent
        self._last_height = 0
        self._last_frame: Rendered | None = None

    @classmethod
    def create(cls, always: bool = False) -> InPlace:
        """Returns an engine that redraws on a TTY (or always when forced)."""
        return cls(interactive=always or is_output_tty(), silent=False)

    @classmethod
    def silent(cls) -> InPlace:
        """Returns an engine that never draws, for headless prompts and tests."""
        return cls(interactive=False, silent=True)

    def draw(self, rendered: Rendered) -> None:
        """Rewinds and rewrites the frame, or records it when off a terminal."""
        if self._silent:
            return
        if not self._interactive:
            self._last_frame = rendered
            return
        buffer = io.StringIO()
        self._rewind(buffer)
        support = color_support()
        for index, line in enumerate(rendered.lines):
            if index:
                buffer.write("\r\n")
            write_line(buffer, line, support)
        sys.stdout.write(buffer.getvalue())
        sys.stdout.flush()
        self._last_height = rendered.height()

    def reset(self) -> None:
        """Forgets the previous frame after an external program drew over it."""
        self._last_height = 0

    def finish(self) -> None:
        """Leaves the final frame in place and ends the session."""
        if self._silent:
            return
        if self._interactive:
            sys.stdout.write("\r\n")
            sys.stdout.flush()
        elif self._last_frame is not None:
            write_rendered(sys.stdout, self._last_frame, color_support())
            sys.stdout.flush()
        self._last_height = 0
        self._last_frame = None

    def clear(self) -> None:
        """Erases the current frame from the terminal."""
        if self._silent or not self._interactive:
            self._last_frame = None
            return
        buffer = io.StringIO()
        self._rewind(buffer)
        sys.stdout.write(buffer.getvalue())
        sys.stdout.flush()
        self._last_height = 0

    def _rewind(self, buffer: io.StringIO) -> None:
        """Writes the escape codes that move the cursor back to the frame top."""
        if not self._last_height:
            return
        buffer.write("\r")
        if self._last_height > 1:
            buffer.write(f"\x1b[{self._last_height - 1}A")
        buffer.write("\x1b[J")


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
        from sparcli.core.terminal import term_width

        self._inplace.draw(widget.render(term_width()))

    def finish(self) -> None:
        """Leaves the final frame and ends the live session."""
        self._inplace.finish()

    def clear(self) -> None:
        """Erases the live frame from the terminal."""
        self._inplace.clear()
