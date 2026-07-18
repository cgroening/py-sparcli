"""
sparcli.input.shortcut
======================

Defines custom keyboard shortcuts and their footer/overlay rendering.

A :class:`Shortcut` binds a key to a caller-defined action id and a footer
label. :func:`find` maps a pressed key to its id; :func:`hint_line` renders the
compact footer, and :func:`help_overlay` the expanded key list. :func:`key_name`
turns a key press into a readable name such as ``Ctrl-S`` or ``Shift-Tab``.

:data:`HELP_KEY` and :func:`opens_help` are the single source of truth for the
key that opens that overlay, so the prompts cannot drift apart on it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.core.theme import theme
from sparcli.input.event import KeyCode, KeyKind, KeyPress


@dataclass(frozen=True, slots=True)
class Shortcut:
    """
    A bound shortcut: a key, a caller-defined id and a footer label.

    Attributes
    ----------
    key : KeyPress
        The key that triggers the action.
    id : int
        The caller-defined action id reported when fired.
    label : str
        The label shown in the footer hint line.
    """

    key: KeyPress
    id: int
    label: str


# The key that opens the help overlay, shared by every prompt offering one.
HELP_KEY = KeyCode.char("?")


def opens_help(key: KeyPress, shortcuts: list[Shortcut]) -> bool:
    """
    Returns whether ``key`` should open the help overlay.

    Parameters
    ----------
    key : KeyPress
        The key the prompt just received.
    shortcuts : list[Shortcut]
        The registered shortcuts; without any there is nothing to show.

    Returns
    -------
    bool
        ``True`` when the overlay should open.
    """
    return bool(shortcuts) and key.code == HELP_KEY


def find(key: KeyPress, shortcuts: list[Shortcut]) -> int | None:
    """Returns the id of the shortcut matching ``key``, if any."""
    for shortcut in shortcuts:
        if shortcut.key == key:
            return shortcut.id
    return None


def hint_line(shortcuts: list[Shortcut]) -> Line:
    """Builds a footer hint line: ``key label - key label - ...``."""
    active = theme()
    spans: list[Span] = []
    for index, shortcut in enumerate(shortcuts):
        if index > 0:
            spans.append(Span.styled(" · ", active.secondary))
        spans.append(
            Span.styled(
                key_name(shortcut.key), Style.new().with_fg(active.accent)
            )
        )
        spans.append(Span.styled(f" {shortcut.label}", active.secondary))
    return Line(spans)


def help_overlay(shortcuts: list[Shortcut]) -> list[Line]:
    """Builds help-overlay lines listing each shortcut (key and label)."""
    active = theme()
    lines: list[Line] = [Line.styled("Keys", active.heading)]
    for shortcut in shortcuts:
        lines.append(
            Line(
                [
                    Span.styled(
                        f"  {key_name(shortcut.key)}",
                        Style.new().with_fg(active.accent),
                    ),
                    Span.styled(f"  {shortcut.label}", active.secondary),
                ]
            )
        )
    lines.append(Line.styled("press any key to close", active.secondary))
    return lines


def key_name(key: KeyPress) -> str:
    """Returns a human-readable name for a key press."""
    parts: list[str] = []
    if key.ctrl:
        parts.append("Ctrl-")
    if key.alt:
        parts.append("Alt-")
    parts.append(_code_name(key.code))
    return "".join(parts)


_CODE_NAMES: dict[KeyKind, str] = {
    KeyKind.ENTER: "Enter",
    KeyKind.ESC: "Esc",
    KeyKind.TAB: "Tab",
    KeyKind.BACK_TAB: "Shift-Tab",
    KeyKind.BACKSPACE: "Backspace",
    KeyKind.DELETE: "Del",
    KeyKind.UP: "Up",
    KeyKind.DOWN: "Down",
    KeyKind.LEFT: "Left",
    KeyKind.RIGHT: "Right",
    KeyKind.HOME: "Home",
    KeyKind.END: "End",
    KeyKind.PAGE_UP: "PgUp",
    KeyKind.PAGE_DOWN: "PgDn",
    KeyKind.UNKNOWN: "?",
}


def _code_name(code: KeyCode) -> str:
    """Returns the base name for a key code."""
    if code.kind is KeyKind.CHAR:
        return (code.ch or "").upper()
    if code.kind is KeyKind.FUNCTION:
        return f"F{code.n}"
    return _CODE_NAMES[code.kind]
