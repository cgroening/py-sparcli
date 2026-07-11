"""
sparcli.input.text
==================

Defines :class:`TextInput`, a single-line text prompt.

The prompt edits one line through the shared :class:`~sparcli.input.line_edit.
LineEditor`, validates and filters input, recalls history with Up/Down and
completes suggestions either as dim inline ghost text or as a navigable
dropdown. It returns an :class:`~sparcli.input.outcome.Outcome` carrying the
submitted string, or a cancellation. Rendering and the event loop are delegated
to the shared infrastructure, so this module only wires configuration, state
and key handling together.
"""

from __future__ import annotations

import enum
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.terminal import is_input_tty
from sparcli.core.text import Line, Span
from sparcli.core.theme import Theme, theme
from sparcli.errors import NoTerminalError, SparcliError
from sparcli.input.editor import edit_text
from sparcli.input.event import (
    EventKind,
    EventSource,
    InputEvent,
    KeyCode,
    KeyKind,
    KeyPress,
    TerminalSource,
)
from sparcli.input.field import (
    error_line,
    field_line,
    placeholder_line,
    value_line,
)
from sparcli.input.guard import TerminalGuard
from sparcli.input.history import History
from sparcli.input.line_edit import LineEditor
from sparcli.input.outcome import Outcome
from sparcli.input.prompt import Flow, run_prompt
from sparcli.input.validate import CharFilter, Validator

logger = logging.getLogger(__name__)

# Maximum number of dropdown rows shown at once.
MAX_DROPDOWN = 5


class MatchMode(enum.Enum):
    """How suggestions are matched against the typed value."""

    PREFIX = enum.auto()
    SUBSEQUENCE = enum.auto()


@dataclass(slots=True)
class _State:
    """Mutable state of a running text prompt."""

    editor: LineEditor
    error: str | None
    history_index: int | None
    dropdown_index: int | None
    history_entries: list[str]
    store: History | None


# Ctrl-letter editing actions dispatched on the shared line editor.
_CTRL_ACTIONS: dict[str, Callable[[LineEditor], None]] = {
    "a": LineEditor.select_all,
    "w": LineEditor.delete_word_back,
    "u": LineEditor.kill_to_line_start,
    "k": LineEditor.kill_to_line_end,
    "c": LineEditor.copy,
    "x": LineEditor.cut,
    "v": LineEditor.paste,
}


