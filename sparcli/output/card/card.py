"""
sparcli.output.card.card
========================

Defines the :class:`Card` widget: a filled surface with title and footer rows.

Where :class:`~sparcli.output.panel.Panel` draws a frame and embeds the title
in the top border, a card is a surface: the background carries the shape, an
outer border is optional, and the title sits on a row of its own. All of its
colors are derived from a single accent, so one call is enough.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sparcli.core.border import BorderType
from sparcli.core.geometry import Align, Edges
from sparcli.core.render import Renderable, Rendered
from sparcli.core.style import Style
from sparcli.core.text import IntoText, Text, into_text
from sparcli.core.theme import theme

if TYPE_CHECKING:
    from sparcli.core.color import Color


@dataclass(slots=True)
class CardOpts:
    """Layout and styling options of a :class:`Card`."""

    accent: Color = field(default_factory=lambda: theme().accent)
    border: BorderType = BorderType.NONE
    width: int | None = None
    padding: Edges = field(default_factory=lambda: Edges.symmetric(1, 1))
    title_padding: Edges = field(default_factory=lambda: Edges.symmetric(0, 1))
    footer_padding: Edges = field(default_factory=lambda: Edges.symmetric(0, 1))
    title_align: Align = Align.LEFT
    content_align: Align = Align.LEFT
    footer_align: Align = Align.LEFT
    wrap: bool = True
    flat_title: bool = False
    flat_footer: bool = False
    title_style: Style = field(default_factory=Style)
    content_style: Style = field(default_factory=Style)
    fill: Style = field(default_factory=Style)
    border_style: Style = field(default_factory=Style)
    footer_style: Style = field(default_factory=Style)


@dataclass(frozen=True, slots=True)
class CardParts:
    """
    Everything the render pipeline needs from a card.

    Bundling the four pieces keeps the render entry point at three parameters
    and spares the render module from reaching into private attributes.
    """

    content: Rendered
    title: Text | None
    footer: Text | None
    opts: CardOpts


class Card(Renderable):
    """
    A filled card: a colored surface with an optional title and footer row.

    Every color comes from one accent (by default
    :attr:`~sparcli.core.theme.Theme.accent`): the title keeps it saturated,
    the body text and both surfaces are desaturated, darker shades of the same
    hue. The individual style setters patch the derived values rather than
    replacing them, so ``title_style(Style.new().bold())`` keeps the derived
    colors and only adds the attribute.

    A card fills the whole width it is rendered into unless :meth:`width`
    narrows it, and it carries no border unless :meth:`border` adds one - note
    that this ignores :attr:`~sparcli.core.theme.Theme.border`, unlike every
    framed widget. Below truecolor support the surfaces are dropped and the
    card renders as accented text, because the derived shades would collapse
    onto one ANSI-16 color.

    Examples
    --------
    >>> from sparcli import Card
    >>> out = Card("All systems nominal.").title("Status").render(40)
    >>> "Status" in out.plain()
    True
    >>> "All systems nominal." in out.plain()
    True
    """

    __slots__ = ("_content", "_footer", "_opts", "_title")

    def __init__(
        self,
        content: IntoText = "",
        *,
        accent: Color | None = None,
        border: BorderType | None = None,
        width: int | None = None,
        padding: Edges | None = None,
        title_padding: Edges | None = None,
        footer_padding: Edges | None = None,
        title: IntoText | None = None,
        footer: IntoText | None = None,
        title_align: Align = Align.LEFT,
        content_align: Align = Align.LEFT,
        footer_align: Align = Align.LEFT,
        wrap: bool = True,
    ) -> None:
        """
        Builds a card around text content.

        Parameters
        ----------
        content : IntoText
            The body content.
        accent : Color | None
            The color every other tone is derived from; defaults to the theme
            accent.
        border : BorderType | None
            An outer border; defaults to none, unlike every framed widget.
        width : int | None
            A fixed outer width; defaults to the full render width.
        padding : Edges | None
            Padding around the body content.
        title_padding : Edges | None
            Padding around the title row.
        footer_padding : Edges | None
            Padding around the footer row.
        title : IntoText | None
            The title row content.
        footer : IntoText | None
            The footer row content.
        title_align, content_align, footer_align : Align
            Horizontal alignment of each region.
        wrap : bool
            Whether overlong lines wrap instead of being truncated.
        """
        self._content = Rendered.from_text(into_text(content))
        self._title = into_text(title) if title is not None else None
        self._footer = into_text(footer) if footer is not None else None
        self._opts = CardOpts(
            accent=accent if accent is not None else theme().accent,
            border=border if border is not None else BorderType.NONE,
            width=width,
            padding=padding if padding is not None else Edges.symmetric(1, 1),
            title_padding=(
                title_padding
                if title_padding is not None
                else Edges.symmetric(0, 1)
            ),
            footer_padding=(
                footer_padding
                if footer_padding is not None
                else Edges.symmetric(0, 1)
            ),
            title_align=title_align,
            content_align=content_align,
            footer_align=footer_align,
            wrap=wrap,
        )

    @classmethod
    def from_rendered(cls, rendered: Rendered) -> Card:
        """
        Builds a card around an already rendered block.

        Parameters
        ----------
        rendered : Rendered
            The pre-rendered body content.

        Returns
        -------
        Card
            A card wrapping that block.
        """
        card = cls()
        card._content = rendered
        return card

    def title(self, title: IntoText) -> Card:
        """Sets the title row content and returns the card."""
        self._title = into_text(title)
        return self

    def footer(self, footer: IntoText) -> Card:
        """Sets the footer row content and returns the card."""
        self._footer = into_text(footer)
        return self

    def accent(self, accent: Color) -> Card:
        """
        Sets the accent color all other tones are derived from.

        Works with any :class:`~sparcli.core.color.Color`: named colors and
        palette indices resolve through
        :meth:`~sparcli.core.color.Color.to_rgb`. An achromatic accent yields a
        neutral gray card rather than picking up an arbitrary hue.

        Parameters
        ----------
        accent : Color
            The color to derive from.

        Returns
        -------
        Card
            The card, for chaining.

        Examples
        --------
        >>> from sparcli import Card, Color
        >>> Card("Done.").accent(Color.GREEN).render(20).height()
        3
        """
        self._opts.accent = accent
        return self

    def width(self, width: int) -> Card:
        """Sets a fixed outer width in columns and returns the card."""
        self._opts.width = width
        return self

    def border(self, border: BorderType) -> Card:
        """
        Adds an outer border around the surface.

        :attr:`~sparcli.core.border.BorderType.TALL` is the one border a card
        draws natively: a thin block frame whose strokes come out equally thick
        on both axes and whose corners close. It needs both truecolor and
        Unicode glyphs to read, and degrades to
        :attr:`~sparcli.core.border.BorderType.THICK` (or to
        :attr:`~sparcli.core.border.BorderType.ASCII` when the theme disables
        Unicode) otherwise.

        Parameters
        ----------
        border : BorderType
            The border to draw.

        Returns
        -------
        Card
            The card, for chaining.

        Examples
        --------
        >>> from sparcli import BorderType, Card
        >>> Card("Deployed.").border(BorderType.TALL).render(30).height()
        5
        """
        self._opts.border = border
        return self

    def padding(self, padding: Edges) -> Card:
        """
        Sets the padding around the body content and returns the card.

        The vertical padding is what separates the body from the title row;
        with ``Edges.symmetric(0, n)`` the two sit on adjacent rows, separated
        only by the background step.
        """
        self._opts.padding = padding
        return self

    def title_padding(self, padding: Edges) -> Card:
        """Sets the padding around the title row and returns the card."""
        self._opts.title_padding = padding
        return self

    def footer_padding(self, padding: Edges) -> Card:
        """Sets the padding around the footer row and returns the card."""
        self._opts.footer_padding = padding
        return self

    def title_align(self, align: Align) -> Card:
        """Sets the horizontal title alignment and returns the card."""
        self._opts.title_align = align
        return self

    def content_align(self, align: Align) -> Card:
        """Sets the horizontal body alignment and returns the card."""
        self._opts.content_align = align
        return self

    def footer_align(self, align: Align) -> Card:
        """Sets the horizontal footer alignment and returns the card."""
        self._opts.footer_align = align
        return self

    def flat_title(self) -> Card:
        """
        Lets the title row share the content background.

        The title then reads only through its saturated text color, which suits
        cards whose surface should stay one uninterrupted block.

        Returns
        -------
        Card
            The card, for chaining.

        Examples
        --------
        >>> from sparcli import Card
        >>> out = Card("body").title("Heading").flat_title().render(30)
        >>> "Heading" in out.plain()
        True
        """
        self._opts.flat_title = True
        return self

    def flat_footer(self) -> Card:
        """Lets the footer row share the content background."""
        self._opts.flat_footer = True
        return self

    def wrap(self, wrap: bool) -> Card:
        """Enables or disables automatic wrapping and returns the card."""
        self._opts.wrap = wrap
        return self

    def title_style(self, style: Style) -> Card:
        """Patches the derived title style and returns the card."""
        self._opts.title_style = style
        return self

    def content_style(self, style: Style) -> Card:
        """Patches the derived body text style and returns the card."""
        self._opts.content_style = style
        return self

    def fill(self, style: Style) -> Card:
        """Patches the derived surface background and returns the card."""
        self._opts.fill = style
        return self

    def border_style(self, style: Style) -> Card:
        """Patches the derived border style and returns the card."""
        self._opts.border_style = style
        return self

    def footer_style(self, style: Style) -> Card:
        """Patches the derived footer style and returns the card."""
        self._opts.footer_style = style
        return self

    def render(self, max_width: int) -> Rendered:
        """
        Renders the card into at most ``max_width`` columns.

        Parameters
        ----------
        max_width : int
            The width available to the card.

        Returns
        -------
        Rendered
            The finished block of styled lines.
        """
        # Deferred because the render module needs CardOpts and CardParts from
        # here, so a module-level import would close an import cycle.
        from sparcli.output.card.render import RenderCaps, render_card

        parts = CardParts(
            content=self._content,
            title=self._title,
            footer=self._footer,
            opts=self._opts,
        )
        return render_card(parts, max_width, RenderCaps.detect())
