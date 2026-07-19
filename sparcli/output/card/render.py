"""
sparcli.output.card.render
==========================

Builds a card's rows and keeps its surface free of gaps.

A :class:`~sparcli.core.render.Rendered` block is a list of styled spans, not a
cell grid, so a background paints only the characters of its own span. Every
row is therefore assembled through :func:`_region_row`, which materializes the
padding columns, the alignment slack and the border glyphs with the region's
background, and rebases the content spans onto it.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sparcli.core.border import TALL, BorderType
from sparcli.core.geometry import Align, Position
from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.terminal import ColorSupport, color_support
from sparcli.core.text import Line, Span
from sparcli.core.theme import theme
from sparcli.core.width import truncate_line, wrap_line
from sparcli.output.card.palette import CardStyles, derive
from sparcli.output.layout import blank_line, pad_line, space_span

if TYPE_CHECKING:
    from sparcli.core.geometry import Edges
    from sparcli.output.card.card import CardOpts, CardParts

# Columns consumed by the two vertical border glyphs.
_BORDER_COLUMNS = 2

# Marker appended to content that had to be truncated.
_ELLIPSIS = "…"


@dataclass(frozen=True, slots=True)
class RenderCaps:
    """
    The terminal capabilities a card renders against.

    Bundling them keeps the render seam at one parameter and makes both
    degradations testable without touching the global theme or environment.

    Attributes
    ----------
    support : ColorSupport
        How much color the terminal supports.
    unicode : bool
        Whether Unicode glyphs may be used.
    """

    support: ColorSupport
    unicode: bool

    @classmethod
    def detect(cls) -> RenderCaps:
        """Reads the capabilities from the environment and the theme."""
        return cls(support=color_support(), unicode=theme().unicode)

    @classmethod
    def truecolor(cls) -> RenderCaps:
        """Returns the capabilities of a fully capable terminal."""
        return cls(support=ColorSupport.TRUECOLOR, unicode=True)


@dataclass(frozen=True, slots=True)
class _Region:
    """The geometry and styling one row of a card needs."""

    width: int
    padding: Edges
    align: Align
    text: Style
    surface: Style
    border: Style
    border_type: BorderType
    wrap: bool

    def area(self) -> int:
        """Returns the width available to text, after horizontal padding."""
        return max(0, self.width - self.padding.horizontal())


@dataclass(frozen=True, slots=True)
class _CardRegions:
    """The three regions of a card plus which optional ones are present."""

    title: _Region
    content: _Region
    footer: _Region
    has_title: bool
    has_footer: bool

    def top(self) -> _Region:
        """Returns the region the top border sits against."""
        return self.title if self.has_title else self.content

    def bottom(self) -> _Region:
        """Returns the region the bottom border sits against."""
        return self.footer if self.has_footer else self.content


def render_card(parts: CardParts, max_width: int, caps: RenderCaps) -> Rendered:
    """
    Renders a card for explicit terminal capabilities.

    :meth:`~sparcli.output.card.card.Card.render` detects the capabilities from
    the environment and the theme; this seam keeps both degradations testable,
    since under pytest standard output is not a terminal and detection would
    always report :attr:`~sparcli.core.terminal.ColorSupport.NONE`.

    Parameters
    ----------
    parts : CardParts
        The card's content, title, footer and options.
    max_width : int
        The width available to the card.
    caps : RenderCaps
        The color and glyph capabilities to render against.

    Returns
    -------
    Rendered
        The finished block of styled lines.
    """
    opts = parts.opts
    border = _effective_border(opts.border, caps)
    outer = max_width if opts.width is None else min(opts.width, max_width)
    columns = _border_columns(border)
    if outer <= columns:
        return Rendered.empty()
    styles = _resolved_styles(opts, caps.support)
    regions = _build_regions(parts, styles, outer - columns, border)
    return _assemble(parts, regions, border)


def _effective_border(border: BorderType, caps: RenderCaps) -> BorderType:
    """
    Resolves the border type actually drawn.

    A tall border is built from block glyphs whose bar only reads against a
    contrasting surface, so it needs both truecolor and Unicode glyphs. Without
    either it degrades to the heavy frame its glyph set already maps to. Other
    border types are returned unchanged, so a card does not diverge from
    :class:`~sparcli.output.panel.Panel` here.
    """
    if not border.is_tall():
        return border
    if not caps.unicode:
        return BorderType.ASCII
    if caps.support is not ColorSupport.TRUECOLOR:
        return BorderType.THICK
    return BorderType.TALL


def _border_columns(border: BorderType) -> int:
    """Returns the columns the vertical border glyphs consume."""
    return 0 if border.is_none() else _BORDER_COLUMNS


def _resolved_styles(opts: CardOpts, support: ColorSupport) -> CardStyles:
    """
    Derives the palette and applies the per-slot overrides on top.

    The surface background is the single source for both the blank padding
    cells and the text cells, so a custom fill reaches the body text as well;
    an explicit content style still wins over it.
    """
    styles = derive(opts.accent, support)
    fill = styles.fill.patch(opts.fill)
    title = styles.title
    footer = styles.footer
    if opts.flat_title:
        title = dataclasses.replace(title, bg=fill.bg)
    if opts.flat_footer:
        footer = dataclasses.replace(footer, bg=fill.bg)
    content = dataclasses.replace(styles.content, bg=fill.bg)
    return CardStyles(
        border=styles.border.patch(opts.border_style),
        title=title.patch(opts.title_style),
        fill=fill,
        content=content.patch(opts.content_style),
        footer=footer.patch(opts.footer_style),
    )


def _build_regions(
    parts: CardParts, styles: CardStyles, surface: int, border: BorderType
) -> _CardRegions:
    """Builds the three regions a card is made of."""
    opts = parts.opts
    title_surface = _surface_of(styles.title)
    footer_surface = _surface_of(styles.footer)
    return _CardRegions(
        title=_Region(
            width=surface,
            padding=opts.title_padding,
            align=opts.title_align,
            text=styles.title,
            surface=title_surface,
            border=_border_over(styles.border, title_surface),
            border_type=border,
            wrap=opts.wrap,
        ),
        content=_Region(
            width=surface,
            padding=opts.padding,
            align=opts.content_align,
            text=styles.content,
            surface=styles.fill,
            border=_border_over(styles.border, styles.fill),
            border_type=border,
            wrap=opts.wrap,
        ),
        footer=_Region(
            width=surface,
            padding=opts.footer_padding,
            align=opts.footer_align,
            text=styles.footer,
            surface=footer_surface,
            border=_border_over(styles.border, footer_surface),
            border_type=border,
            wrap=opts.wrap,
        ),
        has_title=parts.title is not None,
        has_footer=parts.footer is not None,
    )


def _assemble(
    parts: CardParts, regions: _CardRegions, border: BorderType
) -> Rendered:
    """Builds all rows of the card, top to bottom."""
    lines: list[Line] = []
    framed = not border.is_none()
    if framed:
        lines.append(_edge_row(regions.top(), Position.TOP))
    if parts.title is not None:
        _push_block(lines, parts.title.lines, regions.title)
    _push_block(lines, parts.content.lines, regions.content)
    if parts.footer is not None:
        _push_block(lines, parts.footer.lines, regions.footer)
    if framed:
        lines.append(_edge_row(regions.bottom(), Position.BOTTOM))
    return Rendered(lines)


def _push_block(lines: list[Line], source: list[Line], region: _Region) -> None:
    """Appends a region's padding rows, text rows and padding rows."""
    for _ in range(region.padding.top):
        lines.append(_blank_row(region))
    area = region.area()
    if area > 0:
        for line in source:
            lines.extend(
                _region_row(fitted, region) for fitted in _fit(line, region)
            )
    for _ in range(region.padding.bottom):
        lines.append(_blank_row(region))


