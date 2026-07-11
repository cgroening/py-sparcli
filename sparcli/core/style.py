"""
sparcli.core.style
==================

Defines text styling: attributes and the :class:`Style` value type.

A :class:`Style` bundles an optional foreground and background color with a set
of :class:`Attribute` flags (bold, dim, italic, ...). Styles are immutable;
builder methods return a new style, and :meth:`Style.patch` layers one style on
top of another.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace

from sparcli.core.color import Color


class Attribute(enum.IntFlag):
    """Bitflags for text attributes; combine with ``|``."""

    NONE = 0
    BOLD = enum.auto()
    DIM = enum.auto()
    ITALIC = enum.auto()
    UNDERLINED = enum.auto()
    STRIKETHROUGH = enum.auto()

    def contains(self, other: Attribute) -> bool:
        """Returns whether every flag in ``other`` is set in ``self``."""
        return (self & other) == other

    def is_empty(self) -> bool:
        """Returns whether no attribute flag is set."""
        return self == Attribute.NONE


# ratatui-familiar alias for the attribute flags.
Modifier = Attribute


@dataclass(frozen=True, slots=True)
class Style:
    """
    An immutable text style: foreground, background and attribute flags.

    Attributes
    ----------
    fg : Color | None
        Foreground color, or ``None`` to inherit.
    bg : Color | None
        Background color, or ``None`` to inherit.
    attrs : Attribute
        The set of active attribute flags.
    """

    fg: Color | None = None
    bg: Color | None = None
    attrs: Attribute = Attribute.NONE

    @classmethod
    def new(cls) -> Style:
        """Returns an empty style with no color and no attributes."""
        return cls()

    def with_fg(self, color: Color) -> Style:
        """Returns a copy with the foreground color set."""
        return replace(self, fg=color)

    def with_bg(self, color: Color) -> Style:
        """Returns a copy with the background color set."""
        return replace(self, bg=color)

    def add_modifier(self, attr: Attribute) -> Style:
        """Returns a copy with ``attr`` added to the attribute flags."""
        return replace(self, attrs=self.attrs | attr)

    def bold(self) -> Style:
        """Returns a copy with the bold attribute set."""
        return self.add_modifier(Attribute.BOLD)

    def dim(self) -> Style:
        """Returns a copy with the dim attribute set."""
        return self.add_modifier(Attribute.DIM)

    def italic(self) -> Style:
        """Returns a copy with the italic attribute set."""
        return self.add_modifier(Attribute.ITALIC)

    def underlined(self) -> Style:
        """Returns a copy with the underlined attribute set."""
        return self.add_modifier(Attribute.UNDERLINED)

    def strikethrough(self) -> Style:
        """Returns a copy with the strikethrough attribute set."""
        return self.add_modifier(Attribute.STRIKETHROUGH)

    def patch(self, other: Style) -> Style:
        """
        Layers ``other`` on top of this style.

        Parameters
        ----------
        other : Style
            The overriding style. Its set colors win; attribute flags from both
            styles are combined.

        Returns
        -------
        Style
            The merged style.
        """
        return Style(
            fg=other.fg if other.fg is not None else self.fg,
            bg=other.bg if other.bg is not None else self.bg,
            attrs=self.attrs | other.attrs,
        )

    @classmethod
    def from_color(cls, color: Color) -> Style:
        """Returns a style whose foreground is ``color``."""
        return cls(fg=color)
