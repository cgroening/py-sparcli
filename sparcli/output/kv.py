"""
sparcli.output.kv
=================

Defines :class:`KeyValue`, an aligned list of key-value pairs.

Keys are padded to a common column width (the widest key, or a fixed width) and
joined to their values by a separator. Keys are bold by default and values use
the secondary style; long values can be wrapped across several rows, with the
key shown only on the first row. Both a keyword constructor and fluent builders
are provided.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sparcli.core.geometry import Edges
from sparcli.core.render import Renderable, Rendered
from sparcli.core.style import Style
from sparcli.core.text import IntoText, Line, Span, Text, into_text
from sparcli.core.theme import theme
from sparcli.core.width import visible_width, wrap
from sparcli.output.compose import pad

_DEFAULT_SEPARATOR = "  "
_MIN_VALUE_WIDTH = 1


@dataclass(frozen=True, slots=True)
class _Pair:
    """One key-value pair with a plain key and rich value."""

    key: str
    value: Text = field(default_factory=Text)


class KeyValue(Renderable):
    """A list of aligned key-value pairs."""

    __slots__ = (
        "_item_gap",
        "_key_style",
        "_key_width",
        "_margin",
        "_pairs",
        "_separator",
        "_value_style",
        "_wrap_values",
    )

    def __init__(
        self,
        *,
        separator: str = _DEFAULT_SEPARATOR,
        key_width: int | None = None,
        key_style: Style | None = None,
        value_style: Style | None = None,
        item_gap: int = 0,
        wrap_values: bool = False,
        margin: Edges | None = None,
    ) -> None:
        self._pairs: list[_Pair] = []
        self._separator = separator
        self._key_width = key_width
        self._key_style = (
            key_style if key_style is not None else Style.new().bold()
        )
        self._value_style = (
            value_style if value_style is not None else theme().secondary
        )
        self._item_gap = item_gap
        self._wrap_values = wrap_values
        self._margin = margin if margin is not None else Edges()

    def add(self, key: str, value: IntoText) -> KeyValue:
        """Adds a key-value pair and returns the list."""
        self._pairs.append(_Pair(key=key, value=into_text(value)))
        return self

    def separator(self, separator: str) -> KeyValue:
        """Sets the separator between key and value and returns the list."""
        self._separator = separator
        return self

    def key_width(self, width: int) -> KeyValue:
        """Sets a fixed key column width and returns the list."""
        self._key_width = width
        return self

    def key_style(self, style: Style) -> KeyValue:
        """Sets the key style and returns the list."""
        self._key_style = style
        return self

    def value_style(self, style: Style) -> KeyValue:
        """Sets the value style and returns the list."""
        self._value_style = style
        return self

    def item_gap(self, gap: int) -> KeyValue:
        """Sets the number of blank lines between pairs and returns the list."""
        self._item_gap = gap
        return self

    def wrap_values(self, wrap_values: bool) -> KeyValue:
        """Enables or disables value wrapping and returns the list."""
        self._wrap_values = wrap_values
        return self

    def margin(self, margin: Edges) -> KeyValue:
        """Sets the outer margin and returns the list."""
        self._margin = margin
        return self

    def render(self, max_width: int) -> Rendered:
        """
        Renders the aligned pairs into at most ``max_width`` columns.

        Parameters
        ----------
        max_width : int
            The number of columns available for the block.

        Returns
        -------
        Rendered
            The laid-out block of styled lines.
        """
        key_width = self._resolved_key_width()
        prefix_width = key_width + visible_width(self._separator)
        value_width = max(_MIN_VALUE_WIDTH, max_width - prefix_width)
        lines: list[Line] = []
        for index, pair in enumerate(self._pairs):
            if index > 0:
                _push_gap(lines, self._item_gap)
            self._push_pair(lines, pair, key_width, value_width)
        return pad(Rendered(lines), self._margin)

    def _resolved_key_width(self) -> int:
        """Returns the effective key column width."""
        if self._key_width is not None:
            return self._key_width
        return max((visible_width(pair.key) for pair in self._pairs), default=0)

    def _push_pair(
        self,
        lines: list[Line],
        pair: _Pair,
        key_width: int,
        value_width: int,
    ) -> None:
        """Renders one pair, wrapping the value into rows when enabled."""
        for row, value_line in enumerate(self._value_lines(pair, value_width)):
            key_cell = pair.key if row == 0 else ""
            lines.append(self._compose_line(key_cell, key_width, value_line))

    def _value_lines(self, pair: _Pair, value_width: int) -> list[Line]:
        """Splits a pair's value into one or more display lines."""
        if not self._wrap_values:
            return list(pair.value.lines)
        out: list[Line] = []
        for line in pair.value.lines:
            for chunk in wrap(line.plain(), value_width):
                out.append(Line.styled(chunk, self._value_style))
        return out

    def _compose_line(self, key: str, key_width: int, value_line: Line) -> Line:
        """Composes a padded key cell, separator and value into one line."""
        key_pad = max(0, key_width - visible_width(key))
        spans = [
            Span.styled(key, self._key_style),
            Span.raw(" " * key_pad),
            Span.raw(self._separator),
        ]
        for span in value_line.spans:
            style = self._value_style.patch(span.style)
            spans.append(
                Span(content=span.content, style=style, link=span.link)
            )
        return Line(spans)


def _push_gap(lines: list[Line], count: int) -> None:
    """Pushes ``count`` blank lines onto ``lines``."""
    for _ in range(max(0, count)):
        lines.append(Line())