def _fit(line: Line, region: _Region) -> list[Line]:
    """Fits one line into the region's area by wrapping or truncating."""
    if region.wrap:
        return wrap_line(line, region.area())
    return [truncate_line(line, region.area(), _ELLIPSIS)]


def _region_row(line: Line, region: _Region) -> Line:
    """
    Builds one full-width row of a region.

    Border glyph, padding, aligned text, padding, border glyph - with every
    cell carrying the region's background.
    """
    spans: list[Span] = []
    _push_left_border(spans, region)
    if region.padding.left:
        spans.append(space_span(region.padding.left, region.surface))
    rebased = _rebase(line, region.text)
    padded = pad_line(rebased, region.area(), region.align, region.surface)
    spans.extend(padded.spans)
    if region.padding.right:
        spans.append(space_span(region.padding.right, region.surface))
    _push_right_border(spans, region)
    return Line(spans)


def _blank_row(region: _Region) -> Line:
    """Builds an empty row of the region's surface."""
    spans: list[Span] = []
    _push_left_border(spans, region)
    spans.extend(blank_line(region.width, region.surface).spans)
    _push_right_border(spans, region)
    return Line(spans)


def _edge_row(region: _Region, position: Position) -> Line:
    """Builds the top or bottom border row of a region."""
    if region.border_type.is_tall():
        return _tall_edge_row(region, position)
    chars = region.border_type.chars()
    if position is Position.TOP:
        left, right = chars.top_left, chars.top_right
    else:
        left, right = chars.bottom_left, chars.bottom_right
    content = left + chars.horizontal * region.width + right
    return Line([Span(content=content, style=region.border)])


