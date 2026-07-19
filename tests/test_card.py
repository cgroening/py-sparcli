"""Tests for the Card widget: surface, regions, palette and tall border."""

from __future__ import annotations

from conftest import plain_lines

from sparcli.core.border import BorderType
from sparcli.core.color import Color
from sparcli.core.geometry import Align, Edges
from sparcli.core.render import Rendered
from sparcli.core.style import Attribute, Style
from sparcli.core.terminal import ColorSupport
from sparcli.core.text import Line, Span
from sparcli.output.card import Card
from sparcli.output.card.card import CardParts
from sparcli.output.card.palette import derive
from sparcli.output.card.render import RenderCaps, render_card

ACCENT = Color.rgb(137, 180, 250)


def _render(card: Card, width: int, caps: RenderCaps | None = None) -> Rendered:
    """Renders a card with explicit capabilities, bypassing detection."""
    parts = CardParts(
        content=card._content,
        title=card._title,
        footer=card._footer,
        opts=card._opts,
    )
    return render_card(parts, width, caps or RenderCaps.truecolor())


def _row_bg(rendered: Rendered, row: int) -> Color | None:
    """Returns a row's background, taken from its first span."""
    spans = rendered.lines[row].spans
    return spans[0].style.bg if spans else None


def _brightness(rgb: tuple[int, int, int]) -> int:
    """Returns the channel sum as a coarse brightness measure."""
    return sum(rgb)


class TestPalette:
    def test_derives_distinct_styles_from_one_accent(self) -> None:
        styles = derive(ACCENT, ColorSupport.TRUECOLOR)
        assert styles.border.fg == ACCENT
        assert styles.title.bg != styles.fill.bg
        assert styles.title.fg != styles.content.fg

    def test_content_surface_is_darker_than_the_title_surface(self) -> None:
        # The background step is the card's only separator between title and
        # content, so their ordering is pinned independently of the constants.
        styles = derive(ACCENT, ColorSupport.TRUECOLOR)
        title = styles.title.bg
        fill = styles.fill.bg
        assert title is not None
        assert fill is not None
        title_rgb = title.to_rgb()
        fill_rgb = fill.to_rgb()
        assert title_rgb is not None
        assert fill_rgb is not None
        assert _brightness(fill_rgb) < _brightness(title_rgb)

    def test_matches_the_rust_reference_values(self) -> None:
        # The Rust port is the source of truth for behavior; these are its
        # derived tones for the default accent.
        styles = derive(ACCENT, ColorSupport.TRUECOLOR)
        assert styles.title.bg == Color.rgb(36, 51, 76)
        assert styles.fill.bg == Color.rgb(27, 32, 39)
        assert styles.content.fg == Color.rgb(182, 189, 201)

    def test_achromatic_accent_stays_neutral(self) -> None:
        # A gray accent has no hue; re-saturating the fallback hue of zero
        # would turn the whole card red.
        styles = derive(Color.rgb(160, 160, 160), ColorSupport.TRUECOLOR)
        for style in (styles.title, styles.fill, styles.content):
            assert style.bg is not None
            rgb = style.bg.to_rgb()
            assert rgb is not None
            assert rgb[0] == rgb[1] == rgb[2]

    def test_fill_and_content_share_a_background(self) -> None:
        styles = derive(ACCENT, ColorSupport.TRUECOLOR)
        assert styles.fill.bg == styles.content.bg

    def test_ansi16_support_drops_all_backgrounds(self) -> None:
        styles = derive(ACCENT, ColorSupport.ANSI16)
        for style in (styles.border, styles.title, styles.fill, styles.content):
            assert style.bg is None
        assert styles.title.fg == ACCENT
        assert styles.title.attrs.contains(Attribute.BOLD)

    def test_reset_accent_falls_back_to_the_flat_palette(self) -> None:
        styles = derive(Color.RESET, ColorSupport.TRUECOLOR)
        assert styles.fill.bg is None
        assert styles.title.bg is None


