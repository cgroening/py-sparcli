"""
sparcli.output.layout
=====================

Internal line-building helpers shared by the output widgets.

These small functions create blank lines and runs of spaces, and pad a line to
a target width with a fill style. They keep the widget code focused on layout
decisions instead of span bookkeeping.
"""

from __future__ import annotations

from sparcli.core.geometry import Align
from sparcli.core.style import Style
from sparcli.core.text import Line, Span


def space_span(count: int, style: Style | None = None) -> Span:
    """Returns a span of ``count`` spaces with an optional fill style."""
    width = max(0, count)
    return Span(content=" " * width, style=style or Style.new())


def blank_line(width: int = 0, style: Style | None = None) -> Line:
    """Returns an empty line, optionally filled with ``width`` spaces."""
    if width <= 0:
        return Line()
    return Line([space_span(width, style)])


def pad_line(
    line: Line,
    width: int,
    align: Align = Align.LEFT,
    style: Style | None = None,
) -> Line:
    """
    Pads a line to ``width`` columns using ``align`` and a fill style.

    Parameters
    ----------
    line : Line
        The line to pad. Lines wider than ``width`` are returned unchanged.
    width : int
        The target width in columns.
    align : Align
        How to distribute the padding.
    style : Style | None
        The style applied to the padding spaces.

    Returns
    -------
    Line
        A new line padded to ``width``.
    """
    deficit = width - line.width()
    if deficit <= 0:
        return Line(list(line.spans))
    left, right = _split_padding(deficit, align)
    spans: list[Span] = []
    if left:
        spans.append(space_span(left, style))
    spans.extend(line.spans)
    if right:
        spans.append(space_span(right, style))
    return Line(spans)


def _split_padding(deficit: int, align: Align) -> tuple[int, int]:
    """Splits a padding deficit into left and right amounts for an alignment."""
    if align is Align.LEFT:
        return (0, deficit)
    if align is Align.RIGHT:
        return (deficit, 0)
    left = deficit // 2
    return (left, deficit - left)
