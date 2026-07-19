"""
sparcli.core.render
===================

Defines the render model: :class:`Rendered`, :class:`Renderable` and the ANSI
writer.

Every widget lays itself out into a :class:`Rendered` (a list of styled lines
of known width) before anything reaches the terminal. Colors and attributes are
turned into escape codes only here, in :func:`write_rendered`, downgraded to the
detected :class:`~sparcli.core.terminal.ColorSupport`. Plain, unstyled text is
written without a single escape, which keeps piped and ``NO_COLOR`` output
clean.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sparcli.core.style import Attribute, Style
from sparcli.core.terminal import ColorSupport, color_support, output_width
from sparcli.core.text import IntoLine, Line, Span, Text, into_line

if TYPE_CHECKING:
    from sparcli.core.color import ResolvedColor

_ESC = "\x1b"
_RESET = f"{_ESC}[0m"
_OSC8_START = f"{_ESC}]8;;"
_OSC8_END = f"{_ESC}\\"

# Control characters (C0, DEL and C1) minus tab. Emitting these verbatim lets
# untrusted content inject escape sequences or corrupt the layout, so they are
# stripped just before text reaches the terminal.
_TAB_BYTE = 0x09
_CONTROL_TABLE: dict[int, None] = {
    code: None
    for code in (*range(0x20), 0x7F, *range(0x80, 0xA0))
    if code != _TAB_BYTE
}

# SGR parameter for each attribute flag.
_ATTRIBUTE_SGR: list[tuple[Attribute, str]] = [
    (Attribute.BOLD, "1"),
    (Attribute.DIM, "2"),
    (Attribute.ITALIC, "3"),
    (Attribute.UNDERLINED, "4"),
    (Attribute.STRIKETHROUGH, "9"),
]


@runtime_checkable
class SupportsWrite(Protocol):
    """A minimal text sink: anything with a ``write(str)`` method."""

    def write(self, data: str, /) -> int | None:
        """Writes ``data`` to the sink."""
        ...


class Renderable(ABC):
    """
    The interface every printable widget implements.

    Subclasses provide :meth:`render`; :meth:`print` and :meth:`print_to` are
    derived from it.
    """

    __slots__ = ()

    @abstractmethod
    def render(self, max_width: int) -> Rendered:
        """
        Lays the widget out into at most ``max_width`` columns.

        Parameters
        ----------
        max_width : int
            The maximum width available, in columns.

        Returns
        -------
        Rendered
            The laid-out block of styled lines.
        """
        raise NotImplementedError

    def print(self) -> None:
        """
        Renders for the current output width and writes it to stdout.

        At a terminal that is its width. Piped or redirected there is no width
        to fit, so nothing is truncated and the block keeps its natural width -
        clipping to an invented default would drop data from the pipe silently.
        """
        rendered = self.render(output_width())
        write_rendered(sys.stdout, rendered, color_support())
        sys.stdout.flush()

    def print_to(self, writer: SupportsWrite) -> None:
        """
        Renders for the current output width and writes to ``writer``.

        Width is resolved exactly as in :meth:`print`.

        Parameters
        ----------
        writer : SupportsWrite
            Any object with a ``write(str)`` method (a file, ``io.StringIO``).
        """
        rendered = self.render(output_width())
        write_rendered(writer, rendered, color_support())


@dataclass(slots=True)
class Rendered(Renderable):
    """
    A laid-out block of styled lines of known width.

    :class:`Rendered` is both the output of :meth:`Renderable.render` and the
    composable unit used to stack and place widgets next to each other. It is
    itself a :class:`Renderable`, so a pre-built block can be printed directly.
    """

    lines: list[Line] = field(default_factory=list)

    @classmethod
    def empty(cls) -> Rendered:
        """Returns an empty rendered block."""
        return cls([])

    @classmethod
    def from_text(cls, text: Text) -> Rendered:
        """Returns a rendered block from a :class:`Text`'s lines."""
        return cls(list(text.lines))

    def render(self, max_width: int) -> Rendered:
        """
        Returns a copy of this block, ignoring ``max_width``.

        Parameters
        ----------
        max_width : int
            Accepted to satisfy :class:`Renderable`; a block is already laid
            out, so it is not consulted.

        Returns
        -------
        Rendered
            A copy of this block.
        """
        return Rendered(list(self.lines))

    def push(self, line: IntoLine) -> None:
        """Appends a line to the block."""
        self.lines.append(into_line(line))

    def width(self) -> int:
        """Returns the width of the widest line in columns."""
        return max((line.width() for line in self.lines), default=0)

    def height(self) -> int:
        """Returns the number of lines."""
        return len(self.lines)

    def plain(self) -> str:
        r"""Returns the block's text without styling, lines joined by ``\n``."""
        return "\n".join(line.plain() for line in self.lines)


