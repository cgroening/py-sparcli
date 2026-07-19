"""
sparcli.core.color
==================

Defines the :class:`Color` type and its downgrade to lower color depths.

Colors are authored abstractly (named ANSI colors, 24-bit RGB or 256-color
indices) and only turned into concrete escape codes at render time via
:meth:`Color.resolve`, which downgrades to the available
:class:`~sparcli.core.terminal.ColorSupport`. The named-color set mirrors the
Rust original, including the quirk that ``GRAY`` is standard ANSI 7 and
``WHITE`` is bright ANSI 15.
"""

from __future__ import annotations

import enum
from typing import ClassVar, Literal

from sparcli.core.terminal import ColorSupport

# Downgrade thresholds for mapping an RGB channel onto the 16-color palette.
_CHANNEL_ON = 0x60
_CHANNEL_BRIGHT = 0xC0

# 256-color index boundaries used when collapsing to the 16-color palette.
_GRAYSCALE_LIGHT = 244
_GRAYSCALE_DARK = 232

# Resolved-color shapes handed to the renderer, tagged by their first element.
ResetColor = tuple[Literal["reset"]]
Ansi16Color = tuple[Literal["ansi16"], int]
RgbColor = tuple[Literal["rgb"], int, int, int]
IndexedColor = tuple[Literal["indexed"], int]
ResolvedColor = ResetColor | Ansi16Color | RgbColor | IndexedColor


class ColorName(enum.Enum):
    """The named ANSI colors, including reset and the eight bright variants."""

    RESET = enum.auto()
    BLACK = enum.auto()
    RED = enum.auto()
    GREEN = enum.auto()
    YELLOW = enum.auto()
    BLUE = enum.auto()
    MAGENTA = enum.auto()
    CYAN = enum.auto()
    GRAY = enum.auto()
    DARK_GRAY = enum.auto()
    LIGHT_RED = enum.auto()
    LIGHT_GREEN = enum.auto()
    LIGHT_YELLOW = enum.auto()
    LIGHT_BLUE = enum.auto()
    LIGHT_MAGENTA = enum.auto()
    LIGHT_CYAN = enum.auto()
    WHITE = enum.auto()


# Each named color's index in the standard 16-color palette (0..15).
_ANSI16_INDEX: dict[ColorName, int] = {
    ColorName.BLACK: 0,
    ColorName.RED: 1,
    ColorName.GREEN: 2,
    ColorName.YELLOW: 3,
    ColorName.BLUE: 4,
    ColorName.MAGENTA: 5,
    ColorName.CYAN: 6,
    ColorName.GRAY: 7,
    ColorName.DARK_GRAY: 8,
    ColorName.LIGHT_RED: 9,
    ColorName.LIGHT_GREEN: 10,
    ColorName.LIGHT_YELLOW: 11,
    ColorName.LIGHT_BLUE: 12,
    ColorName.LIGHT_MAGENTA: 13,
    ColorName.LIGHT_CYAN: 14,
    ColorName.WHITE: 15,
}

# Accepted spellings for :meth:`Color.from_name`, including common aliases.
_NAME_ALIASES: dict[str, ColorName] = {
    "reset": ColorName.RESET,
    "default": ColorName.RESET,
    "black": ColorName.BLACK,
    "red": ColorName.RED,
    "green": ColorName.GREEN,
    "yellow": ColorName.YELLOW,
    "blue": ColorName.BLUE,
    "magenta": ColorName.MAGENTA,
    "purple": ColorName.MAGENTA,
    "cyan": ColorName.CYAN,
    "gray": ColorName.GRAY,
    "grey": ColorName.GRAY,
    "white": ColorName.GRAY,
    "darkgray": ColorName.DARK_GRAY,
    "darkgrey": ColorName.DARK_GRAY,
    "lightred": ColorName.LIGHT_RED,
    "lightgreen": ColorName.LIGHT_GREEN,
    "lightyellow": ColorName.LIGHT_YELLOW,
    "lightblue": ColorName.LIGHT_BLUE,
    "lightmagenta": ColorName.LIGHT_MAGENTA,
    "lightcyan": ColorName.LIGHT_CYAN,
    "brightwhite": ColorName.WHITE,
}

_HEX_DIGITS = 6

