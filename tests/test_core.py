"""Tests for the core layer: color, style, width, render and markup."""

from __future__ import annotations

import io

from sparcli.core.color import Color
from sparcli.core.markup import parse
from sparcli.core.render import Rendered, write_rendered
from sparcli.core.style import Attribute, Style
from sparcli.core.terminal import ColorSupport
from sparcli.core.text import Line, Span
from sparcli.core.theme import Theme, set_theme, theme
from sparcli.core.width import strip_ansi, truncate, visible_width, wrap


def render_to_string(rendered: Rendered, support: ColorSupport) -> str:
    """Renders a block to a string for assertions."""
    buffer = io.StringIO()
    write_rendered(buffer, rendered, support)
    return buffer.getvalue()


class TestColor:
    def test_from_hex_parses_six_digits(self) -> None:
        assert Color.from_hex("#ff8800") == Color.rgb(255, 136, 0)

    def test_from_hex_rejects_malformed(self) -> None:
        assert Color.from_hex("#fff") is None

    def test_from_name_is_case_insensitive_with_aliases(self) -> None:
        assert Color.from_name("  Purple ") == Color.MAGENTA

    def test_named_resolves_to_ansi16_index(self) -> None:
        assert Color.RED.resolve(ColorSupport.ANSI16) == ("ansi16", 1)

    def test_none_support_resolves_to_nothing(self) -> None:
        assert Color.RED.resolve(ColorSupport.NONE) is None

    def test_rgb_downgrades_to_ansi16(self) -> None:
        resolved = Color.rgb(200, 0, 0).resolve(ColorSupport.ANSI16)
        assert resolved == ("ansi16", 9)


class TestStyle:
    def test_patch_prefers_other_colors_and_unions_attrs(self) -> None:
        base = Style.from_color(Color.RED).bold()
        top = Style.from_color(Color.BLUE).italic()
        merged = base.patch(top)
        assert merged.fg == Color.BLUE
        assert merged.attrs.contains(Attribute.BOLD)
        assert merged.attrs.contains(Attribute.ITALIC)


class TestWidth:
    def test_visible_width_ignores_ansi(self) -> None:
        assert visible_width("\x1b[31mred\x1b[0m") == 3

    def test_wide_glyphs_count_two(self) -> None:
        assert visible_width("中文") == 4

    def test_truncate_appends_ellipsis(self) -> None:
        assert truncate("hello world", 8) == "hello w…"

    def test_strip_ansi_removes_sequences(self) -> None:
        assert strip_ansi("\x1b[1mhi\x1b[0m") == "hi"

    def test_wrap_breaks_on_words(self) -> None:
        assert wrap("one two three", 7) == ["one two", "three"]

    def test_wrap_treats_tabs_and_runs_as_separators(self) -> None:
        # Wrapping splits on whitespace runs (tabs, repeated spaces), matching
        # Rust's split_whitespace rather than a single-space split.
        assert wrap("a\tb\tc", 10) == ["a b c"]
        assert wrap("a   b", 10) == ["a b"]


class TestRender:
    def test_plain_text_has_no_escapes(self) -> None:
        rendered = Rendered([Line.raw("hello")])
        assert render_to_string(rendered, ColorSupport.NONE) == "hello\n"

    def test_styled_span_emits_escape(self) -> None:
        span = Span.styled("hi", Style.from_color(Color.RED))
        output = render_to_string(
            Rendered([Line([span])]), ColorSupport.TRUECOLOR
        )
        assert "\x1b[" in output
        assert "hi" in output

    def test_link_emits_osc8(self) -> None:
        span = Span.raw("site").with_link("https://example.com")
        output = render_to_string(Rendered([Line([span])]), ColorSupport.ANSI16)
        assert "https://example.com" in output


class TestMarkup:
    def test_bold_tag_applies_attribute(self) -> None:
        text = parse("[bold]hi[/]")
        span = text.lines[0].spans[0]
        assert span.style.attrs.contains(Attribute.BOLD)
        assert span.content == "hi"

    def test_unknown_bracket_is_literal(self) -> None:
        text = parse("a [b")
        assert text.lines[0].plain() == "a [b"


class TestTheme:
    def test_set_theme_replaces_active_theme(self) -> None:
        original = theme()
        try:
            set_theme(Theme(unicode=False))
            assert theme().unicode is False
            assert theme().bullet() == "*"
        finally:
            set_theme(original)
