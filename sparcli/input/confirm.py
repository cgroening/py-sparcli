"""
sparcli.input.confirm
=====================

Defines :class:`Confirm`, a yes/no confirmation prompt.

The prompt shows two options; the selected one is highlighted and the other is
dimmed. ``y``/``n`` answer directly, Enter accepts the current selection, and
the arrows, Tab, ``h`` or ``l`` toggle it. Registered
:class:`~sparcli.input.shortcut.Shortcut` keys end the prompt with a shortcut
outcome and appear in a footer hint and the ``?`` help overlay.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.core.theme import Theme, theme
from sparcli.input.event import (
    EventKind,
    EventSource,
    InputEvent,
    KeyCode,
    KeyPress,
)
from sparcli.input.prompt import Flow, run_on_terminal, run_prompt
from sparcli.input.shortcut import (
    Shortcut,
    find,
    help_overlay,
    hint_line,
    opens_help,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sparcli.input.outcome import Outcome

# Keys that toggle the current selection.
_TOGGLE_CODES = frozenset(
    {
        KeyCode.LEFT,
        KeyCode.RIGHT,
        KeyCode.TAB,
        KeyCode.char("h"),
        KeyCode.char("l"),
    }
)


class _State:
    """The mutable state of a running confirm prompt."""

    __slots__ = ("help", "yes")

    def __init__(self, yes: bool) -> None:
        self.yes = yes
        self.help = False


class Confirm:
    """A yes/no confirmation prompt with custom labels and shortcuts."""

    __slots__ = (
        "_default_yes",
        "_no_label",
        "_question",
        "_shortcuts",
        "_yes_label",
    )

    def __init__(
        self,
        question: str = "",
        *,
        default_yes: bool = False,
        yes_label: str = "Yes",
        no_label: str = "No",
        shortcuts: Iterable[Shortcut] | None = None,
    ) -> None:
        self._question = question
        self._default_yes = default_yes
        self._yes_label = yes_label
        self._no_label = no_label
        self._shortcuts: list[Shortcut] = (
            list(shortcuts) if shortcuts is not None else []
        )

    def shortcuts(self, shortcuts: Iterable[Shortcut]) -> Confirm:
        """Registers footer/overlay shortcuts and returns ``self``."""
        self._shortcuts = list(shortcuts)
        return self

    def default_yes(self) -> Confirm:
        """Sets the initial selection to "Yes" and returns ``self``."""
        self._default_yes = True
        return self

    def labels(self, yes: str, no: str) -> Confirm:
        """Sets custom labels for the two options and returns ``self``."""
        self._yes_label = yes
        self._no_label = no
        return self

    def run(self) -> Outcome[bool]:
        """
        Runs the prompt on the real terminal.

        Returns
        -------
        Outcome[bool]
            The chosen answer, a cancellation or a fired shortcut.

        Raises
        ------
        NoTerminalError
            If there is no interactive terminal.
        """
        return run_on_terminal(self.run_with)

    def run_with(self, source: EventSource) -> Outcome[bool]:
        """
        Runs the prompt against ``source`` and returns the outcome.

        Parameters
        ----------
        source : EventSource
            The event source driving the prompt (a fake in tests).

        Returns
        -------
        Outcome[bool]
            The submitted value, a cancellation, or a fired shortcut.
        """
        state = _State(self._default_yes)
        return run_prompt(source, state, self._render, self._handle)

    def frame(self) -> Rendered:
        """Renders the prompt's static frame without running it."""
        state = _State(self._default_yes)
        return self._render(state, False)

    def _render(self, state: _State, final: bool) -> Rendered:
        """Builds the prompt frame for the current selection."""
        active = theme()
        if state.help:
            return Rendered(help_overlay(self._shortcuts))
        spans = [
            Span.raw(f"{self._question} "),
            _option_span(self._yes_label, state.yes, active),
            Span.raw(" "),
            _option_span(self._no_label, not state.yes, active),
        ]
        lines = [Line(spans)]
        if self._shortcuts:
            lines.append(hint_line(self._shortcuts))
        return Rendered(lines)

    def _handle(self, state: _State, event: InputEvent) -> Flow[bool]:
        """Handles one input event."""
        if event.kind is not EventKind.KEY or event.key is None:
            return Flow[bool].cont()
        return self._handle_key(state, event.key)

    def _handle_key(self, state: _State, key: KeyPress) -> Flow[bool]:
        """Handles a single key press."""
        if state.help:
            state.help = False
            return Flow[bool].cont()
        if key.is_ctrl("c"):
            return Flow[bool].cancel()
        if opens_help(key, self._shortcuts):
            state.help = True
            return Flow[bool].cont()
        fired = find(key, self._shortcuts)
        if fired is not None:
            return Flow[bool].shortcut(fired)
        return self._decide(state, key.code)

    def _decide(self, state: _State, code: KeyCode) -> Flow[bool]:
        """Applies a selection, submission or cancellation key."""
        if code == KeyCode.ESC:
            return Flow[bool].cancel()
        if code == KeyCode.ENTER:
            return Flow[bool].submit(state.yes)
        if code in (KeyCode.char("y"), KeyCode.char("Y")):
            return Flow[bool].submit(True)
        if code in (KeyCode.char("n"), KeyCode.char("N")):
            return Flow[bool].submit(False)
        if code in _TOGGLE_CODES:
            state.yes = not state.yes
        return Flow[bool].cont()


def _option_span(label: str, selected: bool, active: Theme) -> Span:
    """Renders one option, highlighted when selected and dimmed otherwise."""
    if selected:
        return Span.styled(f"[{label}]", active.selection)
    return Span.styled(f" {label} ", Style.new().dim())
