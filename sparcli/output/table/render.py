"""
sparcli.output.table.render
============================

Assembles the final rendered lines of a table.

The :class:`Builder` turns a :class:`~sparcli.output.table.table.TableLayout`,
its computed column widths and the placement grid from
:mod:`sparcli.output.table.plan` into styled lines: an optional centered title,
the top border, the header row and its separator, the body rows with zebra
striping and optional row separators, footer rows after a separator, and the
bottom border. Cells wrap when their column enables it, otherwise they truncate
with an ellipsis, and every horizontal edge chooses its corner and junction
glyphs from the border's :class:`~sparcli.core.border.BorderChars`.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from sparcli.core.geometry import Align
from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.core.width import truncate, wrap
from sparcli.output.layout import pad_line
from sparcli.output.table.plan import PlacedCell, RowPlan
from sparcli.output.table.table import Cell

if TYPE_CHECKING:
    from sparcli.core.border import BorderChars
    from sparcli.output.table.table import TableLayout, TableOpts


class Edge(enum.Enum):
    """Which horizontal border line to draw."""

    TOP = enum.auto()
    MIDDLE = enum.auto()
    BOTTOM = enum.auto()


# The (left, junction, right) glyph names of each horizontal edge.
_EDGE_GLYPHS: dict[Edge, tuple[str, str, str]] = {
    Edge.TOP: ("top_left", "tee_down", "top_right"),
    Edge.MIDDLE: ("tee_right", "cross", "tee_left"),
    Edge.BOTTOM: ("bottom_left", "tee_up", "bottom_right"),
}


@dataclass(slots=True)
class _Fmt:
    """How a cell's content is fitted into its span width."""

    width: int
    style: Style
    wrap: bool


@dataclass(slots=True)
class _Placement:
    """Where and how a cell's display line sits inside a row."""

    width: int
    pad: int
    align: Align
    fill: Style


@dataclass(slots=True)
class _RowCtx:
    """The placed cells and their display lines for one visual row."""

    placed: list[PlacedCell]
    cell_lines: list[list[Line]]
    fill_bg: bool


