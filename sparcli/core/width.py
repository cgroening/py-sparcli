"""
sparcli.core.width
==================

Computes display width and reflows text, aware of Unicode and ANSI escapes.

Wide glyphs (CJK, many emoji) count as two columns, zero-width combining marks
as zero, and ANSI escape sequences as nothing. These helpers are the basis for
every alignment, truncation and wrapping decision in the library. Width is
derived from the standard library's :mod:`unicodedata`, so no third-party
dependency is required.
"""

from __future__ import annotations

import unicodedata

_ESC = "\x1b"
_BELL = "\x07"
_CSI_FINAL_MIN = 0x40
_CSI_FINAL_MAX = 0x7E
_ZERO_WIDTH_CATEGORIES = frozenset({"Mn", "Me", "Cf"})
_WIDE_EAST_ASIAN = frozenset({"W", "F"})


def char_width(char: str) -> int:
    """
    Returns the display width of a single character in terminal columns.

    Parameters
    ----------
    char : str
        A single character.

    Returns
    -------
    int
        ``0`` for combining or control characters, ``2`` for wide East Asian
        glyphs, otherwise ``1``.
    """
    if char == "\x00" or unicodedata.combining(char):
        return 0
    category = unicodedata.category(char)
    if category in _ZERO_WIDTH_CATEGORIES or category == "Cc":
        return 0
    if unicodedata.east_asian_width(char) in _WIDE_EAST_ASIAN:
        return 2
    return 1


def visible_width(text: str) -> int:
    """
    Returns the column width of ``text``, ignoring ANSI escape sequences.

    Parameters
    ----------
    text : str
        The text to measure. May contain ANSI escapes.

    Returns
    -------
    int
        The number of terminal columns the text occupies.
    """
    if _ESC not in text:
        return sum(char_width(char) for char in text)
    return sum(char_width(char) for char in strip_ansi(text))


def strip_ansi(text: str) -> str:
    """
    Removes CSI and OSC escape sequences from ``text``.

    Parameters
    ----------
    text : str
        The text to clean.

    Returns
    -------
    str
        ``text`` with ANSI control sequences removed.
    """
    if _ESC not in text:
        return text
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == _ESC:
            index = _skip_escape(text, index)
            continue
        out.append(char)
        index += 1
    return "".join(out)


def truncate(text: str, max_cols: int, ellipsis: str = "…") -> str:
    """
    Truncates ``text`` to ``max_cols`` columns, appending an ellipsis.

    Parameters
    ----------
    text : str
        The text to truncate. Assumed to contain no ANSI escapes.
    max_cols : int
        The maximum number of columns the result may occupy.
    ellipsis : str
        The marker appended when content is dropped.

    Returns
    -------
    str
        The original text if it fits, otherwise a truncated copy ending in the
        ellipsis.
    """
    if max_cols <= 0:
        return ""
    if visible_width(text) <= max_cols:
        return text
    budget = max_cols - visible_width(ellipsis)
    if budget <= 0:
        return ellipsis[:max_cols]
    kept: list[str] = []
    used = 0
    for char in text:
        width = char_width(char)
        if used + width > budget:
            break
        kept.append(char)
        used += width
    return "".join(kept) + ellipsis


def wrap(text: str, width: int) -> list[str]:
    """
    Wraps ``text`` to ``width`` columns on word boundaries.

    Parameters
    ----------
    text : str
        The text to wrap. Newlines split paragraphs first.
    width : int
        The maximum column width per line. A width of ``0`` disables wrapping.

    Returns
    -------
    list[str]
        The wrapped lines. Empty input yields a single empty line.
    """
    if width <= 0:
        return [text]
    lines: list[str] = []
    for paragraph in text.split("\n"):
        lines.extend(_wrap_paragraph(paragraph, width))
    return lines or [""]


def _wrap_paragraph(text: str, width: int) -> list[str]:
    """Wraps a single newline-free paragraph to ``width`` columns."""
    lines: list[str] = []
    current = ""
    current_width = 0
    for word in text.split(" "):
        word_width = visible_width(word)
        gap = 1 if current else 0
        if current and current_width + gap + word_width > width:
            lines.append(current)
            current = ""
            current_width = 0
            gap = 0
        if word_width > width:
            if current:
                lines.append(current)
                current = ""
                current_width = 0
            lines.extend(_split_long_word(word, width))
            if lines:
                current = lines.pop()
                current_width = visible_width(current)
            continue
        current = f"{current} {word}" if current else word
        current_width += gap + word_width
    lines.append(current)
    return lines


def _split_long_word(word: str, width: int) -> list[str]:
    """Hard-splits a word wider than ``width`` into column-sized chunks."""
    chunks: list[str] = []
    current = ""
    current_width = 0
    for char in word:
        char_w = char_width(char)
        if current_width + char_w > width and current:
            chunks.append(current)
            current = ""
            current_width = 0
        current += char
        current_width += char_w
    if current:
        chunks.append(current)
    return chunks


def _skip_escape(text: str, index: int) -> int:
    """Returns the index just past the escape sequence starting at ``index``."""
    length = len(text)
    if index + 1 >= length:
        return index + 1
    marker = text[index + 1]
    if marker == "[":
        return _skip_csi(text, index + 2)
    if marker == "]":
        return _skip_osc(text, index + 2)
    return index + 2


def _skip_csi(text: str, index: int) -> int:
    """Returns the index past a CSI sequence body starting at ``index``."""
    length = len(text)
    while index < length:
        code = ord(text[index])
        if _CSI_FINAL_MIN <= code <= _CSI_FINAL_MAX:
            return index + 1
        index += 1
    return length


def _skip_osc(text: str, index: int) -> int:
    """Returns the index past an OSC sequence starting at ``index``."""
    length = len(text)
    while index < length:
        char = text[index]
        if char == _BELL:
            return index + 1
        if char == _ESC and index + 1 < length and text[index + 1] == "\\":
            return index + 2
        index += 1
    return length