# Standard xterm RGB values of the sixteen named colors, by palette index.
_ANSI16_RGB: tuple[tuple[int, int, int], ...] = (
    (0x00, 0x00, 0x00),  # 0  black
    (0x80, 0x00, 0x00),  # 1  red
    (0x00, 0x80, 0x00),  # 2  green
    (0x80, 0x80, 0x00),  # 3  yellow
    (0x00, 0x00, 0x80),  # 4  blue
    (0x80, 0x00, 0x80),  # 5  magenta
    (0x00, 0x80, 0x80),  # 6  cyan
    (0xC0, 0xC0, 0xC0),  # 7  gray
    (0x80, 0x80, 0x80),  # 8  dark gray
    (0xFF, 0x00, 0x00),  # 9  light red
    (0x00, 0xFF, 0x00),  # 10 light green
    (0xFF, 0xFF, 0x00),  # 11 light yellow
    (0x00, 0x00, 0xFF),  # 12 light blue
    (0xFF, 0x00, 0xFF),  # 13 light magenta
    (0x00, 0xFF, 0xFF),  # 14 light cyan
    (0xFF, 0xFF, 0xFF),  # 15 white
)

# The 6x6x6 color cube occupying palette indices 16..231.
_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)
_CUBE_START = 16
_CUBE_PLANE = 36
_CUBE_ROW = 6

# The grayscale ramp occupying palette indices 232..255.
_GRAY_BASE = 8
_GRAY_STEP = 10


class Color:
    """
    A terminal color: a named ANSI color, an RGB triple or a 256-color index.

    Construct named colors via the class constants (``Color.RED``), true color
    via :meth:`rgb`, and palette colors via :meth:`indexed`. Instances are
    immutable and compare by value.
    """

    RESET: ClassVar[Color]
    BLACK: ClassVar[Color]
    RED: ClassVar[Color]
    GREEN: ClassVar[Color]
    YELLOW: ClassVar[Color]
    BLUE: ClassVar[Color]
    MAGENTA: ClassVar[Color]
    CYAN: ClassVar[Color]
    GRAY: ClassVar[Color]
    DARK_GRAY: ClassVar[Color]
    LIGHT_RED: ClassVar[Color]
    LIGHT_GREEN: ClassVar[Color]
    LIGHT_YELLOW: ClassVar[Color]
    LIGHT_BLUE: ClassVar[Color]
    LIGHT_MAGENTA: ClassVar[Color]
    LIGHT_CYAN: ClassVar[Color]
    WHITE: ClassVar[Color]

    __slots__ = ("_index", "_name", "_rgb")

    def __init__(
        self,
        *,
        name: ColorName | None = None,
        rgb: tuple[int, int, int] | None = None,
        index: int | None = None,
    ) -> None:
        self._name = name
        self._rgb = rgb
        self._index = index

    @classmethod
    def named(cls, name: ColorName) -> Color:
        """Returns the color for a :class:`ColorName` member."""
        return cls(name=name)

    @classmethod
    def rgb(cls, red: int, green: int, blue: int) -> Color:
        """
        Returns a 24-bit true color.

        Parameters
        ----------
        red, green, blue : int
            Channel values, each clamped to the ``0..255`` range.

        Returns
        -------
        Color
            The RGB color.
        """
        return cls(
            rgb=(_clamp_byte(red), _clamp_byte(green), _clamp_byte(blue))
        )

    @classmethod
    def indexed(cls, index: int) -> Color:
        """Returns a 256-color palette color for ``index`` (clamped 0..255)."""
        return cls(index=_clamp_byte(index))

    @classmethod
    def from_name(cls, text: str) -> Color | None:
        """
        Parses a color name (case-insensitive), returning ``None`` if unknown.

        Parameters
        ----------
        text : str
            A color name such as ``"red"`` or an alias such as ``"purple"``.

        Returns
        -------
        Color | None
            The matching color, or ``None`` when the name is not recognized.
        """
        name = _NAME_ALIASES.get(text.strip().lower())
        return cls(name=name) if name is not None else None

    @classmethod
    def from_hex(cls, text: str) -> Color | None:
        """
        Parses ``#rrggbb`` or ``rrggbb`` into an RGB color.

        Parameters
        ----------
        text : str
            A six-digit hex color, optionally prefixed with ``#``.

        Returns
        -------
        Color | None
            The RGB color, or ``None`` when the string is malformed.
        """
        digits = text.strip().removeprefix("#")
        if len(digits) != _HEX_DIGITS:
            return None
        try:
            value = int(digits, 16)
        except ValueError:
            return None
        return cls.rgb(value >> 16 & 0xFF, value >> 8 & 0xFF, value & 0xFF)

    def to_rgb(self) -> tuple[int, int, int] | None:
        """
        Returns the 24-bit value of this color, if it has one.

        Named colors and palette indices resolve through the standard xterm
        palette: slots 0-15 from a fixed table, 16-231 from the 6x6x6 color
        cube, 232-255 from the grayscale ramp.

        Returns
        -------
        tuple[int, int, int] | None
            The red, green and blue channels, or ``None`` for
            :data:`Color.RESET`, which adopts the terminal's default color and
            therefore has no fixed value.

        Examples
        --------
        >>> from sparcli.core.color import Color
        >>> Color.rgb(1, 2, 3).to_rgb()
        (1, 2, 3)
        >>> Color.LIGHT_RED.to_rgb()
        (255, 0, 0)
        >>> Color.indexed(196).to_rgb()
        (255, 0, 0)
        >>> Color.RESET.to_rgb() is None
        True
        """
        if self._rgb is not None:
            return self._rgb
        if self._index is not None:
            return _indexed_to_rgb(self._index)
        if self._name is not None and self._name is not ColorName.RESET:
            return _ANSI16_RGB[_ANSI16_INDEX[self._name]]
        return None

    def resolve(self, support: ColorSupport) -> ResolvedColor | None:
        """
        Resolves the color for a given support level, downgrading if needed.

        Parameters
        ----------
        support : ColorSupport
            The color depth the output stream can display.

        Returns
        -------
        ResolvedColor | None
            A tagged tuple the renderer turns into an escape code, or ``None``
            when no color should be emitted (``ColorSupport.NONE``).
        """
        if support is ColorSupport.NONE:
            return None
        if self._name is ColorName.RESET:
            return ("reset",)
        if self._name is not None:
            return ("ansi16", _ANSI16_INDEX[self._name])
        if self._rgb is not None:
            if support is ColorSupport.TRUECOLOR:
                return ("rgb", *self._rgb)
            return ("ansi16", _nearest_ansi16(*self._rgb))
        if self._index is not None:
            if support is ColorSupport.TRUECOLOR:
                return ("indexed", self._index)
            return ("ansi16", _indexed_to_ansi16(self._index))
        return None

    def __eq__(self, other: object) -> bool:
        """Returns whether both colors name the same value."""
        if not isinstance(other, Color):
            return NotImplemented
        return (
            self._name == other._name
            and self._rgb == other._rgb
            and self._index == other._index
        )

    def __hash__(self) -> int:
        """Returns a hash consistent with :meth:`__eq__`."""
        return hash((self._name, self._rgb, self._index))

    def __repr__(self) -> str:
        """Returns the constructor call that rebuilds this color."""
        if self._name is not None:
            return f"Color.{self._name.name}"
        if self._rgb is not None:
            return f"Color.rgb{self._rgb}"
        return f"Color.indexed({self._index})"


