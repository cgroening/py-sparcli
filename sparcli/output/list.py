"""
sparcli.output.list
===================

Defines :class:`List` and the :class:`Marker` enum: bulleted and ordered lists
with nesting and hanging indents.

A list prefixes each item with a marker (a bullet or an ordered label such as
``1.``, ``a.`` or ``iv.``). Continuation rows of a multi-line item align under
the content with a hanging indent, and nested sub-lists added via
:meth:`List.item_with` are indented beneath their parent item.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass, field

from sparcli.core.geometry import Align, Edges
from sparcli.core.render import Renderable, Rendered
from sparcli.core.style import Style
from sparcli.core.text import IntoText, Line, Span, Text, into_text
from sparcli.core.theme import theme
from sparcli.core.width import visible_width
from sparcli.output.layout import blank_line, pad_line, space_span

# Alphabet size for bijective base-26 alphabetic markers.
_ALPHA_BASE = 26

# Roman-numeral values paired with their lowercase symbols, high to low.
_NUMERALS: tuple[tuple[int, str], ...] = (
    (1000, "m"),
    (900, "cm"),
    (500, "d"),
    (400, "cd"),
    (100, "c"),
    (90, "xc"),
    (50, "l"),
    (40, "xl"),
    (10, "x"),
    (9, "ix"),
    (5, "v"),
    (4, "iv"),
    (1, "i"),
)


class Marker(enum.Enum):
    """The marker style used to label list items."""

    BULLET = enum.auto()
    NUMBER = enum.auto()
    ALPHA_LOWER = enum.auto()
    ALPHA_UPPER = enum.auto()
    ROMAN_LOWER = enum.auto()
    ROMAN_UPPER = enum.auto()


# Ordered-marker label builders keyed by marker, given a zero-based index.
_ORDERED_CORE: dict[Marker, Callable[[int], str]] = {
    Marker.NUMBER: lambda index: str(index + 1),
    Marker.ALPHA_LOWER: lambda index: _to_alpha(index, upper=False),
    Marker.ALPHA_UPPER: lambda index: _to_alpha(index, upper=True),
    Marker.ROMAN_LOWER: lambda index: _to_roman(index + 1, upper=False),
    Marker.ROMAN_UPPER: lambda index: _to_roman(index + 1, upper=True),
}


@dataclass(frozen=True, slots=True)
class _ListItem:
    """One list entry with an optional nested sub-list."""

    content: Text
    children: List | None = field(default=None)


class List(Renderable):
    """A bulleted or ordered list with optional nesting."""

    __slots__ = (
        "_marker",
        "_items",
        "_marker_style",
        "_bullet",
        "_suffix",
        "_indent",
        "_item_gap",
        "_margin",
    )

    def __init__(
        self,
        *,
        marker: Marker = Marker.BULLET,
        marker_style: Style | None = None,
        bullet: str | None = None,
        suffix: str = "",
        indent: int = 0,
        item_gap: int = 0,
        margin: Edges | None = None,
    ) -> None:
        self._marker = marker
        self._items: list[_ListItem] = []
        self._marker_style = (
            marker_style if marker_style is not None else theme().secondary
        )
        self._bullet = bullet
        self._suffix = suffix
        self._indent = indent
        self._item_gap = item_gap
        self._margin = margin if margin is not None else Edges()

    @classmethod
    def ordered(cls, marker: Marker) -> List:
        """
        Returns an empty ordered list using ``marker`` with a ``.`` suffix.

        Parameters
        ----------
        marker : Marker
            The ordered marker style. ``Marker.BULLET`` yields no suffix.

        Returns
        -------
        List
            The configured, empty list.
        """
        suffix = "" if marker is Marker.BULLET else "."
        return cls(marker=marker, suffix=suffix)

    def item(self, content: IntoText) -> List:
        """Adds a leaf item and returns the list."""
        self._items.append(_ListItem(content=into_text(content)))
        return self

    def item_with(self, content: IntoText, children: List) -> List:
        """Adds an item carrying a nested sub-list and returns the list."""
        self._items.append(
            _ListItem(content=into_text(content), children=children)
        )
        return self

    def bullet(self, glyph: str) -> List:
        """Sets a custom bullet glyph (bullet marker only)."""
        self._bullet = glyph
        return self

    def marker_style(self, style: Style) -> List:
        """Sets the marker style and returns the list."""
        self._marker_style = style
        return self

    def indent(self, indent: int) -> List:
        """Sets the left indent in columns and returns the list."""
        self._indent = indent
        return self

    def item_gap(self, gap: int) -> List:
        """Sets the number of blank lines between items."""
        self._item_gap = gap
        return self

    def margin(self, margin: Edges) -> List:
        """Sets the outer margin and returns the list."""
        self._margin = margin
        return self

    def render(self, max_width: int) -> Rendered:
        """Renders the list; ``max_width`` is accepted but not constraining."""
        del max_width
        return self._apply_margin(Rendered(self._render_lines()))

    def _apply_margin(self, block: Rendered) -> Rendered:
        """Surrounds ``block`` with the outer margin, matching Rust ``pad``."""
        edges = self._margin
        content_width = block.width()
        inner_width = content_width + edges.horizontal()
        lines: list[Line] = []
        for _ in range(edges.top):
            lines.append(blank_line(inner_width))
        for line in block.lines:
            lines.append(_pad_content_line(line, edges, content_width))
        for _ in range(edges.bottom):
            lines.append(blank_line(inner_width))
        return Rendered(lines)

    def _marker_label(self, index: int) -> str:
        """Returns the marker label for the item at ``index``."""
        if self._marker is Marker.BULLET:
            glyph = (
                self._bullet if self._bullet is not None else theme().bullet()
            )
            return f"{glyph} "
        core = _ORDERED_CORE[self._marker](index)
        return f"{core}{self._suffix} "

    def _render_lines(self) -> list[Line]:
        """Renders the list into a flat list of lines, without the margin."""
        lines: list[Line] = []
        for index, item in enumerate(self._items):
            if index > 0:
                for _ in range(self._item_gap):
                    lines.append(Line())
            self._render_item(index, item, lines)
        return lines

    def _render_item(
        self, index: int, item: _ListItem, lines: list[Line]
    ) -> None:
        """Renders one item and its children into ``lines``."""
        label = self._marker_label(index)
        label_width = visible_width(label)
        indent = " " * self._indent
        hang = " " * (self._indent + label_width)
        for row, content_line in enumerate(item.content.lines):
            spans: list[Span] = []
            if row == 0:
                spans.append(Span.raw(indent))
                spans.append(Span.styled(label, self._marker_style))
            else:
                spans.append(Span.raw(hang))
            spans.extend(content_line.spans)
            lines.append(Line(spans))
        self._render_children(item, label_width, lines)

    def _render_children(
        self, item: _ListItem, label_width: int, lines: list[Line]
    ) -> None:
        """Renders a nested sub-list indented under its parent item."""
        if item.children is None:
            return
        hang = self._indent + label_width
        for child_line in item.children._render_lines():
            spans: list[Span] = [Span.raw(" " * hang)]
            spans.extend(child_line.spans)
            lines.append(Line(spans))


def _pad_content_line(line: Line, edges: Edges, content_width: int) -> Line:
    """Adds left/right space columns around one content line."""
    spans: list[Span] = []
    if edges.left > 0:
        spans.append(space_span(edges.left))
    if edges.right > 0:
        padded = pad_line(line, content_width, Align.LEFT)
        spans.extend(padded.spans)
        spans.append(space_span(edges.right))
    else:
        spans.extend(line.spans)
    return Line(spans)


def _to_alpha(index: int, *, upper: bool) -> str:
    """Converts a zero-based index to bijective base-26 letters."""
    value = index + 1
    chars: list[str] = []
    base = ord("A") if upper else ord("a")
    while value > 0:
        rem = (value - 1) % _ALPHA_BASE
        chars.append(chr(base + rem))
        value = (value - 1) // _ALPHA_BASE
    return "".join(reversed(chars))


def _to_roman(value: int, *, upper: bool) -> str:
    """Converts a positive integer to a roman numeral."""
    out: list[str] = []
    for amount, symbol in _NUMERALS:
        while value >= amount:
            out.append(symbol)
            value -= amount
    text = "".join(out)
    return text.upper() if upper else text
