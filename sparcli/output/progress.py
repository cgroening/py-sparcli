"""
sparcli.output.progress
=======================

Defines progress bars with multiple styles and threshold-based coloring.

A :class:`ProgressBar` renders a fixed-width bar of filled and empty cells with
an optional label, caps, percentage and value suffix. The static
:meth:`ProgressBar.bar` builds the line without touching the terminal, while
:meth:`ProgressBar.draw` redraws it in place via
:class:`~sparcli.core.inplace.InPlace`. A :class:`Thresholds` value switches the
fill color as the completion ratio crosses configured cut-off points.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass

from sparcli.core.color import Color
from sparcli.core.inplace import InPlace
from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.core.theme import theme

# Default bar width in columns.
DEFAULT_WIDTH = 30


class ProgressStyle(enum.Enum):
    """The visual style of the filled and empty bar cells."""

    BLOCK = enum.auto()
    ASCII = enum.auto()
    LINE = enum.auto()
    SHADED = enum.auto()


# The (filled, empty) glyph pair for each progress style.
_PROGRESS_GLYPHS: dict[ProgressStyle, tuple[str, str]] = {
    ProgressStyle.BLOCK: ("█", "░"),
    ProgressStyle.ASCII: ("#", "-"),
    ProgressStyle.LINE: ("━", "╌"),
    ProgressStyle.SHADED: ("▓", "░"),
}


@dataclass(frozen=True, slots=True)
class Thresholds:
    """
    Threshold-based fill colors keyed on the completion ratio.

    Attributes
    ----------
    mid : float
        Ratio at or above which the mid color applies.
    high : float
        Ratio at or above which the high color applies.
    low_color : Color
        Color used below ``mid``.
    mid_color : Color
        Color used in the ``[mid, high)`` range.
    high_color : Color
        Color used at or above ``high``.
    """

    mid: float
    high: float
    low_color: Color
    mid_color: Color
    high_color: Color


@dataclass(slots=True)
class ProgressOpts:
    """
    The appearance settings of a :class:`ProgressBar`.

    Bundled into one object so the bar itself holds only this and its draw
    engine, the same way :class:`~sparcli.output.table.table.Table` delegates
    to ``TableOpts``.

    Attributes
    ----------
    style : ProgressStyle
        Which glyph pair fills and pads the bar.
    left_cap, right_cap : str
        Strings drawn immediately before and after the bar.
    fill_color : Color
        Color of the filled portion, unless ``thresholds`` overrides it.
    empty_color : Color
        Color of the unfilled portion.
    thresholds : Thresholds | None
        Ratio-dependent fill colors, or ``None`` for a single color.
    show_percent : bool
        Whether the ``nn%`` suffix is shown.
    show_value : bool
        Whether the ``(value/total)`` suffix is shown.
    width : int
        Bar width in columns.
    label : str
        Leading label, empty for none.
    label_style : Style
        Style of the label and the suffixes.
    """

    style: ProgressStyle
    left_cap: str
    right_cap: str
    fill_color: Color
    empty_color: Color
    thresholds: Thresholds | None
    show_percent: bool
    show_value: bool
    width: int
    label: str
    label_style: Style

    @classmethod
    def defaults(cls) -> ProgressOpts:
        """Returns the theme-derived default appearance."""
        active = theme()
        return cls(
            style=ProgressStyle.BLOCK,
            left_cap="",
            right_cap="",
            fill_color=active.accent,
            empty_color=Color.DARK_GRAY,
            thresholds=None,
            show_percent=True,
            show_value=False,
            width=DEFAULT_WIDTH,
            label="",
            label_style=active.secondary,
        )


class ProgressBar:
    """A configurable, single-line progress bar."""

    __slots__ = ("_inplace", "_opts")

    def __init__(self, *, inplace: InPlace | None = None) -> None:
        self._opts = ProgressOpts.defaults()
        self._inplace = inplace

    def style(self, style: ProgressStyle) -> ProgressBar:
        """Sets the bar style and returns the bar."""
        self._opts.style = style
        return self

    def caps(self, left: str, right: str) -> ProgressBar:
        """Sets the left and right cap strings and returns the bar."""
        self._opts.left_cap = left
        self._opts.right_cap = right
        return self

    def fill_color(self, color: Color) -> ProgressBar:
        """Sets the fill color and returns the bar."""
        self._opts.fill_color = color
        return self

    def thresholds(self, thresholds: Thresholds) -> ProgressBar:
        """Sets threshold-based fill colors and returns the bar."""
        self._opts.thresholds = thresholds
        return self

    def show_percent(self, show: bool) -> ProgressBar:
        """Toggles the percentage suffix and returns the bar."""
        self._opts.show_percent = show
        return self

    def show_value(self, show: bool) -> ProgressBar:
        """Toggles the ``(value/total)`` suffix and returns the bar."""
        self._opts.show_value = show
        return self

    def width(self, width: int) -> ProgressBar:
        """Sets the bar width in columns (at least one) and returns the bar."""
        self._opts.width = max(width, 1)
        return self

    def label(self, label: str) -> ProgressBar:
        """Sets a leading label and returns the bar."""
        self._opts.label = label
        return self

    def bar(self, value: float, total: float) -> Rendered:
        """Builds the bar as a single rendered line for the given progress."""
        ratio = _ratio_of(value, total)
        filled = min(_round_half_up(ratio * self._opts.width), self._opts.width)
        empty = self._opts.width - filled
        fill_glyph, empty_glyph = _PROGRESS_GLYPHS[self._opts.style]
        spans: list[Span] = []
        self._push_label(spans)
        self._push_cap(spans, self._opts.left_cap)
        spans.append(
            Span.styled(
                fill_glyph * filled,
                Style.new().with_fg(self._resolve_fill_color(ratio)),
            )
        )
        spans.append(
            Span.styled(
                empty_glyph * empty, Style.new().with_fg(self._opts.empty_color)
            )
        )
        self._push_cap(spans, self._opts.right_cap)
        self._push_suffix(spans, ratio, value, total)
        return Rendered([Line(spans)])

    def draw(self, value: float, total: float) -> None:
        """Draws the bar in place (animated when on a terminal)."""
        self._ensure_inplace().draw(self.bar(value, total))

    def finish(self, value: float, total: float) -> None:
        """Draws the final bar and ends the in-place session."""
        inplace = self._ensure_inplace()
        inplace.draw(self.bar(value, total))
        inplace.finish()

    def _resolve_fill_color(self, ratio: float) -> Color:
        """Resolves the fill color for ``ratio``, honoring thresholds."""
        bounds = self._opts.thresholds
        if bounds is None:
            return self._opts.fill_color
        if ratio >= bounds.high:
            return bounds.high_color
        if ratio >= bounds.mid:
            return bounds.mid_color
        return bounds.low_color

    def _push_label(self, spans: list[Span]) -> None:
        """Pushes the leading label span, if any."""
        if self._opts.label:
            spans.append(
                Span.styled(f"{self._opts.label} ", self._opts.label_style)
            )

    def _push_cap(self, spans: list[Span], cap: str) -> None:
        """Pushes a cap span, if non-empty."""
        if cap:
            spans.append(Span.raw(cap))

    def _push_suffix(
        self, spans: list[Span], ratio: float, value: float, total: float
    ) -> None:
        """Pushes the percentage and/or value suffix."""
        if self._opts.show_percent:
            percent = _round_half_up(ratio * 100.0)
            spans.append(Span.styled(f" {percent:>3}%", self._opts.label_style))
        if self._opts.show_value:
            spans.append(
                Span.styled(
                    f" ({value:.0f}/{total:.0f})", self._opts.label_style
                )
            )

    def _ensure_inplace(self) -> InPlace:
        """Returns the in-place engine, creating a lazy one on first use."""
        if self._inplace is None:
            self._inplace = InPlace.create()
        return self._inplace


def _ratio_of(value: float, total: float) -> float:
    """Clamps ``value / total`` into ``[0, 1]``; non-positive total is zero."""
    if total <= 0.0:
        return 0.0
    return max(0.0, min(1.0, value / total))


def _round_half_up(value: float) -> int:
    """Rounds a non-negative float half away from zero, matching Rust."""
    return math.floor(value + 0.5)
