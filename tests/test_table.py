"""Tests for the Table output widget, including Column and Cell."""

from __future__ import annotations

from sparcli.core.border import BorderType
from sparcli.core.color import Color
from sparcli.core.geometry import Align
from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.width import visible_width
from sparcli.output.table import Cell, Column, Table


def plain_lines(rendered: Rendered) -> list[str]:
    """Returns each rendered line as plain text for assertions."""
    return [line.plain() for line in rendered.lines]


def outer_width(rendered: Rendered) -> int:
    """Returns the width of the widest rendered line."""
    return max(
        (visible_width(line) for line in plain_lines(rendered)), default=0
    )


class TestBorders:
    def test_header_and_rows_with_single_border(self) -> None:
        table = (
            Table()
            .columns(["A", "B"])
            .row(["1", "2"])
            .border(BorderType.SINGLE)
        )
        lines = plain_lines(table.render(80))
        assert lines[0].startswith("┌")
        assert "A" in lines[1] and "B" in lines[1]
        assert lines[2].startswith("├")
        assert "1" in lines[3] and "2" in lines[3]
        assert lines[4].startswith("└")

    def test_each_border_type_uses_its_corner_glyph(self) -> None:
        corners = {
            BorderType.SINGLE: "┌",
            BorderType.DOUBLE: "╔",
            BorderType.ROUNDED: "╭",
            BorderType.THICK: "┏",
            BorderType.ASCII: "+",
        }
        for border, corner in corners.items():
            table = Table().columns(["A", "B"]).row(["1", "2"]).border(border)
            lines = plain_lines(table.render(80))
            assert lines[0].startswith(corner)

    def test_border_none_draws_no_edges(self) -> None:
        table = (
            Table().columns(["A", "B"]).row(["1", "2"]).border(BorderType.NONE)
        )
        joined = "\n".join(plain_lines(table.render(80)))
        assert "┌" not in joined and "+" not in joined
        assert "A" in joined and "1" in joined


class TestAlignment:
    def test_right_alignment_pads_on_the_left(self) -> None:
        table = (
            Table()
            .header(False)
            .column(Column.new("").align(Align.RIGHT).min_width(3))
            .row(["7"])
            .border(BorderType.ASCII)
        )
        lines = plain_lines(table.render(80))
        assert "|   7 |" in lines

    def test_left_alignment_pads_on_the_right(self) -> None:
        table = (
            Table()
            .header(False)
            .column(Column.new("").min_width(3))
            .row(["7"])
            .border(BorderType.ASCII)
        )
        lines = plain_lines(table.render(80))
        assert "| 7   |" in lines


class TestWidthClamping:
    def test_min_width_widens_a_narrow_column(self) -> None:
        table = (
            Table()
            .header(False)
            .column(Column.new("").min_width(6))
            .row(["x"])
            .border(BorderType.SINGLE)
        )
        assert outer_width(table.render(80)) == 6 + 2 * 1 + 2

    def test_max_width_truncates_overlong_cells(self) -> None:
        table = (
            Table()
            .header(False)
            .column(Column.new("").max_width(4))
            .row(["abcdefgh"])
            .border(BorderType.SINGLE)
        )
        lines = plain_lines(table.render(80))
        assert any("abc…" in line for line in lines)

    def test_fixed_width_overrides_natural_width(self) -> None:
        table = (
            Table()
            .header(False)
            .column(Column.new("").fixed_width(8))
            .row(["xy"])
            .border(BorderType.SINGLE)
        )
        assert outer_width(table.render(80)) == 8 + 2 * 1 + 2


class TestSpanning:
    def test_colspan_widens_a_cell(self) -> None:
        table = (
            Table()
            .columns(["A", "B"])
            .row([Cell.new("wide").colspan(2)])
            .border(BorderType.SINGLE)
        )
        lines = plain_lines(table.render(80))
        assert any("wide" in line for line in lines)

    def test_rowspan_spans_following_rows(self) -> None:
        table = (
            Table()
            .header(False)
            .columns(["A", "B"])
            .row([Cell.new("x").rowspan(2), Cell.new("1")])
            .row(["2"])
            .border(BorderType.SINGLE)
        )
        lines = plain_lines(table.render(80))
        assert any("x" in line and "1" in line for line in lines)
        two = next(line for line in lines if "2" in line)
        assert "x" not in two


