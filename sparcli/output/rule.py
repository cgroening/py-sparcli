"""
sparcli.output.rule
===================

Defines :class:`Rule`, a horizontal divider with an optional embedded title.

A rule fills its width with the border's horizontal glyph, painted in the
secondary style. When given a title, the label is embedded in the line with a
one-space pad on each side; a left- or right-aligned title keeps a single
connecting glyph on the outer edge, and a title too wide for the line replaces
it entirely. Both a keyword constructor and fluent builders are provided.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sparcli.core.geometry import Align, Edges
from sparcli.core.render import Renderable, Rendered
from sparcli.core.text import IntoText, Line, Span, Text, into_text
from sparcli.core.theme import theme
from sparcli.output.compose import pad

if TYPE_CHECKING:
    from sparcli.core.border import BorderType
    from sparcli.core.style import Style

_DEFAULT_PAD = 1
_CONNECTOR = 1


class Rule(Renderable):
    """A horizontal divider line, optionally labelled with a title."""

    __slots__ = (
        "_align",
        "_border",
        "_margin",
        "_pad",
        "_style",
        "_title",
        "_width",
    )

    def __init__(
        self,
        title: IntoText | None = None,
        *,
        border: BorderType | None = None,
        style: Style | None = None,
        align: Align = Align.CENTER,
        width: int | None = None,
        margin: Edges | None = None,
    ) -> None:
        active = theme()
        self._title = into_text(title) if title is not None else None
        self._border = border if border is not None else active.border
        self._style = style if style is not None else active.secondary
        self._align = align
        self._width = width
        self._margin = margin if margin is not None else Edges()
        self._pad = _DEFAULT_PAD

    @classmethod
    def with_title(cls, title: IntoText) -> Rule:
        """Returns a rule with an embedded title."""
        return cls(title)

    def border(self, border: BorderType) -> Rule:
        """Sets the line glyph style and returns the rule."""
        self._border = border
        return self

    def style(self, style: Style) -> Rule:
        """Sets the line glyph paint style and returns the rule."""
        self._style = style
        return self

    def align(self, align: Align) -> Rule:
        """Sets the title alignment and returns the rule."""
        self._align = align
        return self

    def width(self, width: int) -> Rule:
        """Sets a fixed width in columns and returns the rule."""
        self._width = width
        return self

    def margin(self, margin: Edges) -> Rule:
        """Sets the outer margin and returns the rule."""
        self._margin = margin
        return self

    def render(self, max_width: int) -> Rendered:
        """
        Renders the rule into at most ``max_width`` columns.

        Parameters
        ----------
        max_width : int
            The number of columns available for the block.

        Returns
        -------
        Rendered
            The laid-out block of styled lines.
        """
        total = self._width if self._width is not None else max_width
        inner = max(0, total - self._margin.horizontal())
        glyph = self._border.chars().horizontal
        if self._title is None:
            line = _fill_line(glyph, inner, self._style)
        else:
            line = self._titled_line(self._title, glyph, inner)
        return pad(Rendered([line]), self._margin)

    def _titled_line(self, title: Text, glyph: str, width: int) -> Line:
        """Builds a rule line with an aligned, embedded title."""
        title_line = title.lines[0] if title.lines else Line()
        title_w = title_line.width() + 2 * self._pad
        if title_w >= width:
            return title_line
        remaining = width - title_w
        left, right = _split_runs(self._align, remaining)
        pad_span = Span.raw(" " * self._pad)
        spans = [_glyph_span(glyph, left, self._style), pad_span]
        spans.extend(title_line.spans)
        spans.append(pad_span)
        spans.append(_glyph_span(glyph, right, self._style))
        return Line(spans)


def _split_runs(align: Align, remaining: int) -> tuple[int, int]:
    """Splits the leftover glyph run around the title per its alignment."""
    if align is Align.LEFT:
        return (min(_CONNECTOR, remaining), max(0, remaining - _CONNECTOR))
    if align is Align.RIGHT:
        return (max(0, remaining - _CONNECTOR), min(_CONNECTOR, remaining))
    left = remaining // 2
    return (left, remaining - left)


def _fill_line(glyph: str, width: int, style: Style) -> Line:
    """Builds a line of ``width`` repeated glyphs."""
    return Line([_glyph_span(glyph, width, style)])


def _glyph_span(glyph: str, count: int, style: Style) -> Span:
    """Builds a span of ``count`` repeated glyphs."""
    return Span.styled(glyph * max(0, count), style)
