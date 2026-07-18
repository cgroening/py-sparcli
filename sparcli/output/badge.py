"""
sparcli.output.badge
====================

Defines :class:`Badge`, a small inline token such as ``[TAG]`` or ``(v1.0)``.

A badge wraps a short text in a pair of caps and paints it in a single style,
defaulting to the accent color in bold. It renders to one line and also exposes
:meth:`Badge.span`, so it can be embedded inline in other lines. Both a keyword
constructor and fluent builder methods are provided, matching :class:`Panel`.
"""

from __future__ import annotations

from sparcli.core.render import Renderable, Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.core.theme import theme

_DEFAULT_LEFT_CAP = "["
_DEFAULT_RIGHT_CAP = "]"


class Badge(Renderable):
    """A small inline token with configurable caps and style."""

    __slots__ = ("_left_cap", "_pad", "_right_cap", "_style", "_text")

    def __init__(
        self,
        text: str,
        *,
        left_cap: str = _DEFAULT_LEFT_CAP,
        right_cap: str = _DEFAULT_RIGHT_CAP,
        style: Style | None = None,
        pad: int = 0,
    ) -> None:
        self._text = text
        self._left_cap = left_cap
        self._right_cap = right_cap
        self._style = style if style is not None else _default_style()
        self._pad = pad

    def caps(self, left: str, right: str) -> Badge:
        """Sets both caps at once and returns the badge."""
        self._left_cap = left
        self._right_cap = right
        return self

    def style(self, style: Style) -> Badge:
        """Sets the badge text style and returns the badge."""
        self._style = style
        return self

    def pad(self, pad: int) -> Badge:
        """Sets the number of spaces inside the caps and returns the badge."""
        self._pad = pad
        return self

    def span(self) -> Span:
        """
        Returns the badge as a single styled :class:`Span`.

        Returns
        -------
        Span
            The caps and padded text painted in the badge style.
        """
        spaces = " " * max(0, self._pad)
        content = (
            f"{self._left_cap}{spaces}{self._text}{spaces}{self._right_cap}"
        )
        return Span.styled(content, self._style)

    def render(self, max_width: int) -> Rendered:
        """
        Renders the badge as a single line, ignoring ``max_width``.

        Parameters
        ----------
        max_width : int
            The number of columns available for the block.

        Returns
        -------
        Rendered
            The laid-out block of styled lines.
        """
        return Rendered([Line([self.span()])])


def _default_style() -> Style:
    """Returns the default accent-bold badge style from the theme."""
    return Style.new().with_fg(theme().accent).bold()