class TestStriping:
    def test_striped_odd_body_row_carries_the_fill_background(self) -> None:
        stripe = Style().with_bg(Color.RED)
        table = (
            Table()
            .striped(True)
            .stripe_style(stripe)
            .columns(["A"])
            .row(["1"])
            .row(["2"])
            .border(BorderType.SINGLE)
        )
        rendered = table.render(80)
        first_body = rendered.lines[3]
        second_body = rendered.lines[4]
        assert not any(span.style.bg == Color.RED for span in first_body.spans)
        assert any(span.style.bg == Color.RED for span in second_body.spans)

    def test_striping_leaves_the_text_unchanged(self) -> None:
        base = Table().columns(["A"]).row(["1"]).row(["2"])
        striped = Table().striped(True).columns(["A"]).row(["1"]).row(["2"])
        assert plain_lines(base.render(80)) == plain_lines(striped.render(80))


class TestSeparatorsAndFooter:
    def test_row_separators_between_body_rows(self) -> None:
        table = (
            Table()
            .header(False)
            .row_separators(True)
            .columns(["A", "B"])
            .row(["1", "2"])
            .row(["3", "4"])
            .border(BorderType.SINGLE)
        )
        lines = plain_lines(table.render(80))
        assert lines[0].startswith("┌")
        assert lines[2].startswith("├")
        assert lines[4].startswith("└")

    def test_footer_row_follows_a_separator(self) -> None:
        table = (
            Table()
            .columns(["A", "B"])
            .row(["1", "2"])
            .footer_row(["S", "T"])
            .border(BorderType.SINGLE)
        )
        lines = plain_lines(table.render(80))
        footer_index = next(i for i, line in enumerate(lines) if "S" in line)
        assert lines[footer_index - 1].startswith("├")
        assert "T" in lines[footer_index]


class TestTitle:
    def test_title_is_centered_above_the_table(self) -> None:
        table = (
            Table()
            .title("Report")
            .columns(["A", "B"])
            .row(["1", "2"])
            .border(BorderType.SINGLE)
        )
        lines = plain_lines(table.render(80))
        assert lines[0].strip() == "Report"
        assert lines[0].startswith(" ")
        assert lines[1].startswith("┌")


class TestWrappingAndFitting:
    def test_wrap_column_reflows_onto_multiple_lines(self) -> None:
        table = (
            Table()
            .header(False)
            .column(Column.new("").wrap().max_width(5))
            .row(["hello world foo"])
            .border(BorderType.SINGLE)
        )
        lines = plain_lines(table.render(80))
        assert any("hello" in line for line in lines)
        assert any("world" in line for line in lines)
        assert any("foo" in line for line in lines)
        assert not any("…" in line for line in lines)

    def test_a_fitting_table_is_identical_regardless_of_width(self) -> None:
        table = (
            Table()
            .columns(["A", "B"])
            .row(["1", "2"])
            .border(BorderType.SINGLE)
        )
        assert plain_lines(table.render(80)) == plain_lines(table.render(1000))

    def test_overflow_reflows_wrapping_columns_before_truncating(self) -> None:
        table = (
            Table()
            .header(False)
            .column(Column.new("").wrap())
            .column(Column.new("").align(Align.RIGHT))
            .row(["aaaaaaaaaaaaaaaaaaaa", "12345"])
            .border(BorderType.SINGLE)
        )
        rendered = table.render(20)
        lines = plain_lines(rendered)
        assert any("12345" in line for line in lines)
        assert not any("…" in line for line in lines)
        assert len(lines) > 3
        assert outer_width(rendered) <= 20

    def test_overflow_truncates_the_widest_non_wrapping_column(self) -> None:
        table = (
            Table()
            .header(False)
            .columns(["A", "B"])
            .row(["abcdefghijklmnop", "xy"])
            .border(BorderType.SINGLE)
        )
        rendered = table.render(16)
        lines = plain_lines(rendered)
        assert any("xy" in line for line in lines)
        assert any("…" in line for line in lines)
        assert outer_width(rendered) <= 16

    def test_fixed_width_column_never_shrinks(self) -> None:
        table = (
            Table()
            .header(False)
            .column(Column.new("").fixed_width(8))
            .column(Column.new("").wrap())
            .row(["FIXEDVAL", "aaaaaaaaaaaaaaaa"])
            .border(BorderType.SINGLE)
        )
        rendered = table.render(20)
        assert any("FIXEDVAL" in line for line in plain_lines(rendered))
        assert outer_width(rendered) <= 20

    def test_column_never_shrinks_below_its_min_width(self) -> None:
        table = (
            Table()
            .header(False)
            .column(Column.new("").min_width(10))
            .row(["x"])
            .border(BorderType.SINGLE)
        )
        assert outer_width(table.render(5)) > 5


class TestEmpty:
    def test_a_table_without_columns_renders_nothing(self) -> None:
        assert plain_lines(Table().render(80)) == []
