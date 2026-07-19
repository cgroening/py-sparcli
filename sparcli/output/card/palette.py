"""
sparcli.output.card.palette
===========================

Derives a card's five styles from a single accent color.

The accent keeps its hue throughout; only saturation and lightness change.
That is what makes one color enough: the title stays saturated, the body text
and both surfaces become desaturated shades of the same tone.
"""

from __future__ import annotations

from dataclasses import dataclass

from sparcli.core.color import Color
from sparcli.core.hsl import Hsl
from sparcli.core.style import Style
from sparcli.core.terminal import ColorSupport

# Saturation and lightness of the title text.
_TITLE_FG_SATURATION = 0.85
_TITLE_FG_LIGHTNESS = 0.78

# Saturation and lightness of the title bar surface.
_TITLE_BG_SATURATION = 0.35
_TITLE_BG_LIGHTNESS = 0.22

# Saturation and lightness of the content surface.
_CONTENT_BG_SATURATION = 0.18
_CONTENT_BG_LIGHTNESS = 0.13

# Saturation and lightness of the body text.
_CONTENT_FG_SATURATION = 0.15
_CONTENT_FG_LIGHTNESS = 0.75

# Below this saturation a color carries no meaningful hue. Re-saturating it
# would pick up the fallback hue of zero and turn a gray accent into a red one,
# so such accents stay neutral.
_ACHROMATIC_SATURATION = 0.05


@dataclass(frozen=True, slots=True)
class CardStyles:
    """
    The five styles a card derives from one accent color.

    Attributes
    ----------
    border : Style
        Style of the border glyphs.
    title : Style
        Style of the title row's text, including its own background.
    fill : Style
        Background of the content surface, used for padding and blank rows.
    content : Style
        Style of the body text.
    footer : Style
        Style of the footer row's text, including its own background.
    """

    border: Style
    title: Style
    fill: Style
    content: Style
    footer: Style


def derive(accent: Color, support: ColorSupport) -> CardStyles:
    """
    Derives the card palette from an accent color.

    Below :attr:`~sparcli.core.terminal.ColorSupport.TRUECOLOR` the surfaces
    are dropped: the downgrade quantizes each channel, so both derived
    backgrounds collapse onto the same named color and the title bar would
    become indistinguishable from the content area - the card's only
    separator. An accent without an RGB value (:data:`Color.RESET`) takes the
    same path, since nothing can be derived from it.

    Parameters
    ----------
    accent : Color
        The color every other tone is built from.
    support : ColorSupport
        The color depth the output stream can display.

    Returns
    -------
    CardStyles
        The five styles, with backgrounds only under truecolor.
    """
    rgb = accent.to_rgb()
    if rgb is None or support is not ColorSupport.TRUECOLOR:
        return _flat_styles(accent)
    base = Hsl.from_rgb(rgb)
    title_bg = _shade(base, _TITLE_BG_SATURATION, _TITLE_BG_LIGHTNESS)
    content_bg = _shade(base, _CONTENT_BG_SATURATION, _CONTENT_BG_LIGHTNESS)
    title_fg = _shade(base, _TITLE_FG_SATURATION, _TITLE_FG_LIGHTNESS)
    content_fg = _shade(base, _CONTENT_FG_SATURATION, _CONTENT_FG_LIGHTNESS)
    title = Style(fg=title_fg, bg=title_bg)
    return CardStyles(
        border=Style(fg=accent, bg=content_bg),
        title=title,
        fill=Style(bg=content_bg),
        content=Style(fg=content_fg, bg=content_bg),
        footer=title,
    )


def _shade(base: Hsl, saturation: float, lightness: float) -> Color:
    """Re-shades a color to the given saturation and lightness, keeping hue."""
    if base.saturation < _ACHROMATIC_SATURATION:
        saturation = 0.0
    shaded = Hsl(
        hue=base.hue, saturation=saturation, lightness=lightness
    ).to_rgb()
    return Color.rgb(*shaded)


def _flat_styles(accent: Color) -> CardStyles:
    """Returns the background-free palette used when surfaces cannot show."""
    accented = Style(fg=accent)
    bold = accented.bold()
    return CardStyles(
        border=accented,
        title=bold,
        fill=Style.new(),
        content=Style.new(),
        footer=bold,
    )
