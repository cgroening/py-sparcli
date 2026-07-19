"""
sparcli.core.width
==================

Computes display width and reflows text, aware of Unicode and ANSI escapes.

Wide glyphs (CJK, many emoji) count as two columns, zero-width combining marks
as zero, and ANSI escape sequences as nothing. These helpers are the basis for
every alignment, truncation and wrapping decision in the library. Width is
derived from the standard library's :mod:`unicodedata`, so no third-party
dependency is required.

:mod:`~sparcli.core.width.measure` holds the plain-string helpers;
:mod:`~sparcli.core.width.line` holds their style-preserving counterparts for
:class:`~sparcli.core.text.Line`.
"""

from __future__ import annotations

from sparcli.core.width.line import truncate_line, wrap_line
from sparcli.core.width.measure import (
    char_width,
    strip_ansi,
    truncate,
    visible_width,
    wrap,
)

__all__ = [
    "char_width",
    "strip_ansi",
    "truncate",
    "truncate_line",
    "visible_width",
    "wrap",
    "wrap_line",
]
