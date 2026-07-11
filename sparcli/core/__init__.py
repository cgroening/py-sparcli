"""
sparcli.core
============

The foundation layer: styling, text, rendering, geometry, borders, theming,
width math, terminal capabilities and inline markup.

Nothing in this package depends on the widget layers; ``output`` and ``input``
build on top of it.
"""

from sparcli.core.border import BorderChars, BorderType
from sparcli.core.color import Color, ColorName
from sparcli.core.geometry import Align, Edges, Position, Title, VAlign
from sparcli.core.markup import markup_print, markup_println, parse
from sparcli.core.render import (
    Renderable,
    Rendered,
    SupportsWrite,
    write_line,
    write_rendered,
)
from sparcli.core.style import Attribute, Modifier, Style
from sparcli.core.terminal import (
    ColorSupport,
    color_support,
    is_input_tty,
    is_output_tty,
    term_height,
    term_width,
    terminal_size,
)
from sparcli.core.text import (
    IntoLine,
    IntoSpan,
    IntoText,
    Line,
    Span,
    Text,
    into_line,
    into_span,
    into_text,
)
from sparcli.core.theme import DEFAULT_ACCENT, Theme, set_theme, theme
from sparcli.core.width import strip_ansi, truncate, visible_width, wrap

__all__ = [
    "DEFAULT_ACCENT",
    "Align",
    "Attribute",
    "BorderChars",
    "BorderType",
    "Color",
    "ColorName",
    "ColorSupport",
    "Edges",
    "IntoLine",
    "IntoSpan",
    "IntoText",
    "Line",
    "Modifier",
    "Position",
    "Rendered",
    "Renderable",
    "Span",
    "Style",
    "SupportsWrite",
    "Text",
    "Theme",
    "Title",
    "VAlign",
    "color_support",
    "into_line",
    "into_span",
    "into_text",
    "is_input_tty",
    "is_output_tty",
    "markup_print",
    "markup_println",
    "parse",
    "set_theme",
    "strip_ansi",
    "term_height",
    "term_width",
    "terminal_size",
    "theme",
    "truncate",
    "visible_width",
    "wrap",
    "write_line",
    "write_rendered",
]
