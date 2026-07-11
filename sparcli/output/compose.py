"""
sparcli.output.compose
======================

Composition helpers for stacking and placing rendered blocks.

:func:`align` pads a block to a width, :func:`pad` adds box-model spacing, and
:func:`vstack` stacks blocks vertically with an optional gap. They operate on
:class:`~sparcli.core.render.Rendered` values, so widgets and hand-built blocks
compose the same way.
"""

from __future__ import annotations

from collections.abc import Sequence

from sparcli.core.geometry import Align, Edges
from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.output.layout import blank_line, pad_line, space_span


def align(rendered: Rendered, width: int, alignment: Align) -> Rendered:
    """
    Pads every line of ``rendered`` to ``width`` using ``alignment``.

    Parameters
    ----------
    rendered : Rendered
        The block to align.
    width : int
        The target width in columns.
    alignment : Align
        How to place each line within the width.

    Returns
    -------
    Rendered
        A new block with every line padded to ``width``.
    """
    return Rendered(
        [pad_line(line, width, alignment) for line in rendered.lines]
    )


def pad(
    rendered: Rendered, edges: Edges, style: Style | None = None
) -> Rendered:
    """
    Surrounds ``rendered`` with box-model spacing.

    Parameters
    ----------
    rendered : Rendered
        The block to pad.
    edges : Edges
        The spacing to add on each side.
    style : Style | None
        The fill style for the padding.

    Returns
    -------
    Rendered
        A new padded block.
    """
    inner_width = rendered.width()
    total_width = inner_width + edges.horizontal()
    lines: list[Line] = []
    for _ in range(edges.top):
        lines.append(blank_line(total_width, style))
    for line in rendered.lines:
        spans: list[Span] = []
        if edges.left:
            spans.append(space_span(edges.left, style))
        spans.extend(line.spans)
        gap = inner_width - line.width() + edges.right
        if gap > 0:
            spans.append(space_span(gap, style))
        lines.append(Line(spans))
    for _ in range(edges.bottom):
        lines.append(blank_line(total_width, style))
    return Rendered(lines)


def vstack(blocks: Sequence[Rendered], gap: int = 0) -> Rendered:
    """
    Stacks blocks vertically with ``gap`` blank lines between them.

    Parameters
    ----------
    blocks : Sequence[Rendered]
        The blocks to stack, top to bottom.
    gap : int
        The number of blank lines inserted between blocks.

    Returns
    -------
    Rendered
        The stacked block.
    """
    lines: list[Line] = []
    for index, block in enumerate(blocks):
        if index and gap:
            lines.extend(blank_line() for _ in range(gap))
        lines.extend(block.lines)
    return Rendered(lines)
