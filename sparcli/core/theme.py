"""
sparcli.core.theme
==================

Defines the unified :class:`Theme` shared by output widgets and input prompts.

A single process-wide theme drives accent color, semantic styles (success,
error, ...), the default border and whether Unicode or ASCII glyphs are used.
Read the active theme with :func:`theme` and replace it with :func:`set_theme`;
per-call widget options still override individual theme values.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from sparcli.core.border import BorderType
from sparcli.core.color import Color
from sparcli.core.style import Style

DEFAULT_ACCENT = Color.rgb(137, 180, 250)

_TITLE = Style.from_color(DEFAULT_ACCENT).bold()
_SUCCESS = Style.from_color(Color.GREEN)
_ERROR = Style.from_color(Color.RED)
_WARNING = Style.from_color(Color.YELLOW)
_INFO = Style.from_color(DEFAULT_ACCENT)
_DEBUG = Style.from_color(Color.MAGENTA)
_SECONDARY = Style.new().dim()
_SELECTION = Style.from_color(DEFAULT_ACCENT).bold()
_CURSOR = Style.new().with_fg(Color.BLACK).with_bg(DEFAULT_ACCENT)

# Two-step glyphs: (unicode, ascii). ASCII is the fallback for plain terminals.
_BULLET = ("•", "*")
_CURSOR_MARKER = ("‣ ", "> ")
_MARKER = ("  ", "  ")
_CHECKBOX_ON = ("◉ ", "[x] ")
_CHECKBOX_OFF = ("◯ ", "[ ] ")


@dataclass(frozen=True, slots=True)
class Theme:
    """
    The look shared across output and input.

    Attributes
    ----------
    accent : Color
        The single highlight color for titles, selections and active items.
    title, heading, secondary, success, error, warning, info, debug, \
    hint : Style
        Semantic styles applied throughout the library.
    selection, cursor : Style
        Styles for the highlighted item and the text cursor.
    border : BorderType
        The default border look.
    unicode : bool
        When ``False``, glyph accessors return their ASCII fallbacks.
    """

    accent: Color = DEFAULT_ACCENT
    title: Style = _TITLE
    heading: Style = _TITLE
    secondary: Style = _SECONDARY
    success: Style = _SUCCESS
    error: Style = _ERROR
    warning: Style = _WARNING
    info: Style = _INFO
    debug: Style = _DEBUG
    hint: Style = _SECONDARY
    selection: Style = _SELECTION
    cursor: Style = _CURSOR
    border: BorderType = BorderType.ROUNDED
    unicode: bool = True

    def bullet(self) -> str:
        """Returns the list bullet glyph."""
        return self._glyph(_BULLET)

    def cursor_marker(self) -> str:
        """Returns the marker shown next to the active list item."""
        return self._glyph(_CURSOR_MARKER)

    def marker(self) -> str:
        """Returns the blank marker aligning non-active list items."""
        return self._glyph(_MARKER)

    def checkbox_on(self) -> str:
        """Returns the checked checkbox glyph."""
        return self._glyph(_CHECKBOX_ON)

    def checkbox_off(self) -> str:
        """Returns the unchecked checkbox glyph."""
        return self._glyph(_CHECKBOX_OFF)

    def _glyph(self, pair: tuple[str, str]) -> str:
        """Returns the unicode or ascii glyph based on the theme setting."""
        return pair[0] if self.unicode else pair[1]


_lock = threading.Lock()
_current = Theme()


def theme() -> Theme:
    """Returns the active process-wide theme."""
    with _lock:
        return _current


def set_theme(new_theme: Theme) -> None:
    """
    Replaces the active process-wide theme.

    Parameters
    ----------
    new_theme : Theme
        The theme to install. Widget options still override individual values.
    """
    # A single process-wide theme drives both input and output.
    global _current  # noqa: PLW0603
    with _lock:
        _current = new_theme