class TextInput:
    """
    A single-line text input prompt.

    Build a prompt with the fluent setters and run it with :meth:`run`. Every
    setter mutates and returns ``self``, so calls chain. The default matching
    completes suggestions by prefix as inline ghost text; :meth:`dropdown`
    switches to a navigable list and :meth:`fuzzy_suggestions` to subsequence
    matching.
    """

    __slots__ = (
        "_prompt",
        "_initial",
        "_placeholder",
        "_max_chars",
        "_hide_char_count",
        "_validator",
        "_char_filter",
        "_suggestions",
        "_history",
        "_history_app",
        "_dropdown",
        "_match_mode",
        "_editor_enabled",
        "_editor_command",
    )

    def __init__(self, prompt: str) -> None:
        self._prompt: str = prompt
        self._initial: str = ""
        self._placeholder: str = ""
        self._max_chars: int = 0
        self._hide_char_count: bool = False
        self._validator: Validator | None = None
        self._char_filter: CharFilter | None = None
        self._suggestions: list[str] = []
        self._history: list[str] = []
        self._history_app: str | None = None
        self._dropdown: bool = False
        self._match_mode: MatchMode = MatchMode.PREFIX
        self._editor_enabled: bool = False
        self._editor_command: str | None = None

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
        self._suggestions = list(values)
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
        self._dropdown = True
        return self

    def fuzzy_suggestions(self) -> TextInput:
        """Matches suggestions by subsequence (fuzzy) instead of prefix."""
        self._match_mode = MatchMode.SUBSEQUENCE
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
        if not is_input_tty():
            raise NoTerminalError()
        with TerminalGuard():
            return self.run_with(TerminalSource())

    def run_with(self, source: EventSource) -> Outcome[str]:
        """Runs the prompt against any event source (the test seam)."""
        store, entries = self._load_history()
        state = _State(
            editor=LineEditor(self._initial),
            error=None,
            history_index=None,
            dropdown_index=None,
            history_entries=entries,
            store=store,
        )
        return run_prompt(source, state, self._render, self._handle)

    def frame(self) -> Rendered:
        """Renders the static initial frame without running (for previews)."""
        state = _State(
            editor=LineEditor(self._initial),
            error=None,
            history_index=None,
            dropdown_index=None,
            history_entries=list(self._history),
            store=None,
        )
        return self._render(state, False)

    def _load_history(self) -> tuple[History | None, list[str]]:
        """Loads the persistent store and the entries used for recall."""
        if self._history_app is None:
            return (None, list(self._history))
        store = History.for_app(self._history_app)
        store.load()
        return (store, store.entries())

    def _render(self, state: _State, final: bool) -> Rendered:
        """Builds the prompt frame: field line, ghost text and dropdown."""
        active_theme = theme()
        value = state.editor.value()
        if final:
            line = value_line(self._prompt, value, Style.new(), active_theme)
            return Rendered([line])
        lines = self._value_lines(state, value, active_theme)
        self._append_char_count(lines, state, active_theme)
        if self._dropdown:
            self._push_dropdown(lines, state, value, active_theme)
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
        if not self._dropdown:
            ghost = self._ghost(value)
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

    def _push_dropdown(
        self,
        lines: list[Line],
        state: _State,
        value: str,
        active_theme: Theme,
    ) -> None:
        """Appends the dropdown rows for the current matches."""
        matches = self._matches(value)
        for row, index in enumerate(matches[:MAX_DROPDOWN]):
            active = state.dropdown_index == row
            marker = (
                active_theme.cursor_marker()
                if active
                else active_theme.marker()
            )
            style = active_theme.selection if active else active_theme.secondary
            lines.append(
                Line(
                    [
                        Span.styled(marker, active_theme.selection),
                        Span.styled(self._suggestions[index], style),
                    ]
                )
            )

    def _ghost(self, value: str) -> str | None:
        """Returns the ghost completion suffix for ``value``, if any."""
        if not value:
            return None
        for suggestion in self._suggestions:
            if suggestion.startswith(value) and len(suggestion) > len(value):
                return suggestion[len(value) :]
        return None

    def _matches(self, value: str) -> list[int]:
        """Returns the suggestion indices matching ``value`` (declared order)."""
        if not value:
            return []
        needle = value.lower()
        return [
            index
            for index, suggestion in enumerate(self._suggestions)
            if _matches_suggestion(needle, suggestion, self._match_mode)
        ]

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
        elif code == KeyCode.LEFT:
            state.editor.move_left(select=key.shift)
        elif code == KeyCode.RIGHT:
            state.editor.move_right(select=key.shift)
        elif code == KeyCode.HOME:
            state.editor.move_home(select=key.shift)
        elif code == KeyCode.END:
            state.editor.move_end(select=key.shift)
        elif code == KeyCode.BACKSPACE:
            state.editor.backspace()
            state.dropdown_index = None
        elif code == KeyCode.DELETE:
            state.editor.delete()
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
        action = _CTRL_ACTIONS.get(code.ch)
        if action is not None:
            action(state.editor)
        return Flow[str].cont()

    def _on_enter(self, state: _State) -> Flow[str]:
        """Enter accepts a highlighted dropdown row, otherwise submits."""
        if self._dropdown and state.dropdown_index is not None:
            self._accept_completion(state)
            return Flow[str].cont()
        return self._submit(state)

    def _recall_up(self, state: _State) -> None:
        """Up moves the dropdown highlight, else recalls older history."""
        if self._dropdown:
            self._dropdown_move(state, -1)
        else:
            self._history_prev(state)

    def _recall_down(self, state: _State) -> None:
        """Down moves the dropdown highlight, else recalls newer history."""
        if self._dropdown:
            self._dropdown_move(state, 1)
        else:
            self._history_next(state)

    def _dropdown_move(self, state: _State, delta: int) -> None:
        """Moves the dropdown highlight, cycling over the current matches."""
        count = min(len(self._matches(state.editor.value())), MAX_DROPDOWN)
        if count == 0:
            state.dropdown_index = None
            return
        current = state.dropdown_index
        if current is None:
            state.dropdown_index = 0 if delta > 0 else count - 1
        else:
            state.dropdown_index = (current + delta) % count

    def _accept_completion(self, state: _State) -> None:
        """Fills from the highlighted match, or the ghost completion."""
        if not self._dropdown:
            self._accept_ghost(state)
            return
        matches = self._matches(state.editor.value())
        row = state.dropdown_index if state.dropdown_index is not None else 0
        if row < len(matches):
            state.editor.set_value(self._suggestions[matches[row]])
            state.dropdown_index = None

    def _accept_ghost(self, state: _State) -> None:
        """Accepts the ghost completion, if present."""
        value = state.editor.value()
        ghost = self._ghost(value)
        if ghost is not None:
            state.editor.set_value(f"{value}{ghost}")

    def _launch_editor(self, state: _State) -> Flow[str]:
        """Opens the value in an external editor, then refreshes the prompt."""
        text = self._edit_value(state.editor.value())
        if text is not None:
            single_line = text.replace("\n", " ").rstrip()
            state.editor.set_value(single_line)
            state.dropdown_index = None
        return Flow[str].refresh()

    def _edit_value(self, value: str) -> str | None:
        """Round-trips ``value`` through the editor, swallowing failures."""
        try:
            return edit_text(self._editor_command, value, ".txt")
        except SparcliError as error:
            logger.debug("could not edit value: %s", error)
            return None

    def _submit(self, state: _State) -> Flow[str]:
        """Validates and submits the current value, persisting history."""
        value = state.editor.value()
        if self._validator is not None:
            message = self._validator(value)
            if message is not None:
                state.error = message
                return Flow[str].cont()
        if state.store is not None:
            state.store.add(value)
            state.store.save()
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

    def _history_prev(self, state: _State) -> None:
        """Recalls the previous (older) history entry."""
        if not state.history_entries:
            return
        if state.history_index is None:
            index = len(state.history_entries) - 1
        elif state.history_index == 0:
            index = 0
        else:
            index = state.history_index - 1
        state.history_index = index
        state.editor.set_value(state.history_entries[index])

    def _history_next(self, state: _State) -> None:
        """Recalls the next (newer) entry, clearing past the newest."""
        index = state.history_index
        if index is None:
            return
        if index + 1 < len(state.history_entries):
            state.history_index = index + 1
            state.editor.set_value(state.history_entries[index + 1])
        else:
            state.history_index = None
            state.editor.set_value("")


def _matches_suggestion(needle: str, suggestion: str, mode: MatchMode) -> bool:
    """Returns whether ``suggestion`` matches the lowercase ``needle``."""
    hay = suggestion.lower()
    if mode is MatchMode.PREFIX:
        return hay.startswith(needle)
    return _is_subsequence(needle, hay)


def _is_subsequence(needle: str, hay: str) -> bool:
    """Returns whether all chars of ``needle`` appear in ``hay`` in order."""
    chars = iter(hay)
    return all(target in chars for target in needle)
