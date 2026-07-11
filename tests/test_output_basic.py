"""Tests for the basic output widgets: Badge, Rule, KeyValue and Columns."""

from __future__ import annotations

from sparcli.core.border import BorderType
from sparcli.core.geometry import Align, VAlign
from sparcli.core.render import Rendered
from sparcli.core.style import Attribute
from sparcli.core.text import Line
from sparcli.core.theme import theme
from sparcli.output.badge import Badge
from sparcli.output.columns import Columns
from sparcli.output.kv import KeyValue
from sparcli.output.rule import Rule


def _plain(rendered: Rendered) -> list[str]:
    """Returns the plain text of each rendered line."""
    return [line.plain() for line in rendered.lines]


class TestBadge:
    def test_wraps_text_in_default_caps(self) -> None:
        assert Badge("OK").span().content == "[OK]"

    def test_honors_custom_caps_and_pad(self) -> None:
        span = Badge("v1").caps("(", ")").pad(1).span()
        assert span.content == "( v1 )"

    def test_default_style_is_accent_bold(self) -> None:
        style = Badge("x").span().style
        assert style.fg == theme().accent
        assert style.attrs.contains(Attribute.BOLD)

    def test_render_yields_single_line(self) -> None:
        rendered = Badge("OK").render(80)
        assert _plain(rendered) == ["[OK]"]


class TestRule:
    def test_plain_rule_fills_the_width(self) -> None:
        rendered = Rule(border=BorderType.SINGLE).render(10)
        assert _plain(rendered) == ["─" * 10]

    def test_none_border_fills_with_spaces(self) -> None:
        rendered = Rule(border=BorderType.NONE).render(6)
        assert _plain(rendered) == [" " * 6]

    def test_titled_rule_embeds_title_and_keeps_width(self) -> None:
        rendered = Rule("Section", border=BorderType.SINGLE).render(20)
        assert "Section" in rendered.lines[0].plain()
        assert rendered.lines[0].width() == 20

    def test_left_aligned_title_keeps_single_connector(self) -> None:
        rendered = Rule(
            "Hi", border=BorderType.SINGLE, align=Align.LEFT
        ).render(20)
        first = rendered.lines[0]
        assert first.spans[0].content == "─"
        assert first.plain().startswith("─ Hi ")
        assert first.width() == 20

    def test_title_replaces_line_when_too_wide(self) -> None:
        rendered = Rule("LongTitle", border=BorderType.SINGLE).render(5)
        assert _plain(rendered) == ["LongTitle"]

    def test_with_title_classmethod(self) -> None:
        rendered = Rule.with_title("Mid").border(BorderType.SINGLE).render(11)
        assert "Mid" in rendered.lines[0].plain()
        assert rendered.lines[0].width() == 11


class TestKeyValue:
    def test_aligns_keys_to_the_widest(self) -> None:
        kv = KeyValue().add("a", "1").add("name", "2")
        lines = _plain(kv.render(40))
        assert lines[0] == "a     1"
        assert lines[1] == "name  2"

    def test_key_is_bold_and_separator_present(self) -> None:
        kv = KeyValue().add("a", "1")
        line = kv.render(40).lines[0]
        assert line.spans[0].content == "a"
        assert line.spans[0].style.attrs.contains(Attribute.BOLD)
        assert line.spans[2].content == "  "

    def test_custom_separator_is_used(self) -> None:
        kv = KeyValue(separator=" = ").add("k", "v")
        assert kv.render(40).lines[0].plain() == "k = v"

    def test_wraps_long_values_when_enabled(self) -> None:
        kv = KeyValue(wrap_values=True).add("k", "one two three four")
        lines = _plain(kv.render(10))
        assert len(lines) > 1

    def test_item_gap_inserts_blank_lines(self) -> None:
        kv = KeyValue(item_gap=1).add("a", "1").add("b", "2")
        lines = _plain(kv.render(40))
        assert len(lines) == 3
        assert lines[1].strip() == ""


class TestColumns:
    def test_places_blocks_side_by_side(self) -> None:
        left = Rendered([Line.raw("a"), Line.raw("b")])
        right = Rendered([Line.raw("x"), Line.raw("y")])
        columns = Columns().add_rendered(left).add_rendered(right).gap(2)
        lines = _plain(columns.render(80))
        assert lines[0] == "a  x"
        assert lines[1] == "b  y"

    def test_pads_shorter_columns(self) -> None:
        left = Rendered([Line.raw("a"), Line.raw("b")])
        right = Rendered([Line.raw("x")])
        columns = Columns().add_rendered(left).add_rendered(right).gap(1)
        lines = _plain(columns.render(80))
        assert lines[0] == "a x"
        assert lines[1].rstrip() == "b"

    def test_bottom_valign_pushes_shorter_column_down(self) -> None:
        left = Rendered([Line.raw("a"), Line.raw("b"), Line.raw("c")])
        right = Rendered([Line.raw("x")])
        columns = (
            Columns(valign=VAlign.BOTTOM)
            .add_rendered(left)
            .add_rendered(right)
            .gap(1)
        )
        lines = _plain(columns.render(80))
        assert lines[0].rstrip() == "a"
        assert lines[2] == "c x"

    def test_draws_separator_between_columns(self) -> None:
        left = Rendered([Line.raw("a")])
        right = Rendered([Line.raw("b")])
        columns = (
            Columns()
            .add_rendered(left)
            .add_rendered(right)
            .gap(3)
            .separator(BorderType.SINGLE)
        )
        line = columns.render(80).lines[0]
        assert "│" in line.plain()
        assert line.plain() == "a │ b"

    def test_empty_columns_render_nothing(self) -> None:
        assert _plain(Columns().render(80)) == []

    def test_align_sets_last_column_alignment(self) -> None:
        left = Rendered([Line.raw("a"), Line.raw("b")])
        right = Rendered([Line.raw("xx"), Line.raw("y")])
        columns = (
            Columns()
            .add_rendered(left)
            .add_rendered(right)
            .align(Align.RIGHT)
            .gap(1)
        )
        lines = _plain(columns.render(80))
        assert lines[0] == "a xx"
        assert lines[1] == "b  y"
