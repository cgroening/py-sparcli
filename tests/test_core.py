"""Tests for the core layer: color, style, width, render and markup."""

from __future__ import annotations

import io

import pytest

from sparcli.core.color import Color
from sparcli.core.markup import markup_print, markup_println, parse
from sparcli.core.render import Rendered, write_rendered
from sparcli.core.style import Attribute, Style
from sparcli.core.terminal import (
    ColorSupport,
    color_support,
    is_input_tty,
    is_output_tty,
)
from sparcli.core.text import Line, Span
from sparcli.core.theme import Theme, set_theme, theme
from sparcli.core.width import (
    char_width,
    strip_ansi,
    truncate,
    visible_width,
    wrap,
)


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

    def test_remove_modifier_clears_only_the_named_attribute(self) -> None:
        style = Style.new().bold().italic().remove_modifier(Attribute.BOLD)
        assert not style.attrs.contains(Attribute.BOLD)
        assert style.attrs.contains(Attribute.ITALIC)


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

    def test_char_width_handles_empty_and_multichar_input(self) -> None:
        # The single-character contract stays intact, but degenerate input
        # never raises: empty is zero and a longer string sums its cells.
        assert char_width("") == 0
        assert char_width("a") == 1
        assert char_width("中") == 2
        assert char_width("ab中") == 4


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

    def test_control_chars_are_stripped_from_content(self) -> None:
        # A raw ESC / BEL / CR in span content must not reach the terminal.
        # An unstyled span emits no escapes at all, so the injected SGR is
        # neutralised: its ESC is gone and "[31m" survives as inert text.
        span = Span.raw("a\x1b[31mb\x07\rc")
        output = render_to_string(
            Rendered([Line([span])]), ColorSupport.TRUECOLOR
        )
        assert "\x1b" not in output
        assert "\x07" not in output
        assert "\r" not in output
        assert output == "a[31mbc\n"

    def test_tab_survives_sanitization(self) -> None:
        output = render_to_string(
            Rendered([Line([Span.raw("a\tb")])]), ColorSupport.NONE
        )
        assert output == "a\tb\n"

    def test_link_injection_is_neutralized(self) -> None:
        # A crafted URL cannot terminate the OSC-8 sequence and inject escapes.
        span = Span.raw("x").with_link("http://e\x1b\\\x1b]8;;evil")
        output = render_to_string(Rendered([Line([span])]), ColorSupport.ANSI16)
        assert "\x1b\\\x1b]8;;evil" not in output


class TestMarkup:
    def test_bold_tag_applies_attribute(self) -> None:
        text = parse("[bold]hi[/]")
        span = text.lines[0].spans[0]
        assert span.style.attrs.contains(Attribute.BOLD)
        assert span.content == "hi"

    def test_unknown_bracket_is_literal(self) -> None:
        text = parse("a [b")
        assert text.lines[0].plain() == "a [b"

    def test_closed_unknown_tag_is_literal(self) -> None:
        # A closed bracket naming no style/attribute is content, not markup.
        assert parse("array[0]").lines[0].plain() == "array[0]"
        assert parse("[hello world]").lines[0].plain() == "[hello world]"

    def test_recognized_tag_still_applies_after_fix(self) -> None:
        text = parse("[red]x[/] array[0]")
        assert text.lines[0].plain() == "x array[0]"
        assert text.lines[0].spans[0].style.fg == Color.RED

    def test_markup_print_writes_the_text(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("NO_COLOR", "1")
        markup_print("[bold]hi[/]")
        assert capsys.readouterr().out == "hi\n"

    def test_markup_println_appends_a_blank_line(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("NO_COLOR", "1")
        markup_println("hi")
        assert capsys.readouterr().out == "hi\n\n"


class TestTerminalColorSupport:
    @staticmethod
    def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
        for key in (
            "NO_COLOR",
            "CLICOLOR_FORCE",
            "COLORTERM",
            "SPARCLI_NO_TTY",
        ):
            monkeypatch.delenv(key, raising=False)

    def test_no_color_forces_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._clear_env(monkeypatch)
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert color_support() is ColorSupport.NONE

    def test_clicolor_force_with_truecolor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._clear_env(monkeypatch)
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert color_support() is ColorSupport.TRUECOLOR

    def test_clicolor_force_without_colorterm_is_ansi16(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._clear_env(monkeypatch)
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert color_support() is ColorSupport.ANSI16

    def test_non_tty_without_force_is_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._clear_env(monkeypatch)
        monkeypatch.setenv("SPARCLI_NO_TTY", "1")
        monkeypatch.setenv("COLORTERM", "truecolor")
        assert color_support() is ColorSupport.NONE

    def test_no_tty_override_reports_non_tty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._clear_env(monkeypatch)
        monkeypatch.setenv("SPARCLI_NO_TTY", "1")
        assert is_output_tty() is False
        assert is_input_tty() is False


class TestTheme:
    def test_set_theme_replaces_active_theme(self) -> None:
        original = theme()
        try:
            set_theme(Theme(unicode=False))
            assert theme().unicode is False
            assert theme().bullet() == "*"
        finally:
            set_theme(original)
