"""
sparcli.output.alert
===================

Defines :class:`Alert`, a bordered callout with a semantic icon and color.

Each :class:`AlertKind` maps to a theme style (info, warning, error, ...) and a
two-step icon (Unicode with an ASCII fallback). The border and icon share the
kind's accent color. Convenience constructors cover the common kinds.
"""

from __future__ import annotations

import enum

from sparcli.core.render import Renderable, Rendered
from sparcli.core.style import Style
from sparcli.core.text import IntoText, Line, Span, Text, into_text
from sparcli.core.theme import Theme, theme
from sparcli.output.box import BoxOpts, draw_box


class AlertKind(enum.Enum):
    """The semantic kind of an alert."""

    INFO = enum.auto()
    DEBUG = enum.auto()
    WARNING = enum.auto()
    ERROR = enum.auto()
    SUCCESS = enum.auto()


# Per-kind (unicode icon, ascii icon).
_ICONS: dict[AlertKind, tuple[str, str]] = {
    AlertKind.INFO: ("ℹ", "i"),
    AlertKind.DEBUG: ("⚙", "*"),
    AlertKind.WARNING: ("⚠", "!"),
    AlertKind.ERROR: ("✖", "x"),
    AlertKind.SUCCESS: ("✔", "+"),
}


def _kind_style(kind: AlertKind, active: Theme) -> Style:
    """Returns the theme style for an alert kind."""
    styles: dict[AlertKind, Style] = {
        AlertKind.INFO: active.info,
        AlertKind.DEBUG: active.debug,
        AlertKind.WARNING: active.warning,
        AlertKind.ERROR: active.error,
        AlertKind.SUCCESS: active.success,
    }
    return styles[kind]


class Alert(Renderable):
    """A bordered callout carrying a semantic icon and color."""

    __slots__ = ("_kind", "_content")

    def __init__(self, kind: AlertKind, content: IntoText) -> None:
        self._kind = kind
        self._content = into_text(content)

    @classmethod
    def info(cls, content: IntoText) -> Alert:
        """Returns an info alert."""
        return cls(AlertKind.INFO, content)

    @classmethod
    def debug(cls, content: IntoText) -> Alert:
        """Returns a debug alert."""
        return cls(AlertKind.DEBUG, content)

    @classmethod
    def warning(cls, content: IntoText) -> Alert:
        """Returns a warning alert."""
        return cls(AlertKind.WARNING, content)

    @classmethod
    def error(cls, content: IntoText) -> Alert:
        """Returns an error alert."""
        return cls(AlertKind.ERROR, content)

    @classmethod
    def success(cls, content: IntoText) -> Alert:
        """Returns a success alert."""
        return cls(AlertKind.SUCCESS, content)

    def render(self, max_width: int) -> Rendered:
        """Renders the alert into at most ``max_width`` columns."""
        active = theme()
        style = _kind_style(self._kind, active)
        icon = _ICONS[self._kind][0 if active.unicode else 1]
        content = _prefix_icon(self._content, icon, style)
        opts = BoxOpts(
            border=active.border,
            border_style=style,
        )
        return draw_box(Rendered.from_text(content), opts, max_width)


def _prefix_icon(content: Text, icon: str, style: Style) -> Text:
    """Prepends a styled icon to the first line of ``content``."""
    lines = list(content.lines) or [Line()]
    first = lines[0]
    prefixed = Line([Span.styled(f"{icon} ", style), *first.spans])
    return Text([prefixed, *lines[1:]])
