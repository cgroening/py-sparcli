"""
sparcli.core.hsl
================

Converts between RGB triples and the HSL color space.

HSL separates a color's identity (hue) from its intensity (saturation) and its
brightness (lightness). That is what lets a widget re-shade one accent color
into a whole palette without changing its character, as
:mod:`sparcli.output.card.palette` does.

This module is internal: it is not re-exported from :mod:`sparcli.core`.
"""

from __future__ import annotations

from dataclasses import dataclass

# Degrees covered by one of the six hue sectors, and by the full circle.
_DEGREES_PER_SECTOR = 60.0
_FULL_TURN = 360.0

# Largest value of an 8-bit color channel.
_CHANNEL_MAX = 255.0


@dataclass(frozen=True, slots=True)
class Hsl:
    """
    A color in HSL space.

    Attributes
    ----------
    hue : float
        The hue in degrees, in ``0.0..360.0``.
    saturation : float
        The saturation, from gray (``0.0``) to fully saturated (``1.0``).
    lightness : float
        The lightness, from black (``0.0``) over the pure hue (``0.5``) to
        white (``1.0``).
    """

    hue: float = 0.0
    saturation: float = 0.0
    lightness: float = 0.0

    @classmethod
    def from_rgb(cls, rgb: tuple[int, int, int]) -> Hsl:
        """
        Converts an RGB triple to HSL.

        An achromatic input (all channels equal) yields a hue of zero. Callers
        that re-saturate a color must treat that hue as meaningless rather than
        as a measurement.

        Parameters
        ----------
        rgb : tuple[int, int, int]
            The red, green and blue channels, each in ``0..255``.

        Returns
        -------
        Hsl
            The same color in HSL space.
        """
        red, green, blue = (channel / _CHANNEL_MAX for channel in rgb)
        high = max(red, green, blue)
        low = min(red, green, blue)
        lightness = (high + low) / 2.0
        delta = high - low
        if delta == 0.0:
            return cls(hue=0.0, saturation=0.0, lightness=lightness)
        saturation = delta / (1.0 - abs(2.0 * lightness - 1.0))
        hue = _hue_of(red, green, blue, high, delta)
        return cls(hue=hue, saturation=saturation, lightness=lightness)

    def to_rgb(self) -> tuple[int, int, int]:
        """
        Converts back to RGB, clamping components that lie out of range.

        Returns
        -------
        tuple[int, int, int]
            The red, green and blue channels, each in ``0..255``.
        """
        saturation = _clamp_unit(self.saturation)
        lightness = _clamp_unit(self.lightness)
        chroma = (1.0 - abs(2.0 * lightness - 1.0)) * saturation
        sector = (self.hue % _FULL_TURN) / _DEGREES_PER_SECTOR
        second = chroma * (1.0 - abs(sector % 2.0 - 1.0))
        base = lightness - chroma / 2.0
        red, green, blue = _sector_channels(sector, chroma, second)
        return (
            _to_channel(red + base),
            _to_channel(green + base),
            _to_channel(blue + base),
        )


def _hue_of(
    red: float, green: float, blue: float, high: float, delta: float
) -> float:
    """Returns the hue in degrees from the channels and their spread."""
    if high == red:
        offset, span = 0.0, green - blue
    elif high == green:
        offset, span = 2.0, blue - red
    else:
        offset, span = 4.0, red - green
    return ((span / delta + offset) * _DEGREES_PER_SECTOR) % _FULL_TURN


def _sector_channels(
    sector: float, chroma: float, second: float
) -> tuple[float, float, float]:
    """Distributes the chroma over the channels by hue sector."""
    match int(sector):
        case 0:
            return (chroma, second, 0.0)
        case 1:
            return (second, chroma, 0.0)
        case 2:
            return (0.0, chroma, second)
        case 3:
            return (0.0, second, chroma)
        case 4:
            return (second, 0.0, chroma)
        case _:
            return (chroma, 0.0, second)


def _clamp_unit(value: float) -> float:
    """Clamps a value into the ``0.0..1.0`` range."""
    return max(0.0, min(1.0, value))


def _to_channel(value: float) -> int:
    """Scales a normalized component back to an 8-bit channel value."""
    return round(_clamp_unit(value) * _CHANNEL_MAX)