class TestCardSurface:
    def test_fills_the_full_width_by_default(self) -> None:
        out = _render(Card("hi"), 40)
        for line in out.lines:
            assert line.width() == 40

    def test_every_cell_of_the_surface_carries_a_background(self) -> None:
        # A background paints only its own span, so a single unstyled span
        # punches a transparent hole through the card. This catches the padding
        # columns, the alignment slack, the border seam and content spans that
        # were not rebased onto the surface - all at once.
        card = (
            Card("body")
            .title("Heading")
            .footer("footer")
            .border(BorderType.ROUNDED)
        )
        out = _render(card, 40)
        for line in out.lines:
            for span in line.spans:
                assert span.style.bg is not None, repr(span.content)

    def test_content_spans_keep_their_own_foreground(self) -> None:
        styled = Line([Span.styled("alert", Style.from_color(Color.RED))])
        out = _render(Card.from_rendered(Rendered([styled])), 30)
        found = next(
            span
            for line in out.lines
            for span in line.spans
            if span.content == "alert"
        )
        assert found.style.fg == Color.RED
        assert found.style.bg is not None

    def test_title_row_has_its_own_background(self) -> None:
        out = _render(Card("body").title("Heading"), 30)
        assert _row_bg(out, 0) != _row_bg(out, 2)

    def test_flat_title_shares_the_content_background(self) -> None:
        out = _render(Card("body").title("Heading").flat_title(), 30)
        assert _row_bg(out, 0) == _row_bg(out, 2)

    def test_footer_row_is_last_and_has_its_own_background(self) -> None:
        out = _render(Card("body").footer("footer"), 30)
        last = len(out.lines) - 1
        assert "footer" in plain_lines(out)[last]
        assert _row_bg(out, last) != _row_bg(out, 1)

    def test_a_custom_fill_reaches_the_body_text(self) -> None:
        card = Card("body").fill(Style.new().with_bg(Color.indexed(236)))
        out = _render(card, 30)
        assert _row_bg(out, 0) == Color.indexed(236)
        assert _row_bg(out, 1) == Color.indexed(236)

    def test_a_style_override_patches_rather_than_replaces(self) -> None:
        card = Card("body").title("Heading").title_style(Style.new().bold())
        out = _render(card, 30)
        title = next(s for s in out.lines[0].spans if s.content == "Heading")
        assert title.style.attrs.contains(Attribute.BOLD)
        assert title.style.bg is not None
        assert title.style.fg is not None


class TestCardGeometry:
    def test_wrap_is_enabled_by_default(self) -> None:
        # Surface 20 minus one padding column per side leaves 18 columns.
        card = Card("alpha beta gamma delta epsilon").width(20)
        lines = plain_lines(_render(card, 80))
        assert len(lines) == 4
        assert "alpha beta gamma" in lines[1]
        assert "delta epsilon" in lines[2]

    def test_wrap_off_truncates_with_an_ellipsis(self) -> None:
        card = Card("alpha beta gamma delta epsilon").width(20).wrap(False)
        lines = plain_lines(_render(card, 80))
        assert len(lines) == 3
        assert "…" in lines[1]

    def test_fixed_width_is_clamped_to_max_width(self) -> None:
        out = _render(Card("hi").width(200), 80)
        for line in out.lines:
            assert line.width() == 80

    def test_narrow_width_is_honored(self) -> None:
        out = _render(Card("hi").width(20), 80)
        for line in out.lines:
            assert line.width() == 20

    def test_degenerate_width_renders_nothing(self) -> None:
        card = Card("hi").width(2).border(BorderType.SINGLE)
        assert _render(card, 80).lines == []

    def test_the_two_padding_levels_are_independent(self) -> None:
        card = (
            Card("body")
            .title("Heading")
            .title_padding(Edges.all(0))
            .padding(Edges.all(2))
        )
        lines = plain_lines(_render(card, 30))
        assert len(lines) == 6
        assert lines[0].startswith("Heading")
        assert lines[3].startswith("  body")

    def test_title_and_content_align_independently(self) -> None:
        card = (
            Card("body")
            .title("Heading")
            .title_align(Align.RIGHT)
            .content_align(Align.CENTER)
            .width(20)
        )
        lines = plain_lines(_render(card, 30))
        assert lines[0].endswith("Heading ")
        assert lines[2] == "        body        "

    def test_content_wraps_to_the_content_area_not_the_surface(self) -> None:
        # Surface 20, horizontal padding 8, so the text area is 12 columns.
        card = Card("aaaa bbbb cccc").width(20).padding(Edges.symmetric(0, 4))
        lines = plain_lines(_render(card, 30))
        assert len(lines) == 2
        assert "aaaa bbbb" in lines[0]
        assert "cccc" in lines[1]

    def test_a_multiline_title_produces_one_row_per_line(self) -> None:
        lines = plain_lines(_render(Card("body").title("first\nsecond"), 30))
        assert "first" in lines[0]
        assert "second" in lines[1]