def _clamp_byte(value: int) -> int:
    """Clamps an integer into the ``0..255`` byte range."""
    return max(0, min(255, value))


def _nearest_ansi16(red: int, green: int, blue: int) -> int:
    """Maps an RGB triple onto the nearest 16-color palette index."""
    base = 0
    if red >= _CHANNEL_ON:
        base |= 1
    if green >= _CHANNEL_ON:
        base |= 2
    if blue >= _CHANNEL_ON:
        base |= 4
    bright = max(red, green, blue) >= _CHANNEL_BRIGHT
    return base + 8 if bright else base


# Size of the base ANSI palette; indices below this pass through unchanged.
_ANSI16_SIZE = 16


def _indexed_to_ansi16(index: int) -> int:
    """Collapses a 256-color index onto the 16-color palette."""
    if index < _ANSI16_SIZE:
        return index
    if index >= _GRAYSCALE_LIGHT:
        return 15
    if index >= _GRAYSCALE_DARK:
        return 8
    return 7


def _indexed_to_rgb(index: int) -> tuple[int, int, int]:
    """Maps a 256-color index onto its RGB value."""
    if index < _CUBE_START:
        return _ANSI16_RGB[index]
    if index >= _GRAYSCALE_DARK:
        level = _GRAY_BASE + (index - _GRAYSCALE_DARK) * _GRAY_STEP
        return (level, level, level)
    return _cube_to_rgb(index - _CUBE_START)


def _cube_to_rgb(offset: int) -> tuple[int, int, int]:
    """Maps an offset into the 6x6x6 color cube onto its RGB value."""
    return (
        _CUBE_LEVELS[offset // _CUBE_PLANE],
        _CUBE_LEVELS[(offset // _CUBE_ROW) % _CUBE_ROW],
        _CUBE_LEVELS[offset % _CUBE_ROW],
    )


def _install_named_colors() -> None:
    """Attaches a class constant for every named color after class creation."""
    for name in ColorName:
        setattr(Color, name.name, Color(name=name))


_install_named_colors()
