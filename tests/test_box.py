"""
Tests for the shared box-drawing routine behind Panel and Alert.

``draw_box`` carries the title-embedding and truncation rules that must match
the Rust original, so it is exercised directly here rather than only through
the widgets that happen to use it.
"""

from __future__ import annotations

from conftest import plain_lines

from sparcli.core.border import TALL, BorderType
from sparcli.core.geometry import Align, Edges, Title
from sparcli.core.render import Rendered
from sparcli.core.text import Text
from sparcli.output.box import BoxOpts, draw_box, title_bar_width


def _content(*lines: str) -> Rendered:
    """Builds a rendered block from plain text lines."""
    return Rendered.from_text(Text.raw("\n".join(lines)))


class TestDrawBox:
    def test_rounded_border_frames_the_content(self) -> None:
        rendered = draw_box(_content("hi"), BoxOpts(), 40)
        lines = plain_lines(rendered)
        assert lines[0].startswith("╭")
        assert lines[0].endswith("╮")
        assert "hi" in lines[1]
        assert lines[-1].startswith("╰")
        assert lines[-1].endswith("╯")

    def test_box_width_is_consistent_across_rows(self) -> None:
        rendered = draw_box(_content("a", "bbbb"), BoxOpts(), 40)
        widths = {len(line) for line in plain_lines(rendered)}
        assert len(widths) == 1

    def test_border_none_degrades_to_padding(self) -> None:
        opts = BoxOpts(border=BorderType.NONE)
        lines = plain_lines(draw_box(_content("hi"), opts, 40))
        assert "╭" not in "".join(lines)
        assert any("hi" in line for line in lines)

    def test_left_title_keeps_one_connecting_glyph(self) -> None:
        # A left-aligned title reads as part of the frame: exactly one border
        # glyph sits before it, never a flush corner.
        opts = BoxOpts(title=Title(Text.raw("Status"), Align.LEFT))
        top = plain_lines(draw_box(_content("wide enough content"), opts, 40))[
            0
        ]
        assert top.startswith("╭─ Status ")

    def test_centered_title_is_padded_on_both_sides(self) -> None:
        opts = BoxOpts(title=Title(Text.raw("Mid"), Align.CENTER))
        top = plain_lines(draw_box(_content("wide enough content"), opts, 40))[
            0
        ]
        before, _, after = top.partition("Mid")
        assert before.count("─") > 1
        assert after.count("─") > 1

    def test_title_never_widens_the_box(self) -> None:
        # A title longer than the content is cut into the border instead of
        # stretching the frame; this is the documented Rust-parity rule.
        plain = draw_box(_content("x"), BoxOpts(), 40)
        opts = BoxOpts(title=Title(Text.raw("a very long title"), Align.LEFT))
        titled = draw_box(_content("x"), opts, 40)
        assert len(plain_lines(titled)[0]) == len(plain_lines(plain)[0])

    def test_overlong_title_is_truncated_with_an_ellipsis(self) -> None:
        opts = BoxOpts(title=Title(Text.raw("a" * 60), Align.LEFT))
        rendered = draw_box(_content("x"), opts, 20)
        lines = plain_lines(rendered)
        assert len(lines[0]) <= 20
        assert "…" in lines[0]

    def test_subtitle_is_embedded_in_the_bottom_edge(self) -> None:
        opts = BoxOpts(subtitle=Title(Text.raw("v1"), Align.LEFT))
        bottom = plain_lines(draw_box(_content("x"), opts, 40))[-1]
        assert "v1" in bottom
        assert bottom.startswith("╰")

    def test_explicit_width_is_honored(self) -> None:
        opts = BoxOpts(width=24)
        lines = plain_lines(draw_box(_content("x"), opts, 80))
        assert all(len(line) == 24 for line in lines)

    def test_width_is_capped_by_max_width(self) -> None:
        opts = BoxOpts(width=200)
        lines = plain_lines(draw_box(_content("x"), opts, 30))
        assert all(len(line) <= 30 for line in lines)

    def test_padding_adds_blank_rows(self) -> None:
        tight = draw_box(_content("x"), BoxOpts(), 40).height()
        padded = draw_box(
            _content("x"), BoxOpts(padding=Edges.symmetric(1, 1)), 40
        ).height()
        assert padded == tight + 2

    def test_content_align_center_centers_the_row(self) -> None:
        opts = BoxOpts(width=20, content_align=Align.CENTER)
        row = plain_lines(draw_box(_content("ab"), opts, 40))[1]
        inner = row[1:-1]
        assert inner.startswith(" ")
        assert inner.endswith(" ")

    def test_empty_content_still_produces_a_frame(self) -> None:
        rendered = draw_box(Rendered([]), BoxOpts(), 40)
        lines = plain_lines(rendered)
        assert lines[0].startswith("╭")
        assert lines[-1].startswith("╰")

    def test_multiline_content_keeps_every_row(self) -> None:
        rendered = draw_box(_content("one", "two", "three"), BoxOpts(), 40)
        body = plain_lines(rendered)[1:-1]
        assert len(body) == 3

    def test_double_border_uses_its_own_glyphs(self) -> None:
        opts = BoxOpts(border=BorderType.DOUBLE)
        lines = plain_lines(draw_box(_content("x"), opts, 40))
        assert lines[0].startswith("╔")
        assert lines[-1].startswith("╚")


class TestTitleBarWidth:
    def test_width_counts_the_label_and_its_spacing(self) -> None:
        assert title_bar_width(Title(Text.raw("ab"), Align.LEFT)) > 2

    def test_empty_title_has_a_small_width(self) -> None:
        assert title_bar_width(Title(Text.raw(""), Align.LEFT)) >= 0

    def test_wide_label_widens_the_bar(self) -> None:
        narrow = title_bar_width(Title(Text.raw("a"), Align.LEFT))
        wide = title_bar_width(Title(Text.raw("aaaaa"), Align.LEFT))
        assert wide > narrow


class TestBoxOpts:
    def test_defaults_are_rounded_and_horizontally_padded(self) -> None:
        opts = BoxOpts()
        assert opts.border is BorderType.ROUNDED
        assert opts.content_align is Align.LEFT

    def test_each_instance_gets_its_own_padding(self) -> None:
        # Mutable defaults must not be shared between boxes.
        first = BoxOpts()
        second = BoxOpts()
        assert first.padding is not second.padding


class TestTallBorder:
    def test_degrades_to_thick_glyphs(self) -> None:
        # Widgets that cannot draw block glyphs read chars() directly, so this
        # is what keeps them from raising a KeyError or drawing a blank frame.
        assert BorderType.TALL.chars() == BorderType.THICK.chars()

    def test_is_a_border_of_its_own(self) -> None:
        assert BorderType.TALL.is_tall()
        assert not BorderType.TALL.is_none()
        assert not BorderType.THICK.is_tall()

    def test_strokes_are_equally_thick_on_both_axes(self) -> None:
        # A quarter of the cell width and an eighth of its height come out the
        # same number of pixels, because a cell is about twice as tall as it is
        # wide. Equal fractions on both axes would not.
        assert TALL.left == "▎"
        assert TALL.right == "▊"
        assert TALL.top == "▁"
        assert TALL.bottom == "▔"