class TestTallBorder:
    def test_side_bars_are_quarter_blocks_on_opposite_edges(self) -> None:
        # ▊ inks the left three quarters, so only swapping its colors turns the
        # remaining quarter into the bar - Unicode defines no right-aligned
        # quarter block.
        out = _render(Card("body").border(BorderType.TALL), 30)
        spans = out.lines[1].spans
        left, right = spans[0], spans[-1]
        assert left.content == "▎"
        assert right.content == "▊"
        assert left.style.fg == right.style.bg
        assert left.style.bg == right.style.fg
        assert left.style.fg != left.style.bg

    def test_corners_are_closed_by_a_full_width_line(self) -> None:
        # The horizontal line runs across the corner cells too, and sits on the
        # inner side of its row, so it touches the side bar of the adjoining
        # row instead of starting a cell away from it.
        lines = plain_lines(_render(Card("body").border(BorderType.TALL), 20))
        assert lines[0] == "▁" * 20
        assert lines[-1] == "▔" * 20

    def test_horizontal_rows_carry_no_surface(self) -> None:
        # Otherwise a band of card color would sit above the top line, making
        # the frame look like it starts one row too early.
        out = _render(Card("body").border(BorderType.TALL), 30)
        for span in out.lines[0].spans:
            assert span.style.bg is None
            assert span.style.fg is not None

    def test_body_cells_keep_a_background(self) -> None:
        card = (
            Card("body")
            .title("Heading")
            .footer("footer")
            .border(BorderType.TALL)
        )
        out = _render(card, 30)
        for line in out.lines[1:-1]:
            for span in line.spans:
                assert span.style.bg is not None, repr(span.content)

    def test_degrades_to_thick_without_truecolor(self) -> None:
        caps = RenderCaps(support=ColorSupport.ANSI16, unicode=True)
        out = _render(Card("body").border(BorderType.TALL), 30, caps)
        lines = plain_lines(out)
        assert lines[0].startswith("┏")
        assert lines[0].endswith("┓")
        assert lines[1].startswith("┃")
        assert not any("▎" in line for line in lines)
        for line in out.lines:
            assert line.width() == 30

    def test_degrades_to_ascii_without_unicode(self) -> None:
        caps = RenderCaps(support=ColorSupport.TRUECOLOR, unicode=False)
        lines = plain_lines(
            _render(Card("body").border(BorderType.TALL), 30, caps)
        )
        assert lines[0].startswith("+")
        assert lines[0].endswith("+")
        assert lines[1].startswith("|")

    def test_a_non_tall_border_uses_one_glyph_on_both_sides(self) -> None:
        out = _render(Card("body").border(BorderType.ROUNDED), 30)
        spans = out.lines[1].spans
        assert spans[0].content == "│"
        assert spans[-1].content == "│"
        assert spans[0].style == spans[-1].style