def write_rendered(
    writer: SupportsWrite, rendered: Rendered, support: ColorSupport
) -> None:
    """
    Writes a :class:`Rendered` to ``writer`` as ANSI, one line per row.

    Parameters
    ----------
    writer : SupportsWrite
        The text sink to write to.
    rendered : Rendered
        The block to write.
    support : ColorSupport
        The color depth to emit.
    """
    for line in rendered.lines:
        write_line(writer, line, support)
        writer.write("\n")


def write_line(
    writer: SupportsWrite, line: Line, support: ColorSupport
) -> None:
    """Writes a single styled line to ``writer`` without a trailing newline."""
    for span in line.spans:
        writer.write(_render_span(span, support))


def _render_span(span: Span, support: ColorSupport) -> str:
    """Returns the escaped string for a single span at a support level."""
    content = _sanitize(span.content)
    if support is ColorSupport.NONE:
        return content
    codes = _sgr_codes(span.style, support)
    content = _wrap_link(content, span.link)
    if not codes:
        return content
    prefix = f"{_ESC}[{";".join(codes)}m"
    return f"{prefix}{content}{_RESET}"


def _sanitize(text: str) -> str:
    """Strips control characters (except tab) that would corrupt output."""
    return text.translate(_CONTROL_TABLE)


def _sgr_codes(style: Style, support: ColorSupport) -> list[str]:
    """Returns the SGR parameters for a style, empty when nothing is styled."""
    codes: list[str] = []
    if style.fg is not None:
        resolved = style.fg.resolve(support)
        if resolved is not None:
            codes.append(_color_sgr(resolved, background=False))
    if style.bg is not None:
        resolved = style.bg.resolve(support)
        if resolved is not None:
            codes.append(_color_sgr(resolved, background=True))
    for attribute, code in _ATTRIBUTE_SGR:
        if style.attrs.contains(attribute):
            codes.append(code)
    return codes


def _color_sgr(resolved: ResolvedColor, *, background: bool) -> str:
    """Builds the SGR fragment for a resolved color."""
    lead = "48" if background else "38"
    match resolved:
        case ("reset",):
            return "49" if background else "39"
        case ("ansi16", index):
            return _ansi16_sgr(index, background=background)
        case ("rgb", red, green, blue):
            return f"{lead};2;{red};{green};{blue}"
        case ("indexed", palette_index):
            return f"{lead};5;{palette_index}"


# Palette indices at or above this use the bright SGR range.
_ANSI_BRIGHT_OFFSET = 8


def _ansi16_sgr(index: int, *, background: bool) -> str:
    """Builds the SGR fragment for a 16-color palette index."""
    if index < _ANSI_BRIGHT_OFFSET:
        base = 40 if background else 30
        return str(base + index)
    base = 100 if background else 90
    return str(base + index - _ANSI_BRIGHT_OFFSET)


def _wrap_link(content: str, link: str | None) -> str:
    """
    Wraps ``content`` in an OSC-8 hyperlink when a link is present.

    The URL is scrubbed of control characters so a crafted link cannot
    terminate the OSC-8 sequence early and inject its own escapes.
    """
    if link is None:
        return content
    safe = _sanitize(link)
    return f"{_OSC8_START}{safe}{_OSC8_END}{content}{_OSC8_START}{_OSC8_END}"
