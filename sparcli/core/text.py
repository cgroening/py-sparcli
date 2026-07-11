"""
sparcli.core.text
=================

Defines the rich-text primitives :class:`Span`, :class:`Line` and
:class:`Text`.

A :class:`Span` is a run of text with a single style and an optional hyperlink.
A :class:`Line` is a sequence of spans; a :class:`Text` is a sequence of lines.
Together they mirror ratatui's text vocabulary. The ``into_*`` helpers coerce
plain strings into these types, so widget APIs can accept either.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from sparcli.core.style import Style
from sparcli.core.width import visible_width


@dataclass(frozen=True, slots=True)
class Span:
    """
    A styled run of text with an optional hyperlink target.

    Attributes
    ----------
    content : str
        The text of the span.
    style : Style
        The style applied to the text.
    link : str | None
        An OSC-8 hyperlink target, or ``None``.
    """

    content: str = ""
    style: Style = field(default_factory=Style)
    link: str | None = None

    @classmethod
    def raw(cls, content: str) -> Span:
        """Returns an unstyled span with no link."""
        return cls(content=content)

    @classmethod
    def styled(cls, content: str, style: Style) -> Span:
        """Returns a span with the given style."""
        return cls(content=content, style=style)

    def with_link(self, url: str) -> Span:
        """Returns a copy of the span carrying an OSC-8 hyperlink."""
        return replace(self, link=url)

    def width(self) -> int:
        """Returns the display width of the span in columns."""
        return visible_width(self.content)


@dataclass(slots=True)
class Line:
    """A single line of text made of one or more :class:`Span` objects."""

    spans: list[Span] = field(default_factory=list)

    @classmethod
    def raw(cls, content: str) -> Line:
        """Returns a line holding a single unstyled span."""
        return cls([Span.raw(content)])

    @classmethod
    def styled(cls, content: str, style: Style) -> Line:
        """Returns a line holding a single styled span."""
        return cls([Span.styled(content, style)])

    def width(self) -> int:
        """Returns the total display width of the line in columns."""
        return sum(span.width() for span in self.spans)

    def plain(self) -> str:
        """Returns the line's text without any styling."""
        return "".join(span.content for span in self.spans)


@dataclass(slots=True)
class Text:
    """A block of styled text made of zero or more :class:`Line` objects."""

    lines: list[Line] = field(default_factory=list)

    @classmethod
    def raw(cls, content: str) -> Text:
        """Returns text with ``content`` split into lines on newlines."""
        return cls([Line.raw(part) for part in content.split("\n")])

    @classmethod
    def styled(cls, content: str, style: Style) -> Text:
        """Returns styled text with ``content`` split on newlines."""
        return cls([Line.styled(part, style) for part in content.split("\n")])

    def push_line(self, line: IntoLine) -> None:
        """Appends a line to the text."""
        self.lines.append(into_line(line))

    def width(self) -> int:
        """Returns the width of the widest line in columns."""
        return max((line.width() for line in self.lines), default=0)

    def height(self) -> int:
        """Returns the number of lines."""
        return len(self.lines)


IntoSpan = str | Span
IntoLine = str | Span | Line
IntoText = str | Span | Line | Text


def into_span(value: IntoSpan) -> Span:
    """Coerces a string or span into a :class:`Span`."""
    if isinstance(value, Span):
        return value
    return Span.raw(value)


def into_line(value: IntoLine) -> Line:
    """Coerces a string, span or line into a :class:`Line`."""
    if isinstance(value, Line):
        return value
    if isinstance(value, Span):
        return Line([value])
    return Line.raw(value)


def into_text(value: IntoText) -> Text:
    """Coerces a string, span, line or text into a :class:`Text`."""
    if isinstance(value, Text):
        return value
    if isinstance(value, Line):
        return Text([value])
    if isinstance(value, Span):
        return Text([Line([value])])
    return Text.raw(value)
