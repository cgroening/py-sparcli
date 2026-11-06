"""The widget styles that come from the theme, and the ``ansi:`` tokens."""

from __future__ import annotations

from sparcli.core.border import BorderType
from sparcli.core.color import Color
from sparcli.core.markup import parse
from sparcli.core.style import Style
from sparcli.core.theme import Theme, set_theme
from sparcli.input.confirm import Confirm
from sparcli.output.diff import Diff
from sparcli.output.progress import ProgressOpts
from sparcli.output.table.table import Table


class TestThemeDefaults:
    def test_the_new_fields_keep_the_previous_look(self) -> None:
        defaults = Theme()
        assert defaults.diff_add == Style.from_color(Color.GREEN)
        assert defaults.diff_delete == Style.from_color(Color.RED)
        assert defaults.progress_empty == Color.DARK_GRAY
        assert defaults.code == Style.from_color(Color.CYAN)
        assert defaults.stripe == Style.new().dim()


class TestWidgetsReadTheTheme:
    def test_diff_lines_take_the_theme_styles(self) -> None:
        set_theme(
            Theme(
                diff_add=Style.from_color(Color.BLUE),
                diff_delete=Style.from_color(Color.MAGENTA),
            )
        )
        rendered = Diff("a", "b").no_header().render(80)
        colors = {
            span.style.fg for line in rendered.lines for span in line.spans
        }
        assert Color.BLUE in colors
        assert Color.MAGENTA in colors

    def test_the_empty_progress_bar_takes_the_theme_color(self) -> None:
        set_theme(Theme(progress_empty=Color.BLUE))
        assert ProgressOpts.defaults().empty_color == Color.BLUE

    def test_code_spans_take_the_theme_style(self) -> None:
        set_theme(Theme(code=Style.from_color(Color.MAGENTA)))
        spans = parse("`x`").lines[0].spans
        assert any(span.style.fg == Color.MAGENTA for span in spans)

    def test_table_stripes_take_the_theme_style(self) -> None:
        set_theme(Theme(stripe=Style().with_bg(Color.BLUE)))
        rendered = (
            Table()
            .striped(True)
            .columns(["A"])
            .row(["1"])
            .row(["2"])
            .border(BorderType.SINGLE)
            .render(80)
        )
        second_body = rendered.lines[4]
        assert any(span.style.bg == Color.BLUE for span in second_body.spans)

    def test_the_unselected_confirm_button_takes_the_hint_style(self) -> None:
        set_theme(Theme(hint=Style.from_color(Color.BLUE)))
        lines = Confirm("Go?").frame().lines
        spans = [span for line in lines for span in line.spans]
        assert any(
            span.content.strip() == "Yes" and span.style.fg == Color.BLUE
            for span in spans
        )


class TestAnsiTokens:
    def test_every_terminal_color_has_a_token(self) -> None:
        names = [
            "black", "red", "green", "yellow", "blue", "magenta", "cyan",
            "gray", "dark_gray", "light_red", "light_green", "light_yellow",
            "light_blue", "light_magenta", "light_cyan", "white",
        ]
        for name in names:
            assert Color.from_name(f"ansi:{name}") is not None, name

    def test_white_is_the_bright_white_and_grey_is_accepted(self) -> None:
        assert Color.from_name("ansi:white") == Color.WHITE
        assert Color.from_name("ANSI:Dark_Grey") == Color.DARK_GRAY

    def test_an_unknown_token_is_none(self) -> None:
        assert Color.from_name("ansi:orange") is None
