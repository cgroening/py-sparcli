"""
sparcli.core.markup
==================

Parses lightweight inline markup such as ``[bold red]text[/]`` into rich text.

Space-separated specs inside brackets combine attributes and colors; ``on
<color>`` sets a background; ``[/]`` closes the most recent tag; a backtick
span like ```code``` gets a cyan code style; and a backslash escapes the next
character. The parser never fails: a bracket that names no known style or
attribute (such as ``array[0]``) and any malformed bracket are emitted
literally.
"""

from __future__ import annotations

from sparcli.core.color import Color
from sparcli.core.render import Renderable, Rendered
from sparcli.core.style import Attribute, Style
from sparcli.core.text import Line, Span, Text

_BACKGROUND_KEYWORD = "on"

_ATTRIBUTE_TOKENS: dict[str, Attribute] = {
    "bold": Attribute.BOLD,
    "b": Attribute.BOLD,
    "dim": Attribute.DIM,
    "d": Attribute.DIM,
    "italic": Attribute.ITALIC,
    "i": Attribute.ITALIC,
    "underline": Attribute.UNDERLINED,
    "underlined": Attribute.UNDERLINED,
    "u": Attribute.UNDERLINED,
    "strike": Attribute.STRIKETHROUGH,
    "strikethrough": Attribute.STRIKETHROUGH,
    "s": Attribute.STRIKETHROUGH,
}


def parse(markup: str) -> Text:
    """
    Parses markup into a :class:`~sparcli.core.text.Text`.

    Parameters
    ----------
    markup : str
        The markup string.

    Returns
    -------
    Text
        The parsed rich text.

    Examples
    --------
    >>> text = parse("[bold]hi[/]")
    >>> text.lines[0].plain()
    'hi'
    """
    return _Parser(markup).run()


def markup_print(markup: str) -> None:
    """Parses ``markup`` and prints it to stdout."""
    _AsRenderable(parse(markup)).print()


def markup_println(markup: str) -> None:
    """Parses ``markup``, appends a blank line and prints it to stdout."""
    text = parse(markup)
    text.push_line(Line())
    _AsRenderable(text).print()


class _AsRenderable(Renderable):
    """Adapts a parsed :class:`Text` to the :class:`Renderable` interface."""

    __slots__ = ("_text",)

    def __init__(self, text: Text) -> None:
        self._text = text

    def render(self, max_width: int) -> Rendered:
        """Returns the text's lines as a rendered block."""
        return Rendered.from_text(self._text)


class _Parser:
    """A small state machine turning markup into styled lines."""

    __slots__ = ("_chars", "_stack", "_lines", "_spans", "_buffer", "_in_code")

    def __init__(self, markup: str) -> None:
        self._chars = markup
        self._stack: list[Style] = [Style.new()]
        self._lines: list[Line] = []
        self._spans: list[Span] = []
        self._buffer: list[str] = []
        self._in_code = False

    def run(self) -> Text:
        """Parses the input and returns the resulting text."""
        index = 0
        length = len(self._chars)
        while index < length:
            char = self._chars[index]
            if char == "\\":
                index = self._consume_escape(index)
            elif char == "[":
                index = self._consume_tag(index)
            elif char == "`":
                self._toggle_code()
                index += 1
            elif char == "\n":
                self._break_line()
                index += 1
            else:
                self._buffer.append(char)
                index += 1
        self._break_line()
        return Text(self._lines)

    def _consume_escape(self, index: int) -> int:
        """Appends the escaped character literally and returns the next index."""
        if index + 1 < len(self._chars):
            self._buffer.append(self._chars[index + 1])
            return index + 2
        self._buffer.append("\\")
        return index + 1

    def _consume_tag(self, index: int) -> int:
        """Handles a ``[...]`` tag or emits an unrecognized bracket literally."""
        end = self._chars.find("]", index)
        if end == -1:
            self._buffer.append("[")
            return index + 1
        tag = self._chars[index + 1 : end]
        if tag.strip() == "/":
            self._flush_buffer()
            if len(self._stack) > 1:
                self._stack.pop()
            return end + 1
        specs = _parse_specs(tag)
        if specs == Style.new():
            # A closed bracket that names no known style or attribute (e.g.
            # "array[0]") is content, not markup, so emit it literally.
            self._buffer.append(self._chars[index : end + 1])
            return end + 1
        self._flush_buffer()
        self._stack.append(self._current().patch(specs))
        return end + 1

    def _toggle_code(self) -> None:
        """Toggles a cyan code style on or off at the current nesting."""
        self._flush_buffer()
        if self._in_code:
            if len(self._stack) > 1:
                self._stack.pop()
        else:
            code = self._current().patch(Style.new().with_fg(Color.CYAN))
            self._stack.append(code)
        self._in_code = not self._in_code

    def _break_line(self) -> None:
        """Flushes the buffer and starts a new line."""
        self._flush_buffer()
        self._lines.append(Line(self._spans))
        self._spans = []

    def _flush_buffer(self) -> None:
        """Emits the buffered text as a span with the current style."""
        if not self._buffer:
            return
        content = "".join(self._buffer)
        self._spans.append(Span(content=content, style=self._current()))
        self._buffer = []

    def _current(self) -> Style:
        """Returns the style on top of the stack."""
        return self._stack[-1]


def _parse_specs(tag: str) -> Style:
    """Parses a tag's space-separated specs into a style."""
    style = Style.new()
    expect_background = False
    for token in tag.split():
        lowered = token.lower()
        if lowered == _BACKGROUND_KEYWORD:
            expect_background = True
            continue
        if expect_background:
            color = _parse_color(token)
            if color is not None:
                style = style.with_bg(color)
            expect_background = False
            continue
        style = _apply_token(style, lowered, token)
    return style


def _apply_token(style: Style, lowered: str, token: str) -> Style:
    """Applies a single foreground or attribute token to ``style``."""
    attribute = _ATTRIBUTE_TOKENS.get(lowered)
    if attribute is not None:
        return style.add_modifier(attribute)
    color = _parse_color(token)
    return style.with_fg(color) if color is not None else style


def _parse_color(token: str) -> Color | None:
    """Parses a hex or named color token, returning ``None`` if unknown."""
    if token.startswith("#"):
        return Color.from_hex(token)
    return Color.from_name(token)
