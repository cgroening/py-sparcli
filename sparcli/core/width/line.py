"""
sparcli.core.width.line
=======================

Wraps and truncates :class:`~sparcli.core.text.Line` without losing styles.

The plain-string :func:`~sparcli.core.width.measure.wrap` and
:func:`~sparcli.core.width.measure.truncate` return ``str`` and therefore drop
every span's style and hyperlink. The helpers here keep both, which is what
filled widgets need: a hole in a styled run shows up as a gap in the
background, not merely as lost color.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.core.width.measure import (
    char_width,
    truncate,
    visible_width,
    wrap,
)


def wrap_line(line: Line, width: int) -> list[Line]:
    """
    Wraps a line to at most ``width`` columns, preserving styles.

    Word-aware and consistent with :func:`~sparcli.core.width.measure.wrap`:
    runs of whitespace collapse to a single space and words wider than
    ``width`` are hard-split. A word that straddles a span boundary stays whole
    and keeps both styles.

    Parameters
    ----------
    line : Line
        The line to reflow.
    width : int
        The maximum column width. A value of zero disables wrapping and yields
        the line unchanged.

    Returns
    -------
    list[Line]
        The wrapped lines, each with its spans' styles and links intact.

    Examples
    --------
    >>> from sparcli.core.text import Line
    >>> [row.plain() for row in wrap_line(Line.raw("one two three"), 7)]
    ['one two', 'three']
    """
    if width <= 0:
        return [Line(list(line.spans))]
    if len(line.spans) <= 1:
        return _wrap_single_span(line, width)
    return _pack_words(_split_words(line), width)


def truncate_line(line: Line, max_cols: int, ellipsis: str = "…") -> Line:
    """
    Truncates a line to at most ``max_cols`` columns, preserving styles.

    Never splits a wide glyph, and the result never exceeds ``max_cols``.

    Parameters
    ----------
    line : Line
        The line to shorten.
    max_cols : int
        The maximum column width.
    ellipsis : str, optional
        The marker appended when content was dropped.

    Returns
    -------
    Line
        The shortened line, with the ellipsis carrying the style of the last
        surviving span.

    Examples
    --------
    >>> from sparcli.core.text import Line
    >>> truncate_line(Line.raw("hello world"), 7).plain()
    'hello …'
    """
    if max_cols <= 0:
        return Line()
    if line.width() <= max_cols:
        return Line(list(line.spans))
    fallback = line.spans[0].style if line.spans else None
    marker_width = visible_width(ellipsis)
    if marker_width >= max_cols:
        clipped = truncate(ellipsis, max_cols, "")
        return Line([Span(content=clipped, style=_or_default(fallback))])
    spans = _clip_spans(line, max_cols - marker_width)
    style = spans[-1].style if spans else _or_default(fallback)
    spans.append(Span(content=ellipsis, style=style))
    return Line(_merge_adjacent(spans))


def _wrap_single_span(line: Line, width: int) -> list[Line]:
    """Wraps a line of at most one span via the plain-string wrapper."""
    if not line.spans:
        return [Line()]
    span = line.spans[0]
    return [
        Line([Span(content=chunk, style=span.style, link=span.link)])
        for chunk in wrap(span.content, width)
    ]


@dataclass(slots=True)
class _WordPart:
    """One styled fragment of a word; a word may span several styles."""

    content: str
    style: Style
    link: str | None


@dataclass(slots=True)
class _Word:
    """A whitespace-delimited word, possibly assembled from several spans."""

    parts: list[_WordPart] = field(default_factory=list)
    width: int = 0

    def push(self, char: str, span: Span) -> None:
        """Appends one character carrying the style of ``span``."""
        self.width += char_width(char)
        last = self.parts[-1] if self.parts else None
        if (
            last is not None
            and last.style == span.style
            and last.link == span.link
        ):
            last.content += char
            return
        self.parts.append(
            _WordPart(content=char, style=span.style, link=span.link)
        )

    def to_spans(self) -> list[Span]:
        """Converts the word's fragments into spans."""
        return [
            Span(content=part.content, style=part.style, link=part.link)
            for part in self.parts
        ]


@dataclass(slots=True)
class _Pending:
    """The line currently being assembled by :func:`_pack_words`."""

    spans: list[Span] = field(default_factory=list)
    width: int = 0

    def flush(self, out: list[Line]) -> None:
        """Emits the collected spans as a line and starts a fresh one."""
        out.append(Line(_merge_adjacent(self.spans)))
        self.spans = []
        self.width = 0


def _split_words(line: Line) -> list[_Word]:
    """Splits a line into words, keeping cross-span words whole."""
    words: list[_Word] = []
    current = _Word()
    for span in line.spans:
        for char in span.content:
            if char.isspace():
                if current.parts:
                    words.append(current)
                    current = _Word()
                continue
            current.push(char, span)
    if current.parts:
        words.append(current)
    return words


def _pack_words(words: list[_Word], width: int) -> list[Line]:
    """Greedily packs words into lines of at most ``width`` columns."""
    out: list[Line] = []
    pending = _Pending()
    for word in words:
        separator = 1 if pending.spans else 0
        if pending.spans and pending.width + separator + word.width > width:
            pending.flush(out)
        if word.width > width:
            _hard_split_word(word, width, pending, out)
            continue
        _push_separator(pending)
        pending.spans.extend(word.to_spans())
        pending.width += word.width
    pending.flush(out)
    return out


def _push_separator(pending: _Pending) -> None:
    """Adds the single space joining two words on the same line."""
    if not pending.spans:
        return
    pending.spans.append(Span(content=" ", style=pending.spans[-1].style))
    pending.width += 1


def _hard_split_word(
    word: _Word, width: int, pending: _Pending, out: list[Line]
) -> None:
    """Splits a word wider than ``width`` across lines, keeping styles."""
    if pending.spans:
        pending.flush(out)
    for part in word.parts:
        for char in part.content:
            size = char_width(char)
            if pending.spans and pending.width + size > width:
                pending.flush(out)
            pending.spans.append(
                Span(content=char, style=part.style, link=part.link)
            )
            pending.width += size


def _clip_spans(line: Line, budget: int) -> list[Span]:
    """Clips spans to ``budget`` columns without splitting a wide glyph."""
    spans: list[Span] = []
    used = 0
    for span in line.spans:
        content = ""
        for char in span.content:
            size = char_width(char)
            if used + size > budget:
                break
            content += char
            used += size
        if content:
            spans.append(
                Span(content=content, style=span.style, link=span.link)
            )
        if used >= budget:
            break
    return spans


def _merge_adjacent(spans: list[Span]) -> list[Span]:
    """Merges consecutive spans that share style and hyperlink."""
    merged: list[Span] = []
    for span in spans:
        last = merged[-1] if merged else None
        if (
            last is not None
            and last.style == span.style
            and last.link == span.link
        ):
            merged[-1] = Span(
                content=last.content + span.content,
                style=last.style,
                link=last.link,
            )
            continue
        merged.append(span)
    return merged


def _or_default(style: Style | None) -> Style:
    """Returns the style, or an empty one when there is none."""
    return style if style is not None else Style.new()
