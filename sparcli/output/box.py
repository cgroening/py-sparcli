"""
sparcli.output.box
=================

Shared box-drawing routine used by :class:`~sparcli.output.panel.Panel` and
:class:`~sparcli.output.alert.Alert`.

:func:`draw_box` frames a rendered block with a border, padding and an optional
fill, embedding a title in the top edge and a subtitle in the bottom edge. A
``BorderType.NONE`` box degrades to padding only. The title-embedding rules
match the Rust original: a left-aligned title keeps a single connecting glyph.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sparcli.core.border import BorderType
from sparcli.core.geometry import Align, Edges, Title
from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.core.width import truncate, visible_width
from sparcli.output.layout import blank_line, pad_line, space_span

_BORDER_COLUMNS = 2
_LEFT_CONNECTOR = 1


@dataclass(slots=True)
class BoxOpts:
    """Options controlling how :func:`draw_box` frames its content."""

    border: BorderType = BorderType.ROUNDED
    border_style: Style = field(default_factory=Style)
    fill: Style = field(default_factory=Style)
    padding: Edges = field(default_factory=lambda: Edges.symmetric(0, 1))
    title: Title | None = None
    subtitle: Title | None = None
    width: int | None = None
    content_align: Align = Align.LEFT


def draw_box(content: Rendered, opts: BoxOpts, max_width: int) -> Rendered:
    """
    Frames ``content`` with a border, padding and fill.

    Parameters
    ----------
    content : Rendered
        The block to frame.
    opts : BoxOpts
        The framing options.
    max_width : int
        The maximum outer width in columns.

    Returns
    -------
    Rendered
        The framed block.
    """
    if opts.border.is_none():
        return _frame_borderless(content, opts, max_width)
    chars = opts.border.chars()
    inner_content = _inner_content_width(content, opts, max_width)
    body = _body_rows(content, inner_content, opts)
    inner_width = opts.padding.left + inner_content + opts.padding.right
    lines = [
        _edge_line(chars.top_left, chars.top_right, inner_width, opts, True)
    ]
    lines.extend(
        _border_row(row, chars.vertical, opts.border_style) for row in body
    )
    lines.append(
        _edge_line(
            chars.bottom_left, chars.bottom_right, inner_width, opts, False
        )
    )
    return Rendered(lines)


def _frame_borderless(
    content: Rendered, opts: BoxOpts, max_width: int
) -> Rendered:
    """Frames content with padding and fill only, without border glyphs."""
    inner_content = _inner_content_width(content, opts, max_width)
    return Rendered(_body_rows(content, inner_content, opts))


def _inner_content_width(
    content: Rendered, opts: BoxOpts, max_width: int
) -> int:
    """Computes the width available for content between the padding."""
    border_cols = 0 if opts.border.is_none() else _BORDER_COLUMNS
    overhead = border_cols + opts.padding.horizontal()
    if opts.width is not None:
        outer = min(opts.width, max_width)
        return max(0, outer - overhead)
    natural = content.width()
    if natural + overhead <= max_width:
        return natural
    return max(0, max_width - overhead)


def _body_rows(
    content: Rendered, inner_content: int, opts: BoxOpts
) -> list[Line]:
    """Builds the padded, filled content rows between the border edges."""
    inner_width = opts.padding.left + inner_content + opts.padding.right
    rows: list[Line] = []
    for _ in range(opts.padding.top):
        rows.append(blank_line(inner_width, opts.fill))
    for line in content.lines:
        filled = pad_line(line, inner_content, opts.content_align, opts.fill)
        rows.append(_content_row(filled, opts))
    for _ in range(opts.padding.bottom):
        rows.append(blank_line(inner_width, opts.fill))
    return rows


def _content_row(line: Line, opts: BoxOpts) -> Line:
    """Wraps an aligned content line in horizontal padding."""
    spans: list[Span] = []
    if opts.padding.left:
        spans.append(space_span(opts.padding.left, opts.fill))
    spans.extend(line.spans)
    if opts.padding.right:
        spans.append(space_span(opts.padding.right, opts.fill))
    return Line(spans)


def _border_row(row: Line, vertical: str, style: Style) -> Line:
    """Wraps a content row with the left and right vertical border glyphs."""
    edge = Span.styled(vertical, style)
    return Line([edge, *row.spans, edge])


def _edge_line(
    left: str, right: str, inner_width: int, opts: BoxOpts, is_top: bool
) -> Line:
    """Builds a top or bottom border edge, embedding the title if present."""
    title = opts.title if is_top else opts.subtitle
    corner_left = Span.styled(left, opts.border_style)
    corner_right = Span.styled(right, opts.border_style)
    horizontal = opts.border.chars().horizontal
    if title is None or not title.content.lines:
        run = Span.styled(horizontal * inner_width, opts.border_style)
        return Line([corner_left, run, corner_right])
    middle = _embed_title(title, inner_width, horizontal, opts.border_style)
    return Line([corner_left, *middle, corner_right])


def _embed_title(
    title: Title, width: int, horizontal: str, style: Style
) -> list[Span]:
    """Embeds a title in a horizontal border run of ``width`` columns."""
    label = _title_spans(title)
    label_width = sum(span.width() for span in label) + 2 * title.pad
    if label_width >= width:
        text = truncate(title.content.lines[0].plain(), width)
        return [Span.styled(text, style)]
    left_run, right_run = _title_runs(title.align, width, label_width)
    pad_span = space_span(title.pad, style)
    spans: list[Span] = []
    if left_run:
        spans.append(Span.styled(horizontal * left_run, style))
    spans.append(pad_span)
    spans.extend(label)
    spans.append(pad_span)
    if right_run:
        spans.append(Span.styled(horizontal * right_run, style))
    return spans


def _title_spans(title: Title) -> list[Span]:
    """Returns the styled spans of a title's first line."""
    if not title.content.lines:
        return []
    return list(title.content.lines[0].spans)


def _title_runs(align: Align, width: int, label_width: int) -> tuple[int, int]:
    """Splits the border run around a title according to its alignment."""
    slack = width - label_width
    if align is Align.LEFT:
        return (_LEFT_CONNECTOR, slack - _LEFT_CONNECTOR)
    if align is Align.RIGHT:
        return (slack - _LEFT_CONNECTOR, _LEFT_CONNECTOR)
    left = slack // 2
    return (left, slack - left)


def title_bar_width(title: Title) -> int:
    """Returns the column width a title occupies including its padding."""
    label = sum(visible_width(line.plain()) for line in title.content.lines[:1])
    return label + 2 * title.pad
