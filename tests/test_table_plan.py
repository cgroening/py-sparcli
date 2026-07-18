"""Tests for the table placement grid and the column width distributor.

``build_plan`` and ``column_widths`` carry the colspan, rowspan and shrinking
rules. Driving them through the ``Table`` facade cannot reach their edge cases,
so they are exercised directly here.
"""

from __future__ import annotations

from sparcli.core.text import Text
from sparcli.output.table.plan import build_plan, column_widths
from sparcli.output.table.table import (
    Cell,
    Column,
    Row,
    TableLayout,
    TableOpts,
)


def _row(*cells: Cell, footer: bool = False) -> Row:
    """Builds a table row from cells."""
    return Row(cells=list(cells), footer=footer)


def _cell(text: str, *, colspan: int = 1, rowspan: int = 1) -> Cell:
    """Builds a cell with the given spans."""
    cell = Cell.new(Text.raw(text))
    if colspan > 1:
        cell = cell.colspan(colspan)
    if rowspan > 1:
        cell = cell.rowspan(rowspan)
    return cell


def _layout(columns: list[Column], **opts: object) -> TableLayout:
    """Builds a layout from columns and option overrides."""
    table_opts = TableOpts()
    for key, value in opts.items():
        setattr(table_opts, key, value)
    return TableLayout(columns=columns, opts=table_opts)


class TestBuildPlan:
    def test_each_row_fills_every_column(self) -> None:
        plan = build_plan([_row(_cell("a"), _cell("b"))], 2)
        assert len(plan) == 1
        assert len(plan[0].cells) == 2

    def test_a_short_row_is_padded_with_empty_slots(self) -> None:
        plan = build_plan([_row(_cell("a"))], 3)
        assert len(plan[0].cells) == 3

    def test_colspan_occupies_several_columns(self) -> None:
        plan = build_plan([_row(_cell("wide", colspan=2), _cell("z"))], 3)
        placed = plan[0].cells
        spanning = next(
            p for p in placed if p.cell is not None and p.start == 0
        )
        assert spanning.colspan == 2

    def test_rowspan_reserves_the_slot_in_the_next_row(self) -> None:
        rows = [_row(_cell("tall", rowspan=2), _cell("a")), _row(_cell("b"))]
        plan = build_plan(rows, 2)
        assert len(plan) == 2
        # The second row's first slot is the continuation, so its own cell
        # must have landed in column one.
        second = plan[1].cells
        assert second[0].cell is None
        assert second[1].cell is not None

    def test_footer_rows_are_marked(self) -> None:
        plan = build_plan([_row(_cell("a")), _row(_cell("t"), footer=True)], 1)
        assert plan[0].footer is False
        assert plan[1].footer is True

    def test_no_rows_produce_no_plan(self) -> None:
        assert build_plan([], 3) == []

    def test_overflowing_colspan_is_clamped_to_the_grid(self) -> None:
        # A span wider than the table cannot reach past the last column.
        plan = build_plan([_row(_cell("x", colspan=9))], 2)
        placed = plan[0].cells
        assert len(placed) == 1
        assert placed[0].colspan == 2


class TestColumnWidths:
    def test_width_follows_the_widest_cell(self) -> None:
        layout = _layout([Column.new(Text.raw("h")), Column.new(Text.raw("h"))])
        plan = build_plan([_row(_cell("aaaa"), _cell("b"))], 2)
        widths = column_widths(layout, plan, 80)
        assert widths[0] == 4
        assert widths[1] == 1

    def test_header_counts_towards_the_width(self) -> None:
        layout = _layout([Column.new(Text.raw("header"))])
        plan = build_plan([_row(_cell("x"))], 1)
        assert column_widths(layout, plan, 80)[0] == len("header")

    def test_header_is_ignored_when_hidden(self) -> None:
        layout = _layout([Column.new(Text.raw("header"))], header=False)
        plan = build_plan([_row(_cell("x"))], 1)
        assert column_widths(layout, plan, 80)[0] == 1

    def test_fixed_width_overrides_the_natural_width(self) -> None:
        layout = _layout([Column.new(Text.raw("h")).fixed_width(9)])
        plan = build_plan([_row(_cell("aaaaaaaaaaaa"))], 1)
        assert column_widths(layout, plan, 80)[0] == 9

    def test_min_width_raises_a_narrow_column(self) -> None:
        layout = _layout([Column.new(Text.raw("h")).min_width(7)])
        plan = build_plan([_row(_cell("a"))], 1)
        assert column_widths(layout, plan, 80)[0] == 7

    def test_max_width_caps_a_wide_column(self) -> None:
        layout = _layout([Column.new(Text.raw("h")).max_width(3)])
        plan = build_plan([_row(_cell("aaaaaaaa"))], 1)
        assert column_widths(layout, plan, 80)[0] == 3

    def test_columns_shrink_to_fit_the_budget(self) -> None:
        layout = _layout([Column.new(Text.raw("a")), Column.new(Text.raw("b"))])
        plan = build_plan([_row(_cell("x" * 40), _cell("y" * 40))], 2)
        widths = column_widths(layout, plan, 30)
        assert sum(widths) < 80

    def test_wrapping_columns_give_up_width_first(self) -> None:
        # The shrink pass takes from wrapping columns before it touches the
        # ones that would have to truncate.
        wrapping = Column.new(Text.raw("w")).wrap()
        fixed = Column.new(Text.raw("f"))
        layout = _layout([wrapping, fixed])
        plan = build_plan([_row(_cell("x" * 30), _cell("y" * 30))], 2)
        widths = column_widths(layout, plan, 40)
        assert widths[0] < widths[1]

    def test_a_tiny_budget_still_yields_non_negative_widths(self) -> None:
        layout = _layout([Column.new(Text.raw("a")), Column.new(Text.raw("b"))])
        plan = build_plan([_row(_cell("x" * 20), _cell("y" * 20))], 2)
        widths = column_widths(layout, plan, 1)
        assert all(width >= 0 for width in widths)

    def test_a_generous_budget_leaves_natural_widths_alone(self) -> None:
        layout = _layout([Column.new(Text.raw("a"))])
        plan = build_plan([_row(_cell("hello"))], 1)
        assert column_widths(layout, plan, 200)[0] == 5

    def test_colspan_cells_do_not_drive_a_single_column(self) -> None:
        # A cell spanning two columns must not blow up either column's width.
        layout = _layout([Column.new(Text.raw("a")), Column.new(Text.raw("b"))])
        plan = build_plan([_row(_cell("x" * 20, colspan=2))], 2)
        widths = column_widths(layout, plan, 80)
        assert widths[0] <= 1
