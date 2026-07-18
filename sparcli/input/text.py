"""
sparcli.input.text
==================

Defines :class:`TextInput`, a single-line text prompt.

The prompt edits one line through the shared :class:`~sparcli.input.line_edit.
LineEditor`, validates and filters input, recalls history with Up/Down and
completes suggestions either as dim inline ghost text or as a navigable
dropdown. It returns an :class:`~sparcli.input.outcome.Outcome` carrying the
submitted string, or a cancellation. Rendering and the event loop are delegated
to the shared infrastructure, and the two larger concerns live in their own
collaborators: :class:`~sparcli.input.completion.Completion` for suggestions and
:class:`~sparcli.input.recall.HistoryRecall` for Up/Down history. This module
only wires configuration, state and key handling together.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.core.theme import Theme, theme
from sparcli.input.completion import Completion, MatchMode
from sparcli.input.editor import edit_or_none
from sparcli.input.event import (
    EventKind,
    EventSource,
    InputEvent,
    KeyCode,
    KeyKind,
    KeyPress,
)
from sparcli.input.field import (
    error_line,
    field_line,
    placeholder_line,
    value_line,
)
from sparcli.input.line_edit import (
    CTRL_ACTIONS,
    LineEditor,
    apply_caret_key,
)
from sparcli.input.prompt import Flow, run_on_terminal, run_prompt
from sparcli.input.recall import HistoryRecall

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from sparcli.input.outcome import Outcome
    from sparcli.input.validate import CharFilter, Validator

logger = logging.getLogger(__name__)

# Temporary file suffix handed to the external editor.
_EDITOR_SUFFIX = ".txt"


@dataclass(slots=True)
class _State:
    """Mutable state of a running text prompt."""

    editor: LineEditor
    error: str | None
    dropdown_index: int | None
    recall: HistoryRecall


class TextInput:
    """
    A single-line text input prompt.

    Configure a prompt either through the keyword-only constructor options or
    the matching fluent setters (each mutates and returns ``self``, so calls
    chain), then run it with :meth:`run`. The default matching completes
    suggestions by prefix as inline ghost text; :meth:`dropdown` switches to a
    navigable list and :meth:`fuzzy_suggestions` to subsequence matching.
    """

    __slots__ = (
        "_char_filter",
        "_completion",
        "_editor_command",
        "_editor_enabled",
        "_hide_char_count",
        "_history",
        "_history_app",
        "_initial",
        "_max_chars",
        "_placeholder",
        "_prompt",
        "_validator",
    )

    def __init__(
        self,
        prompt: str,
        *,
        initial: str = "",
        placeholder: str = "",
        max_chars: int = 0,
        hide_char_count: bool = False,
        validator: Validator | None = None,
        char_filter: CharFilter | None = None,
        suggestions: Iterable[str] = (),
        history: Iterable[str] = (),
        history_app: str | None = None,
        dropdown: bool = False,
        fuzzy_suggestions: bool = False,
        editor: bool = False,
        editor_command: str | None = None,
    ) -> None:
        self._prompt: str = prompt
        self._initial: str = initial
        self._placeholder: str = placeholder
        self._max_chars: int = max_chars
        self._hide_char_count: bool = hide_char_count
        self._validator: Validator | None = validator
        self._char_filter: CharFilter | None = char_filter
        self._completion = Completion(
            suggestions,
            match_mode=(
                MatchMode.SUBSEQUENCE if fuzzy_suggestions else MatchMode.PREFIX
            ),
            dropdown=dropdown,
        )
        self._history: list[str] = list(history)
        self._history_app: str | None = history_app
        self._editor_enabled: bool = editor or editor_command is not None
        self._editor_command: str | None = editor_command

    def initial(self, value: str) -> TextInput:
        """Sets the initial value and returns ``self``."""
        self._initial = value
        return self

    def placeholder(self, value: str) -> TextInput:
        """Sets the placeholder shown when empty and returns ``self``."""
        self._placeholder = value
        return self

    def max_chars(self, maximum: int) -> TextInput:
        """Limits the number of characters (0 = unlimited)."""
        self._max_chars = maximum
        return self

    def validate(self, validator: Validator) -> TextInput:
        """Sets a full-value validator and returns ``self``."""
        self._validator = validator
        return self

    def char_filter(self, char_filter: CharFilter) -> TextInput:
        """Sets a per-character filter and returns ``self``."""
        self._char_filter = char_filter
        return self

    def suggestions(self, values: Iterable[str]) -> TextInput:
        """Sets autocomplete suggestions (prefix-matched ghost text)."""
        self._completion.suggestions = list(values)
        return self

    def history(self, entries: Iterable[str]) -> TextInput:
        """
        Provides history entries recalled with Up/Down.

        History is unavailable while a navigable dropdown is enabled, since
        Up/Down then drive the suggestion list.
        """
        self._history = list(entries)
        return self

    def dropdown(self) -> TextInput:
        """
        Shows suggestions as a navigable dropdown instead of ghost text.

        Up/Down move the highlight, Tab/Enter accept it.
        """
        self._completion.dropdown = True
        return self

    def fuzzy_suggestions(self) -> TextInput:
        """Matches suggestions by subsequence (fuzzy) instead of prefix."""
        self._completion.match_mode = MatchMode.SUBSEQUENCE
        return self

    def hide_char_count(self) -> TextInput:
        """Hides the ``(n/max)`` counter shown when ``max_chars`` is set."""
        self._hide_char_count = True
        return self

    def history_app(self, app: str) -> TextInput:
        """
        Persists history under the app's state dir, recalling and auto-adding.

        Loads previous entries for Up/Down recall and appends the submitted
        value on success. Overrides :meth:`history`.
        """
        self._history_app = app
        return self

    def editor(self) -> TextInput:
        """Enables opening the value in ``$EDITOR`` with Ctrl-G."""
        self._editor_enabled = True
        return self

    def editor_command(self, command: str) -> TextInput:
        """Sets the editor command (implies :meth:`editor`)."""
        self._editor_enabled = True
        self._editor_command = command
        return self

    def run(self) -> Outcome[str]:
        """
        Runs the prompt on the real terminal.

        Returns
        -------
        Outcome[str]
            The submitted value or a cancellation.

        Raises
        ------
        NoTerminalError
            When there is no interactive terminal.
        """
        return run_on_terminal(self.run_with)

    def run_with(self, source: EventSource) -> Outcome[str]:
        """
        Runs the prompt against ``source`` and returns the outcome.

        Parameters
        ----------
        source : EventSource
            The event source driving the prompt (a fake in tests).

        Returns
        -------
        Outcome[str]
            The submitted value, a cancellation, or a fired shortcut.
        """
        state = _State(
            editor=LineEditor(self._initial),
            error=None,
            dropdown_index=None,
            recall=HistoryRecall.for_app(self._history_app, self._history),
        )
        return run_prompt(source, state, self._render, self._handle)

    def frame(self) -> Rendered:
        """Renders the static initial frame without running (for previews)."""
        state = _State(
            editor=LineEditor(self._initial),
            error=None,
            dropdown_index=None,
            recall=HistoryRecall(self._history),
        )
        return self._render(state, False)

    def _render(self, state: _State, final: bool) -> Rendered:
        """Builds the prompt frame: field line, ghost text and dropdown."""
        active_theme = theme()
        value = state.editor.value()
        if final:
            line = value_line(self._prompt, value, Style.new(), active_theme)
            return Rendered([line])
        lines = self._value_lines(state, value, active_theme)
        self._append_char_count(lines, state, active_theme)
        if self._completion.dropdown:
            lines.extend(
                self._completion.rows(value, state.dropdown_index, active_theme)
            )
        if state.error is not None:
            lines.append(error_line(state.error, active_theme))
        return Rendered(lines)

    def _value_lines(
        self, state: _State, value: str, active_theme: Theme
    ) -> list[Line]:
        """Builds the leading placeholder or field line with ghost text."""
        if not value and self._placeholder:
            return [
                placeholder_line(self._prompt, self._placeholder, active_theme)
            ]
        line = field_line(
            self._prompt, value, state.editor.cursor, Style.new(), active_theme
        )
        if not self._completion.dropdown:
            ghost = self._completion.ghost(value)
            if ghost is not None:
                line.spans.append(Span.styled(ghost, active_theme.secondary))
        return [line]

    def _append_char_count(
        self, lines: list[Line], state: _State, active_theme: Theme
    ) -> None:
        """Appends the ``(n/max)`` counter to the last line, when enabled."""
        if self._max_chars <= 0 or self._hide_char_count or not lines:
            return
        count = f" ({len(state.editor)}/{self._max_chars})"
        lines[-1].spans.append(Span.styled(count, active_theme.secondary))

    def _handle(self, state: _State, event: InputEvent) -> Flow[str]:
        """Handles one input event."""
        if event.kind is EventKind.PASTE and event.text is not None:
            self._insert_filtered(state, event.text)
            return Flow[str].cont()
        if event.kind is EventKind.KEY and event.key is not None:
            return self._handle_key(state, event.key)
        return Flow[str].cont()

    def _handle_key(self, state: _State, key: KeyPress) -> Flow[str]:
        """Handles a single key press."""
        if key.ctrl:
            return self._handle_ctrl(state, key)
        code = key.code
        if code == KeyCode.ESC:
            return Flow[str].cancel()
        if code == KeyCode.ENTER:
            return self._on_enter(state)
        self._edit_key(state, key)
        return Flow[str].cont()

    def _edit_key(self, state: _State, key: KeyPress) -> None:
        """Applies a non-terminal editing or navigation key."""
        code = key.code
        if code == KeyCode.TAB:
            self._accept_completion(state)
        elif code == KeyCode.UP:
            self._recall_up(state)
        elif code == KeyCode.DOWN:
            self._recall_down(state)
        elif apply_caret_key(state.editor, key, select=key.shift):
            if code in (KeyCode.BACKSPACE, KeyCode.DELETE):
                state.dropdown_index = None
        elif code.kind is KeyKind.CHAR and code.ch is not None:
            self._type_char(state, code.ch)

    def _handle_ctrl(self, state: _State, key: KeyPress) -> Flow[str]:
        """Handles Ctrl-modified editing keys."""
        code = key.code
        if code.kind is not KeyKind.CHAR or code.ch is None:
            return Flow[str].cont()
        if code.ch == "g" and self._editor_enabled:
            return self._launch_editor(state)
        action = CTRL_ACTIONS.get(code.ch)
        if action is not None:
            action(state.editor)
        return Flow[str].cont()

    def _on_enter(self, state: _State) -> Flow[str]:
        """Enter accepts a highlighted dropdown row, otherwise submits."""
        if self._completion.dropdown and state.dropdown_index is not None:
            self._accept_completion(state)
            return Flow[str].cont()
        return self._submit(state)

    def _recall_up(self, state: _State) -> None:
        """Up moves the dropdown highlight, else recalls older history."""
        self._move_or_recall(state, -1, state.recall.previous)

    def _recall_down(self, state: _State) -> None:
        """Down moves the dropdown highlight, else recalls newer history."""
        self._move_or_recall(state, 1, state.recall.following)

    def _move_or_recall(
        self, state: _State, delta: int, recall: Callable[[], str | None]
    ) -> None:
        """Moves the dropdown highlight, or applies a recalled entry."""
        if self._completion.dropdown:
            state.dropdown_index = self._completion.move(
                state.editor.value(), state.dropdown_index, delta
            )
            return
        recalled = recall()
        if recalled is not None:
            state.editor.set_value(recalled)

    def _accept_completion(self, state: _State) -> None:
        """Fills from the highlighted match, or the ghost completion."""
        completed = self._completion.accept(
            state.editor.value(), state.dropdown_index
        )
        if completed is None:
            return
        state.editor.set_value(completed)
        if self._completion.dropdown:
            state.dropdown_index = None

    def _launch_editor(self, state: _State) -> Flow[str]:
        """Opens the value in an external editor, then refreshes the prompt."""
        text = edit_or_none(
            self._editor_command, state.editor.value(), _EDITOR_SUFFIX
        )
        if text is not None:
            single_line = text.replace("\n", " ").rstrip()
            state.editor.set_value(single_line)
            state.dropdown_index = None
        return Flow[str].refresh()

    def _submit(self, state: _State) -> Flow[str]:
        """Validates and submits the current value, persisting history."""
        value = state.editor.value()
        if self._validator is not None:
            message = self._validator(value)
            if message is not None:
                state.error = message
                return Flow[str].cont()
        state.recall.remember(value)
        return Flow[str].submit(value)

    def _type_char(self, state: _State, ch: str) -> None:
        """Types one character if it passes the filter and length limit."""
        if self._char_filter is not None and not self._char_filter(ch):
            return
        if self._max_chars > 0 and len(state.editor) >= self._max_chars:
            return
        state.editor.insert_char(ch)
        state.error = None
        state.dropdown_index = None

    def _insert_filtered(self, state: _State, text: str) -> None:
        """Inserts pasted text, applying the character filter."""
        for ch in text:
            self._type_char(state, ch)