def _tall_edge_row(region: _Region, position: Position) -> Line:
    """
    Builds a tall border's horizontal row.

    The line runs across the corner cells as well, which is what closes the
    corner, and it carries no surface behind it so the colored area begins at
    the line rather than a row above it.
    """
    glyph = TALL.top if position is Position.TOP else TALL.bottom
    content = glyph * (region.width + _BORDER_COLUMNS)
    style = dataclasses.replace(region.border, bg=None)
    return Line([Span(content=content, style=style)])


def _push_left_border(spans: list[Span], region: _Region) -> None:
    """Appends the left border glyph, unless the card is unframed."""
    if region.border_type.is_none():
        return
    if region.border_type.is_tall():
        spans.append(Span(content=TALL.left, style=region.border))
        return
    glyph = region.border_type.chars().vertical
    spans.append(Span(content=glyph, style=region.border))


def _push_right_border(spans: list[Span], region: _Region) -> None:
    """Appends the right border glyph, unless the card is unframed."""
    if region.border_type.is_none():
        return
    if region.border_type.is_tall():
        style = _swap_colors(region.border)
        spans.append(Span(content=TALL.right, style=style))
        return
    glyph = region.border_type.chars().vertical
    spans.append(Span(content=glyph, style=region.border))


def _rebase(line: Line, base: Style) -> Line:
    """
    Rebases every span of a line onto a base style.

    Without this the content spans keep their own (usually unset) background
    and punch transparent holes through the surface - invisible in the plain
    text, visible in the terminal.
    """
    return Line(
        [
            dataclasses.replace(span, style=base.patch(span.style))
            for span in line.spans
        ]
    )


def _surface_of(style: Style) -> Style:
    """Reduces a text style to the background it sits on."""
    return Style() if style.bg is None else Style(bg=style.bg)


def _border_over(border: Style, surface: Style) -> Style:
    """
    Returns the border style carrying the surface's background.

    Without it the glyphs leave a transparent seam along the card's edges.
    """
    if surface.bg is None:
        return border
    return dataclasses.replace(border, bg=surface.bg)


def _swap_colors(style: Style) -> Style:
    """
    Returns a style with foreground and background swapped.

    A tall border's right-hand glyph inks the left three quarters of its cell;
    swapping turns the remaining quarter into the bar, which is the only way to
    get a right-aligned quarter block - Unicode does not define one. Returns
    the style unchanged when either color is unset, since the swap needs both.
    """
    if style.fg is None or style.bg is None:
        return style
    return dataclasses.replace(style, fg=style.bg, bg=style.fg)
