"""
sparcli.output.spinner
======================

Defines animated spinners for in-progress operations.

A :class:`Spinner` is a single line that cycles through a set of glyphs while a
task runs, then closes with a success or failure marker. The static
:meth:`Spinner.frame` builds the current line without touching the terminal,
while :meth:`Spinner.tick` advances the animation and redraws it in place via
:class:`~sparcli.core.inplace.InPlace`.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sparcli.core.inplace import InPlace
from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.core.theme import theme

if TYPE_CHECKING:
    from sparcli.core.color import Color


class SpinnerStyle(enum.Enum):
    """The animation style of a spinner."""

    BRAILLE = enum.auto()
    PIPE = enum.auto()
    DOTS = enum.auto()
    ARROW = enum.auto()


# Animation frames for each spinner style, keyed by the style enum.
_SPINNER_FRAMES: dict[SpinnerStyle, tuple[str, ...]] = {
    SpinnerStyle.BRAILLE: (
        "⠋",
        "⠙",
        "⠹",
        "⠸",
        "⠼",
        "⠴",
        "⠦",
        "⠧",
        "⠇",
        "⠏",
    ),
    SpinnerStyle.PIPE: ("|", "/", "-", "\\"),
    SpinnerStyle.DOTS: ("⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"),
    SpinnerStyle.ARROW: ("←", "↖", "↑", "↗", "→", "↘", "↓", "↙"),
}

# Two-step markers: (unicode, ascii) for success and failure respectively.
_SUCCESS_GLYPH = ("✔", "+")
_FAILURE_GLYPH = ("✖", "x")


class Spinner:
    """An animated, single-line spinner with a label."""

    __slots__ = (
        "_color",
        "_frame_index",
        "_inplace",
        "_label",
        "_label_style",
        "_style",
    )

    def __init__(
        self, label: str = "", *, inplace: InPlace | None = None
    ) -> None:
        self._style = SpinnerStyle.BRAILLE
        self._color = theme().accent
        self._label = label
        self._label_style = Style.new()
        self._frame_index = 0
        self._inplace = inplace

    def style(self, style: SpinnerStyle) -> Spinner:
        """Sets the spinner style and returns the spinner."""
        self._style = style
        return self

    def color(self, color: Color) -> Spinner:
        """Sets the spinner color and returns the spinner."""
        self._color = color
        return self

    def set_label(self, label: str) -> None:
        """Updates the label shown next to the spinner glyph."""
        self._label = label

    def frame(self) -> Rendered:
        """Builds the current frame as a single rendered line."""
        frames = _SPINNER_FRAMES[self._style]
        glyph = frames[self._frame_index % len(frames)]
        return self._compose(glyph, Style.new().with_fg(self._color))

    def tick(self) -> None:
        """Advances to the next frame and redraws it in place."""
        frame = self.frame()
        self._ensure_inplace().draw(frame)
        self._frame_index += 1

    def clear(self) -> None:
        """Stops the spinner and erases its line, leaving nothing behind."""
        if self._inplace is not None:
            self._inplace.clear()

    def finish(self, *, success: bool, label: str) -> None:
        """Stops the spinner with a success or failure marker."""
        active = theme()
        if success:
            glyph = _SUCCESS_GLYPH[0] if active.unicode else _SUCCESS_GLYPH[1]
            marker_style = active.success
        else:
            glyph = _FAILURE_GLYPH[0] if active.unicode else _FAILURE_GLYPH[1]
            marker_style = active.error
        self._label = label
        frame = self._compose(glyph, marker_style)
        inplace = self._ensure_inplace()
        inplace.draw(frame)
        inplace.finish()

    def _compose(self, glyph: str, glyph_style: Style) -> Rendered:
        """Composes a marker glyph and the label into one line."""
        spans = [Span.styled(glyph, glyph_style)]
        if self._label:
            spans.append(Span.styled(f" {self._label}", self._label_style))
        return Rendered([Line(spans)])

    def _ensure_inplace(self) -> InPlace:
        """Returns the in-place engine, creating a lazy one on first use."""
        if self._inplace is None:
            self._inplace = InPlace.progress()
        return self._inplace
