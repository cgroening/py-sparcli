"""
sparcli.core.inplace
====================

Defines the in-place redraw engine :class:`InPlace`.

:class:`InPlace` rewinds the cursor and rewrites a frame in place; it powers
spinners, progress bars, multi-progress groups and every interactive prompt.
Off a terminal it emits no control codes and prints only the final frame once,
so piped and captured output stays clean.

It lives in ``core`` rather than ``output`` because it is a pure cursor and
redraw mechanism without widget semantics, and because ``input`` depends on it:
the dependency direction ``output``/``input`` -> ``core`` must stay acyclic.
"""

from __future__ import annotations

import io
import sys
from typing import TextIO

from sparcli.core import cursor
from sparcli.core.render import Rendered, write_line, write_rendered
from sparcli.core.terminal import (
    color_support,
    is_error_tty,
    is_output_tty,
)


class InPlace:
    """Redraws successive frames in the same terminal region."""

    __slots__ = (
        "_interactive",
        "_last_frame",
        "_last_height",
        "_silent",
        "_stream",
    )

    def __init__(
        self,
        interactive: bool,
        silent: bool,
        stream: TextIO | None = None,
    ) -> None:
        self._interactive = interactive
        self._silent = silent
        self._stream = stream if stream is not None else sys.stdout
        self._last_height = 0
        self._last_frame: Rendered | None = None

    @classmethod
    def create(cls, always: bool = False) -> InPlace:
        """Returns an engine that redraws on a TTY (or always when forced)."""
        return cls(interactive=always or is_output_tty(), silent=False)

    @classmethod
    def progress(cls) -> InPlace:
        """
        Returns an engine for a progress indicator, drawing on stderr.

        Progress is not payload: drawing it on standard output would put
        animation frames into whatever a caller pipes the output into. It is
        drawn only when standard error is itself a terminal.
        """
        return cls(interactive=is_error_tty(), silent=False, stream=sys.stderr)

    @classmethod
    def silent(cls) -> InPlace:
        """Returns an engine that never draws (headless prompts, tests)."""
        return cls(interactive=False, silent=True)

    def draw(self, rendered: Rendered) -> None:
        """Rewinds and rewrites the frame, or records it when off a terminal."""
        if self._silent:
            return
        if not self._interactive:
            self._last_frame = rendered
            return
        cursor.hide()
        buffer = io.StringIO()
        self._rewind(buffer)
        support = color_support()
        for index, line in enumerate(rendered.lines):
            if index:
                buffer.write("\r\n")
            write_line(buffer, line, support)
        self._stream.write(buffer.getvalue())
        self._stream.flush()
        self._last_height = rendered.height()

    def reset(self) -> None:
        """Forgets the previous frame after an external program drew over it."""
        self._last_height = 0

    def finish(self) -> None:
        """Leaves the final frame in place and ends the session."""
        if self._silent:
            return
        if self._interactive:
            self._stream.write("\r\n")
            self._stream.flush()
        elif self._last_frame is not None:
            write_rendered(self._stream, self._last_frame, color_support())
            self._stream.flush()
        cursor.show()
        self._last_height = 0
        self._last_frame = None

    def clear(self) -> None:
        """Erases the current frame from the terminal."""
        if self._silent or not self._interactive:
            self._last_frame = None
            return
        buffer = io.StringIO()
        self._rewind(buffer)
        self._stream.write(buffer.getvalue())
        self._stream.flush()
        cursor.show()
        self._last_height = 0

    def _rewind(self, buffer: io.StringIO) -> None:
        """Writes the escapes moving the cursor back to the frame top."""
        if not self._last_height:
            return
        buffer.write("\r")
        if self._last_height > 1:
            buffer.write(f"\x1b[{self._last_height - 1}A")
        buffer.write("\x1b[J")
