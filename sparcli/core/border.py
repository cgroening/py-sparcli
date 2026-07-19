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


@dataclass(frozen=True, slots=True)
class TallChars:
    """
    The block glyphs of a :attr:`BorderType.TALL` border.

    The sides ink a quarter of their cell's width, the top and bottom an
    eighth of their cell's height. Since a terminal cell is roughly twice as
    tall as it is wide, both come out the same number of pixels - a fraction
    equal on both axes would not.

    The horizontal glyphs sit on the *inner* side of their row (``▁`` at the
    top of the frame, ``▔`` at the bottom) and run across the corner cells
    too. That is what closes the corner: the line touches the side bar of the
    adjoining row instead of starting a cell away from it.

    :class:`BorderChars` cannot express any of this - it offers one
    ``horizontal`` and one ``vertical`` for all four edges, and no way to say
    that a glyph is painted with foreground and background swapped.

    Attributes
    ----------
    left : str
        The left edge, inking the left quarter of its cell.
    right : str
        The right edge, painted with swapped colors so its right quarter inks.
    top : str
        The top edge, inking the bottom eighth of its cell.
    bottom : str
        The bottom edge, inking the top eighth of its cell.
    """

    left: str
    right: str
    top: str
    bottom: str


TALL = TallChars(
    left="▎",  # LEFT ONE QUARTER BLOCK
    right="▊",  # LEFT THREE QUARTERS BLOCK, painted with swapped colors
    top="▁",  # LOWER ONE EIGHTH BLOCK
    bottom="▔",  # UPPER ONE EIGHTH BLOCK
)


class BorderType(enum.Enum):
    """A border look; :meth:`chars` returns its glyph set."""

    NONE = enum.auto()
    ASCII = enum.auto()
    SINGLE = enum.auto()
    DOUBLE = enum.auto()
    ROUNDED = enum.auto()
    THICK = enum.auto()
    TALL = enum.auto()
    """
    A thin block frame around a filled surface.

    Only :class:`~sparcli.output.card.Card` draws this natively: the bars need
    a filled surface to read against, all four edges use a different glyph,
    and the right-hand one is painted with foreground and background swapped.
    Every other widget receives the :attr:`BorderType.THICK` glyphs from
    :meth:`chars` instead.
    """

    def chars(self) -> BorderChars:
        """Returns the concrete glyph set for this border type."""
        return _BORDER_CHARS[self]

    def is_none(self) -> bool:
        """Returns whether this border type draws nothing."""
        return self is BorderType.NONE

    def is_tall(self) -> bool:
        """Returns whether this border type is drawn from block glyphs."""
        return self is BorderType.TALL


_BORDER_CHARS: dict[BorderType, BorderChars] = {
    BorderType.NONE: _SPACE,
    BorderType.ASCII: _ASCII,
    BorderType.SINGLE: _SINGLE,
    BorderType.DOUBLE: _DOUBLE,
    BorderType.ROUNDED: _ROUNDED,
    BorderType.THICK: _THICK,
    # Tall's half blocks cannot be expressed as a BorderChars set, so widgets
    # that do not draw it natively fall back to a heavy line frame.
    BorderType.TALL: _THICK,
}
