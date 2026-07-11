"""
sparcli.core.border
===================

Defines border styles and their glyph sets.

:class:`BorderType` selects a look (rounded, single, double, thick, ASCII or
none); :meth:`BorderType.chars` returns the concrete :class:`BorderChars` glyph
set used to draw boxes, tables and rules. The ASCII set is the fallback for
terminals without Unicode line-drawing support.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BorderChars:
    """
    The glyphs used to draw a border.

    Attributes
    ----------
    top_left, top_right, bottom_left, bottom_right : str
        Corner glyphs.
    horizontal, vertical : str
        Edge glyphs.
    cross : str
        The four-way junction glyph.
    tee_down, tee_up, tee_right, tee_left : str
        T-junction glyphs used by tables.
    """

    top_left: str
    top_right: str
    bottom_left: str
    bottom_right: str
    horizontal: str
    vertical: str
    cross: str
    tee_down: str
    tee_up: str
    tee_right: str
    tee_left: str


_SPACE = BorderChars(
    top_left=" ",
    top_right=" ",
    bottom_left=" ",
    bottom_right=" ",
    horizontal=" ",
    vertical=" ",
    cross=" ",
    tee_down=" ",
    tee_up=" ",
    tee_right=" ",
    tee_left=" ",
)

_ASCII = BorderChars(
    top_left="+",
    top_right="+",
    bottom_left="+",
    bottom_right="+",
    horizontal="-",
    vertical="|",
    cross="+",
    tee_down="+",
    tee_up="+",
    tee_right="+",
    tee_left="+",
)

_SINGLE = BorderChars(
    top_left="┌",
    top_right="┐",
    bottom_left="└",
    bottom_right="┘",
    horizontal="─",
    vertical="│",
    cross="┼",
    tee_down="┬",
    tee_up="┴",
    tee_right="├",
    tee_left="┤",
)

_DOUBLE = BorderChars(
    top_left="╔",
    top_right="╗",
    bottom_left="╚",
    bottom_right="╝",
    horizontal="═",
    vertical="║",
    cross="╬",
    tee_down="╦",
    tee_up="╩",
    tee_right="╠",
    tee_left="╣",
)

_ROUNDED = BorderChars(
    top_left="╭",
    top_right="╮",
    bottom_left="╰",
    bottom_right="╯",
    horizontal="─",
    vertical="│",
    cross="┼",
    tee_down="┬",
    tee_up="┴",
    tee_right="├",
    tee_left="┤",
)

_THICK = BorderChars(
    top_left="┏",
    top_right="┓",
    bottom_left="┗",
    bottom_right="┛",
    horizontal="━",
    vertical="┃",
    cross="╋",
    tee_down="┳",
    tee_up="┻",
    tee_right="┣",
    tee_left="┫",
)


class BorderType(enum.Enum):
    """A border look; :meth:`chars` returns its glyph set."""

    NONE = enum.auto()
    ASCII = enum.auto()
    SINGLE = enum.auto()
    DOUBLE = enum.auto()
    ROUNDED = enum.auto()
    THICK = enum.auto()

    def chars(self) -> BorderChars:
        """Returns the concrete glyph set for this border type."""
        return _BORDER_CHARS[self]

    def is_none(self) -> bool:
        """Returns whether this border type draws nothing."""
        return self is BorderType.NONE


_BORDER_CHARS: dict[BorderType, BorderChars] = {
    BorderType.NONE: _SPACE,
    BorderType.ASCII: _ASCII,
    BorderType.SINGLE: _SINGLE,
    BorderType.DOUBLE: _DOUBLE,
    BorderType.ROUNDED: _ROUNDED,
    BorderType.THICK: _THICK,
}