class Builder:
    """Assembles the table lines from the layout, plan and column widths."""

    __slots__ = ("layout", "opts", "plan", "widths", "chars")

    def __init__(
        self, layout: TableLayout, plan: list[RowPlan], widths: list[int]
    ) -> None:
        self.layout = layout
        self.opts: TableOpts = layout.opts
        self.plan = plan
        self.widths = widths
        self.chars: BorderChars = layout.opts.border.chars()

    def build(self) -> Rendered:
        """Builds the full rendered table."""
        lines: list[Line] = []
        lines.extend(self._title_lines())
        lines.extend(self._border(Edge.TOP))
        if self.opts.header:
            lines.extend(self._header_lines())
            lines.extend(self._border(Edge.MIDDLE))
        lines.extend(self._body_lines())
        lines.extend(self._border(Edge.BOTTOM))
        return Rendered(lines)

    def _title_lines(self) -> list[Line]:
        """Builds the optional centered title line above the table."""
        title = self.opts.title
        if title is None:
            return []
        first = title.lines[0] if title.lines else Line()
        width = self._total_width()
        return [pad_line(first, width, Align.CENTER, self.opts.title_style)]

    def _header_lines(self) -> list[Line]:
        """Builds the header row from the column headers."""
        placed: list[PlacedCell] = []
        for index, column in enumerate(self.layout.columns):
            cell = Cell.new(column.header).align(column.alignment)
            placed.append(PlacedCell(cell, index, 1))
        return self._row_lines(placed, self.opts.header_style, False)

    def _body_lines(self) -> list[Line]:
        """Builds all body and footer rows from the placement plan."""
        lines: list[Line] = []
        last_body = self._last_body_index()
        body_index = 0
        footer_started = False
        for index, row in enumerate(self.plan):
            if row.footer and not footer_started:
                lines.extend(self._border(Edge.MIDDLE))
                footer_started = True
            striped = self.opts.striped and body_index % 2 == 1
            style = self.opts.stripe_style if striped else Style()
            lines.extend(self._row_lines(row.cells, style, striped))
            if row.footer:
                continue
            body_index += 1
            if self.opts.row_separators and index != last_body:
                lines.extend(self._border(Edge.MIDDLE))
        return lines

    def _last_body_index(self) -> int:
        """Returns the index of the last non-footer row, or ``-1``."""
        last = -1
        for index, row in enumerate(self.plan):
            if not row.footer:
                last = index
        return last

    def _row_lines(
        self, placed: list[PlacedCell], style: Style, fill_bg: bool
    ) -> list[Line]:
        """Renders one placed row into one or more physical lines."""
        cell_lines = self._cell_lines(placed, style)
        height = max((len(lines) for lines in cell_lines), default=1)
        height = max(height, 1)
        ctx = _RowCtx(placed, cell_lines, fill_bg)
        return [self._row_line(ctx, physical) for physical in range(height)]

    def _cell_lines(
        self, placed: list[PlacedCell], style: Style
    ) -> list[list[Line]]:
        """Wraps or truncates each placed cell into its display lines."""
        result: list[list[Line]] = []
        for slot in placed:
            if slot.cell is None:
                result.append([Line()])
                continue
            width = self._span_width(slot.start, slot.colspan)
            fmt = _Fmt(width, style, self._column_wraps(slot.start))
            result.append(_format_cell(slot.cell, fmt))
        return result

    def _row_line(self, ctx: _RowCtx, physical: int) -> Line:
        """Builds one physical line of a placed row."""
        pad = self.opts.pad
        spans: list[Span] = [self._vbar()]
        for slot_index, slot in enumerate(ctx.placed):
            width = self._span_width(slot.start, slot.colspan)
            align = self._slot_align(slot)
            content = _blank_or(ctx.cell_lines, slot_index, physical)
            fill = self.opts.stripe_style if ctx.fill_bg else Style()
            _push_cell(spans, content, _Placement(width, pad, align, fill))
            spans.append(self._vbar())
        return Line(spans)

    def _slot_align(self, slot: PlacedCell) -> Align:
        """Returns the effective alignment of a placed cell."""
        if slot.cell is not None and slot.cell.alignment is not None:
            return slot.cell.alignment
        return self._align_for(slot.start)

    def _align_for(self, index: int) -> Align:
        """Returns the alignment of the column at ``index``."""
        columns = self.layout.columns
        if index < len(columns):
            return columns[index].alignment
        return Align.LEFT

    def _column_wraps(self, index: int) -> bool:
        """Returns whether the column at ``index`` wraps its content."""
        columns = self.layout.columns
        return index < len(columns) and columns[index].wrapping

    def _span_width(self, start: int, colspan: int) -> int:
        """Returns the width spanned by ``colspan`` columns from ``start``."""
        pad = self.opts.pad
        end = min(start + colspan, len(self.widths))
        content = sum(self.widths[start:end])
        extra = max(colspan - 1, 0) * (2 * pad + 1)
        return content + extra

    def _total_width(self) -> int:
        """Returns the total outer width of the table."""
        pad = self.opts.pad
        cells = len(self.widths)
        return sum(self.widths) + cells * 2 * pad + cells + 1

    def _vbar(self) -> Span:
        """Returns a vertical border span."""
        return Span.styled(self.chars.vertical, self.opts.border_style)

    def _border(self, edge: Edge) -> list[Line]:
        """Builds a horizontal border line for ``edge``, or nothing."""
        if self.opts.border.is_none():
            return []
        left, mid, right = self._corners(edge)
        pad = self.opts.pad
        horizontal = self.chars.horizontal
        parts = [left]
        count = len(self.widths)
        for index, width in enumerate(self.widths):
            parts.append(horizontal * (width + 2 * pad))
            if index + 1 < count:
                parts.append(mid)
        parts.append(right)
        return [Line.styled("".join(parts), self.opts.border_style)]

    def _corners(self, edge: Edge) -> tuple[str, str, str]:
        """Returns the (left, junction, right) glyphs for ``edge``."""
        left, mid, right = _EDGE_GLYPHS[edge]
        chars = self.chars
        return (
            getattr(chars, left),
            getattr(chars, mid),
            getattr(chars, right),
        )


def _format_cell(cell: Cell, fmt: _Fmt) -> list[Line]:
    """Formats one cell into styled lines, wrapping or truncating overflow."""
    out: list[Line] = []
    for line in cell.content.lines:
        plain = line.plain()
        if line.width() <= fmt.width:
            out.append(_restyle(line, fmt.style))
        elif fmt.wrap:
            for chunk in wrap(plain, fmt.width):
                out.append(Line.styled(chunk, fmt.style))
        else:
            span_style = line.spans[0].style if line.spans else fmt.style
            cell_style = fmt.style.patch(span_style)
            out.append(Line.styled(truncate(plain, fmt.width, "…"), cell_style))
    if not out:
        out.append(Line())
    return out


def _restyle(line: Line, base: Style) -> Line:
    """Applies a base style underneath each span's own style."""
    spans = [replace(span, style=base.patch(span.style)) for span in line.spans]
    return Line(spans)


def _blank_or(cell_lines: list[list[Line]], index: int, physical: int) -> Line:
    """Returns the cell's display line at ``physical``, or a blank line."""
    if index < len(cell_lines):
        lines = cell_lines[index]
        if physical < len(lines):
            return lines[physical]
    return Line()


def _push_cell(spans: list[Span], content: Line, place: _Placement) -> None:
    """Pushes one padded, aligned cell into ``spans``."""
    truncated = _clip(content, place.width)
    padded = pad_line(truncated, place.width, place.align, place.fill)
    if place.pad > 0:
        spans.append(Span.styled(" " * place.pad, place.fill))
    spans.extend(padded.spans)
    if place.pad > 0:
        spans.append(Span.styled(" " * place.pad, place.fill))


def _clip(line: Line, width: int) -> Line:
    """Truncates a line to ``width`` columns, keeping the first span's style."""
    if line.width() <= width:
        return line
    style = line.spans[0].style if line.spans else Style()
    return Line.styled(truncate(line.plain(), width, "…"), style)
