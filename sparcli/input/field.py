"""
sparcli.input.field
===================

Defines the shared line-rendering helpers for text-entry prompts.

Every text prompt renders a labelled field with a block cursor, a final value
line without a cursor, a dim placeholder line, or an error line. These helpers
draw those four shapes consistently so the prompts share one look.
"""

from __future__ import annotations

from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.core.theme import Theme


def field_line(
    prompt: str, display: str, cursor: int, style: Style, theme: Theme
) -> Line:
    """
    Renders a labelled single-line field with a block cursor.

    Parameters
    ----------
    prompt : str
        The field label; omitted when empty.
    display : str
        The already-prepared text (e.g. masked for passwords).
    cursor : int
        The character index the block cursor sits on.
    style : Style
        The style for the entered text.
    theme : Theme
        The active theme, for the title and cursor styles.

    Returns
    -------
    Line
        The rendered field line.
    """
    spans: list[Span] = []
    if prompt:
        spans.append(Span.styled(f"{prompt} ", theme.title))
    _push_with_cursor(spans, display, cursor, style, theme.cursor)
    return Line(spans)


def value_line(prompt: str, display: str, style: Style, theme: Theme) -> Line:
    """Renders a labelled value without any cursor (the final frame)."""
    spans: list[Span] = []
    if prompt:
        spans.append(Span.styled(f"{prompt} ", theme.title))
    if display:
        spans.append(Span.styled(display, style))
    return Line(spans)


def placeholder_line(prompt: str, placeholder: str, theme: Theme) -> Line:
    """Renders dim placeholder text with the cursor at the start."""
    spans: list[Span] = []
    if prompt:
        spans.append(Span.styled(f"{prompt} ", theme.title))
    spans.append(Span.styled(" ", theme.cursor))
    spans.append(Span.styled(placeholder, theme.secondary))
    return Line(spans)


def error_line(message: str, theme: Theme) -> Line:
    """Renders an error message line in the theme's error style."""
    return Line.styled(f"  {message}", theme.error)


def _push_with_cursor(
    spans: list[Span],
    display: str,
    cursor: int,
    style: Style,
    cursor_style: Style,
) -> None:
    """Splits ``display`` at the cursor and pushes spans with a block cursor."""
    chars = list(display)
    before = "".join(chars[:cursor])
    if before:
        spans.append(Span.styled(before, style))
    at = chars[cursor] if cursor < len(chars) else " "
    spans.append(Span.styled(at, cursor_style))
    if cursor + 1 < len(chars):
        spans.append(Span.styled("".join(chars[cursor + 1 :]), style))
