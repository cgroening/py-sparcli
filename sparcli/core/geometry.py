"""
sparcli.core.geometry
=====================

Defines layout primitives: alignment enums, box spacing and titles.

:class:`Align` and :class:`VAlign` control horizontal and vertical placement,
:class:`Position` selects which edge a title sits on, :class:`Edges` models
box-model spacing (padding/margins), and :class:`Title` is a positioned,
aligned label used by panels, rules and tables.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from sparcli.core.text import IntoText, Line, Span, Text, into_text

if TYPE_CHECKING:
    from sparcli.core.style import Style


class Align(enum.Enum):
    """Horizontal alignment within an available width."""

    LEFT = enum.auto()
    CENTER = enum.auto()
    RIGHT = enum.auto()


class VAlign(enum.Enum):
    """Vertical alignment within an available height."""

    TOP = enum.auto()
    MIDDLE = enum.auto()
    BOTTOM = enum.auto()


class Position(enum.Enum):
    """Which edge a title is placed on."""

    TOP = enum.auto()
    BOTTOM = enum.auto()


@dataclass(frozen=True, slots=True)
class Edges:
    """
    Box-model spacing for the four edges.

    Attributes
    ----------
    top, right, bottom, left : int
        The spacing on each edge, in cells.
    """

    top: int = 0
    right: int = 0
    bottom: int = 0
    left: int = 0

    @classmethod
    def all(cls, value: int) -> Edges:
        """Returns edges with the same spacing on every side."""
        return cls(top=value, right=value, bottom=value, left=value)

    @classmethod
    def symmetric(cls, vertical: int, horizontal: int) -> Edges:
        """Returns edges with matching vertical and horizontal spacing."""
        return cls(
            top=vertical,
            right=horizontal,
            bottom=vertical,
            left=horizontal,
        )

    def horizontal(self) -> int:
        """Returns the combined left and right spacing."""
        return self.left + self.right

    def vertical(self) -> int:
        """Returns the combined top and bottom spacing."""
        return self.top + self.bottom


@dataclass(slots=True)
class Title:
    """
    A positioned, aligned label rendered inside a border or rule.

    Attributes
    ----------
    content : Text
        The title text.
    align : Align
        Horizontal alignment along the edge.
    position : Position
        Which edge the title sits on.
    pad : int
        Horizontal padding around the title text, in cells.
    """

    content: Text = field(default_factory=Text)
    align: Align = Align.LEFT
    position: Position = Position.TOP
    pad: int = 1

    @classmethod
    def new(cls, content: IntoText) -> Title:
        """Returns a top-left title with default padding."""
        return cls(content=into_text(content))

    def with_align(self, align: Align) -> Title:
        """Returns a copy with the alignment set."""
        return replace(self, align=align)

    def with_position(self, position: Position) -> Title:
        """Returns a copy with the edge position set."""
        return replace(self, position=position)

    def with_pad(self, pad: int) -> Title:
        """Returns a copy with the horizontal padding set."""
        return replace(self, pad=pad)

    def with_style(self, style: Style) -> Title:
        """Returns a copy with ``style`` patched onto every span."""
        styled = Text(
            [
                Line(
                    [
                        Span(
                            content=span.content,
                            style=span.style.patch(style),
                            link=span.link,
                        )
                        for span in line.spans
                    ]
                )
                for line in self.content.lines
            ]
        )
        return replace(self, content=styled)
