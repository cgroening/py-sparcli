"""
sparcli.output.panel
===================

Defines :class:`Panel`, a bordered box framing rich content.

A panel wraps text or any rendered block in a border with optional title,
subtitle, padding and fill. It supports both a keyword constructor and fluent
builder methods, so ``Panel("hi", title="Note")`` and
``Panel("hi").title("Note")`` are equivalent.
"""

from __future__ import annotations

from sparcli.core.border import BorderType
from sparcli.core.geometry import Align, Edges, Position, Title
from sparcli.core.render import Renderable, Rendered
from sparcli.core.style import Style
from sparcli.core.text import IntoText, Text, into_text
from sparcli.core.theme import theme
from sparcli.output.box import BoxOpts, draw_box

IntoTitle = IntoText | Title


def into_title(value: IntoTitle) -> Title:
    """Coerces a string, rich text or title into a :class:`Title`."""
    if isinstance(value, Title):
        return value
    return Title.new(value)


class Panel(Renderable):
    """A bordered box framing rich content."""

    __slots__ = ("_content", "_opts")

    def __init__(
        self,
        content: IntoText = "",
        *,
        border: BorderType | None = None,
        border_style: Style | None = None,
        fill: Style | None = None,
        padding: Edges | None = None,
        title: IntoTitle | None = None,
        subtitle: IntoTitle | None = None,
        width: int | None = None,
        content_align: Align = Align.LEFT,
    ) -> None:
        self._content = _content_to_rendered(content)
        self._opts = BoxOpts(
            border=border if border is not None else theme().border,
            border_style=border_style or Style.new(),
            fill=fill or Style.new(),
            padding=padding if padding is not None else Edges.symmetric(0, 1),
            title=into_title(title) if title is not None else None,
            subtitle=_as_subtitle(subtitle),
            width=width,
            content_align=content_align,
        )

    @classmethod
    def from_rendered(cls, rendered: Rendered) -> Panel:
        """Returns a panel framing an already rendered block."""
        panel = cls()
        panel._content = rendered
        return panel

    def border(self, border: BorderType) -> Panel:
        """Sets the border type and returns the panel."""
        self._opts.border = border
        return self

    def border_style(self, style: Style) -> Panel:
        """Sets the border style and returns the panel."""
        self._opts.border_style = style
        return self

    def fill(self, style: Style) -> Panel:
        """Sets the interior fill style and returns the panel."""
        self._opts.fill = style
        return self

    def padding(self, edges: Edges) -> Panel:
        """Sets the interior padding and returns the panel."""
        self._opts.padding = edges
        return self

    def title(self, title: IntoTitle) -> Panel:
        """Sets the title and returns the panel."""
        self._opts.title = into_title(title)
        return self

    def subtitle(self, subtitle: IntoTitle) -> Panel:
        """Sets the bottom subtitle and returns the panel."""
        self._opts.subtitle = _as_subtitle(subtitle)
        return self

    def width(self, width: int) -> Panel:
        """Fixes the outer width and returns the panel."""
        self._opts.width = width
        return self

    def content_align(self, align: Align) -> Panel:
        """Sets the content alignment and returns the panel."""
        self._opts.content_align = align
        return self

    def render(self, max_width: int) -> Rendered:
        """Renders the framed panel into at most ``max_width`` columns."""
        return draw_box(self._content, self._opts, max_width)


def _content_to_rendered(content: IntoText) -> Rendered:
    """Converts widget content into a rendered block."""
    text: Text = into_text(content)
    return Rendered.from_text(text)


def _as_subtitle(value: IntoTitle | None) -> Title | None:
    """Coerces a subtitle value, forcing it to sit on the bottom edge."""
    if value is None:
        return None
    return into_title(value).with_position(Position.BOTTOM)
