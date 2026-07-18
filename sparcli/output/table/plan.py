"""
sparcli.output.table.plan
=========================

Resolves table rows into a grid and computes each column's display width.

:func:`build_plan` walks the rows and places every cell at a concrete column,
honoring ``colspan`` and ``rowspan`` occupancy (rowspan continuation cells fill
the skipped slots in the rows below). :func:`column_widths` derives each
column's width from the header and body cells, clamps it by the column's
min/max/fixed constraints and, when the table overflows, shrinks the flexible
columns until it fits. The result feeds :mod:`sparcli.output.table.render`.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sparcli.output.table.table import Cell, Column, Row, TableLayout


@dataclass(slots=True)
class PlacedCell:
    """A cell placed at a concrete column, or a rowspan continuation slot."""

    cell: Cell | None
    start: int
    colspan: int


@dataclass(slots=True)
class RowPlan:
    """One visual row: every column filled, including rowspan continuations."""

    cells: list[PlacedCell]
    footer: bool


def build_plan(rows: list[Row], cols: int) -> list[RowPlan]:
    """
    Resolves rows into a grid, honoring colspan and rowspan occupancy.

    Parameters
    ----------
    rows : list[Row]
        The table's rows in order.
    cols : int
        The number of columns defined on the table.

    Returns
    -------
    list[RowPlan]
        One plan per row, every column filled.
    """
    occupied = [0] * cols
    plan: list[RowPlan] = []
    for row in rows:
        cells = iter(row.cells)
        placed: list[PlacedCell] = []
        col = 0
        while col < cols:
            if occupied[col] > 0:
                occupied[col] -= 1
                placed.append(PlacedCell(None, col, 1))
                col += 1
                continue
            cell = next(cells, None)
            if cell is None:
                placed.append(PlacedCell(None, col, 1))
                col += 1
                continue
            span = max(min(cell.span_cols, cols - col), 1)
            if cell.span_rows > 1:
                for slot in range(col, col + span):
                    occupied[slot] = cell.span_rows - 1
            placed.append(PlacedCell(cell, col, span))
            col += span
        plan.append(RowPlan(placed, row.footer))
    return plan


def column_widths(
    layout: TableLayout, plan: list[RowPlan], max_width: int
) -> list[int]:
    """
    Computes the display width of each column from the placement plan.

    Parameters
    ----------
    layout : TableLayout
        The column definitions and table options.
    plan : list[RowPlan]
        The resolved placement grid.
    max_width : int
        The maximum outer width in columns.

    Returns
    -------
    list[int]
        The width of each column, never exceeding ``max_width`` together.
    """
    columns = layout.columns
    opts = layout.opts
    widths = [0] * len(columns)
    if opts.header:
        for index, column in enumerate(columns):
            widths[index] = column.header.width()
    for row in plan:
        for placed in row.cells:
            if placed.cell is not None and placed.colspan == 1:
                natural = placed.cell.content.width()
                widths[placed.start] = max(widths[placed.start], natural)
    for index, column in enumerate(columns):
        widths[index] = _clamp_width(widths[index], column)
    _Fitter(columns, widths, opts.pad).fit(max_width)
    return widths


class ShrinkPass(enum.Enum):
    """Which columns a shrink pass may take width from."""

    WRAPPING = enum.auto()
    NON_WRAPPING = enum.auto()


class _Fitter:
    """Shrinks flexible columns until the table fits a maximum width."""

    __slots__ = ("columns", "pad", "widths")

    def __init__(
        self, columns: list[Column], widths: list[int], pad: int
    ) -> None:
        self.columns = columns
        self.widths = widths
        self.pad = pad

    def fit(self, max_width: int) -> None:
        """Shrinks columns in place until the table fits ``max_width``."""
        cells = len(self.widths)
        overhead = cells * (2 * self.pad + 1) + 1
        budget = max(max_width - overhead, 0)
        content = sum(self.widths)
        if content <= budget:
            return
        deficit = content - budget
        deficit = self._shrink(deficit, ShrinkPass.WRAPPING)
        self._shrink(deficit, ShrinkPass.NON_WRAPPING)

    def _shrink(self, deficit: int, pass_: ShrinkPass) -> int:
        """Takes one cell at a time from the widest eligible column."""
        while deficit > 0:
            index = self._widest_shrinkable(pass_)
            if index is None:
                break
            self.widths[index] -= 1
            deficit -= 1
        return deficit

    def _widest_shrinkable(self, pass_: ShrinkPass) -> int | None:
        """Returns the eligible column with the most slack above its floor."""
        best_index: int | None = None
        best_width = 0
        for index, width in enumerate(self.widths):
            column = self.columns[index]
            if not _eligible(column, pass_) or width <= _floor(column):
                continue
            if best_index is None or width > best_width:
                best_index = index
                best_width = width
        return best_index


def _clamp_width(natural: int, column: Column) -> int:
    """Clamps a natural width by a column's min/max/fixed constraints."""
    if column.width_fixed is not None:
        return column.width_fixed
    width = max(natural, column.width_min)
    if column.width_max is not None:
        width = min(width, column.width_max)
    return max(width, 1)


def _eligible(column: Column, pass_: ShrinkPass) -> bool:
    """Returns whether ``column`` may give up width during ``pass_``."""
    if column.width_fixed is not None:
        return False
    if pass_ is ShrinkPass.WRAPPING:
        return column.wrapping
    return not column.wrapping


def _floor(column: Column) -> int:
    """Returns the narrowest a column may be shrunk to."""
    return max(column.width_min, 1)
