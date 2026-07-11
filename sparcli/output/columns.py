"""
sparcli.output.columns
======================

Defines :class:`Columns`, a side-by-side arrangement of rendered blocks.

Each column is laid out at its own width, padded to the tallest column and
placed next to its neighbours with a configurable gap. Shorter columns are
vertically aligned (top, middle or bottom), and an optional border glyph can be
drawn as a separator centered in the gap. Both a keyword constructor and fluent
builders are provided.
"""

from __future__ import annotations

from dataclasses import dataclass

from sparcli.core.border import BorderType
from sparcli.core.geometry import Align, VAlign
from sparcli.core.render import Renderable, Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.core.theme import theme
from sparcli.output.layout import blank_line, pad_line

_DEFAULT_GAP = 2


@dataclass(slots=True)
class _ColumnItem:
    """One column: a rendered block and its horizontal alignment."""

    block: Rendered
    align: Align = Align.LEFT


class Columns(Renderable):
    """A horizontal arrangement of rendered blocks."""

    __slots__ = (
        "_items",
        "_gap",
        "_separator",
        "_separator_style",
        "_valign",
    )

    def __init__(
        self,
        *,
        gap: int = _DEFAULT_GAP,
        separator: BorderType | None = None,
        separator_style: Style | None = None,
        valign: VAlign = VAlign.TOP,
    ) -> None:
        self._items: list[_ColumnItem] = []
        self._gap = gap
        self._separator = separator
        self._separator_style = (
            separator_style
            if separator_style is not None
            else theme().secondary
        )
        self._valign = valign

    def add(self, content: Renderable, width: int) -> Columns:
        """Adds a column from a renderable laid out at ``width`` columns."""
        self._items.append(_ColumnItem(block=content.render(width)))
        return self

    def add_rendered(self, block: Rendered) -> Columns:
        """Adds a column from an already rendered block and returns self."""
        self._items.append(_ColumnItem(block=block))
        return self

    def align(self, align: Align) -> Columns:
        """Sets the alignment of the most recently added column."""
        if self._items:
            self._items[-1].align = align
        return self

    def gap(self, gap: int) -> Columns:
        """Sets the gap between columns in spaces and returns self."""
        self._gap = gap
        return self

    def separator(self, border: BorderType) -> Columns:
        """Draws a vertical separator between columns and returns self."""
        self._separator = border
        return self

    def valign(self, valign: VAlign) -> Columns:
        """Sets the vertical alignment of shorter columns and returns self."""
        self._valign = valign
        return self

    def render(self, max_width: int) -> Rendered:
        """Renders the columns side by side, ignoring ``max_width``."""
        if not self._items:
            return Rendered.empty()
        height = max(item.block.height() for item in self._items)
        widths = [item.block.width() for item in self._items]
        aligned = [
            self._align_column(item, width, height)
            for item, width in zip(self._items, widths, strict=True)
        ]
        lines = [
            self._compose_row(aligned, widths, row) for row in range(height)
        ]
        return Rendered(lines)

    def _align_column(
        self, item: _ColumnItem, width: int, height: int
    ) -> list[Line]:
        """Vertically aligns and pads a column into a uniform block."""
        pad_top = _pad_top(self._valign, height, item.block.height())
        lines: list[Line] = [blank_line(width) for _ in range(pad_top)]
        for line in item.block.lines:
            lines.append(pad_line(line, width, item.align))
        while len(lines) < height:
            lines.append(blank_line(width))
        return lines

    def _compose_row(
        self, aligned: list[list[Line]], widths: list[int], row: int
    ) -> Line:
        """Joins the columns at index ``row`` into one output line."""
        spans: list[Span] = []
        for index, column in enumerate(aligned):
            if index > 0:
                self._push_gap(spans)
            line = (
                column[row] if row < len(column) else blank_line(widths[index])
            )
            spans.extend(line.spans)
        return Line(spans)

    def _push_gap(self, spans: list[Span]) -> None:
        """Pushes the inter-column gap and optional separator glyph."""
        if self._separator is None:
            spans.append(Span.raw(" " * self._gap))
            return
        half = self._gap // 2
        glyph = self._separator.chars().vertical
        spans.append(Span.raw(" " * half))
        spans.append(Span.styled(glyph, self._separator_style))
        rest = max(0, self._gap - (half + 1))
        spans.append(Span.raw(" " * rest))


def _pad_top(valign: VAlign, height: int, block_height: int) -> int:
    """Returns the number of blank rows above a column for a vertical align."""
    if valign is VAlign.TOP:
        return 0
    if valign is VAlign.MIDDLE:
        return (height - block_height) // 2
    return height - block_height
