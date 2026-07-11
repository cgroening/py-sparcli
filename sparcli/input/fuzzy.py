"""
sparcli.input.fuzzy
===================

Defines :class:`FuzzySelect`, an inline fzf-style filtering picker.

The user types a query, the option list is filtered and ranked against it, and
one (or several, in multi mode) entries can be selected. Filtering is backed by
:func:`score_match`, a small dependency-free subsequence scorer that rewards
contiguous runs and start-of-word matches. The prompt reuses
:class:`~sparcli.input.line_edit.LineEditor` for the query and follows the
shared prompt pattern of a kwargs constructor, fluent builders, a guarded
:meth:`FuzzySelect.run` and a headless :meth:`FuzzySelect.run_with`.
"""

from __future__ import annotations

from collections.abc import Iterable

from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.terminal import is_input_tty
from sparcli.core.text import Line, Span
from sparcli.core.theme import Theme, theme
from sparcli.errors import NoTerminalError
from sparcli.input.event import (
    EventKind,
    EventSource,
    InputEvent,
    KeyCode,
    KeyKind,
    KeyPress,
    TerminalSource,
)
from sparcli.input.guard import TerminalGuard
from sparcli.input.line_edit import LineEditor
from sparcli.input.outcome import Outcome
from sparcli.input.prompt import Flow, run_prompt
from sparcli.input.shortcut import Shortcut, find, hint_line

# Default number of visible result rows.
DEFAULT_VISIBLE = 10

# Scoring weights for the subsequence matcher (larger is a better match).
_MATCH_SCORE = 16  # base reward for each matched character
_CONTIGUOUS_BONUS = 8  # extra reward when a match follows the previous one
_WORD_START_BONUS = 8  # extra reward when a match begins a word

# Space key handled specially in multi mode (else typed into the query).
_SPACE = KeyCode.char(" ")

# The prompt collects indices, so every flow it produces carries this type.
_Flow = Flow[list[int]]


def score_match(query: str, option: str) -> int | None:
    """
    Scores ``option`` against a lower-cased ``query`` (order-preserving).

    Matching is case-insensitive and greedy: each query character is matched
    against the next occurrence in ``option``. Contiguous matches and matches
    at the start of a word score higher, so tighter and word-aligned hits rank
    above scattered ones.

    Parameters
    ----------
    query : str
        The already lower-cased search query; must be non-empty.
    option : str
        The candidate option text.

    Returns
    -------
    int | None
        The match score, or ``None`` when ``option`` does not contain every
        query character in order.
    """
    haystack = option.lower()
    score = 0
    query_index = 0
    previous_match = -1
    for position, character in enumerate(haystack):
        if query_index >= len(query):
            break
        if character != query[query_index]:
            continue
        score += _character_score(haystack, position, previous_match)
        previous_match = position
        query_index += 1
    if query_index < len(query):
        return None
    return score


def _character_score(haystack: str, position: int, previous_match: int) -> int:
    """Scores a single matched character with its contiguity/word bonuses."""
    score = _MATCH_SCORE
    if previous_match >= 0 and position == previous_match + 1:
        score += _CONTIGUOUS_BONUS
    if _is_word_start(haystack, position):
        score += _WORD_START_BONUS
    return score


def _is_word_start(haystack: str, position: int) -> bool:
    """Returns whether ``position`` begins a word in ``haystack``."""
    if position == 0:
        return True
    return not haystack[position - 1].isalnum()


class _State:
    """The mutable state of a running fuzzy prompt."""

    __slots__ = ("query", "filtered", "cursor", "offset", "checked")

    def __init__(
        self,
        query: LineEditor,
        filtered: list[int],
        checked: list[bool],
    ) -> None:
        self.query = query
        self.filtered = filtered
        self.cursor = 0
        self.offset = 0
        self.checked = checked


class FuzzySelect:
    """
    An inline fuzzy-select prompt with a live query filter.

    Attributes
    ----------
    prompt : str
        The label shown before the query field.
    options : Iterable[str]
        The candidate rows to filter.
    max_visible : int
        The maximum number of result rows shown at once.
    multi : bool
        Whether checkboxes and multi-selection are enabled.
    shortcuts : Iterable[Shortcut]
        Custom shortcuts shown in the footer hint line.
    initial_query : str
        The query the prompt starts with.
    """

    __slots__ = (
        "_prompt",
        "_options",
        "_max_visible",
        "_multi",
        "_shortcuts",
        "_initial_query",
    )

    def __init__(
        self,
        prompt: str,
        *,
        options: Iterable[str] = (),
        max_visible: int = DEFAULT_VISIBLE,
        multi: bool = False,
        shortcuts: Iterable[Shortcut] = (),
        initial_query: str = "",
    ) -> None:
        self._prompt = prompt
        self._options = list(options)
        self._max_visible = max(max_visible, 1)
        self._multi = multi
        self._shortcuts = list(shortcuts)
        self._initial_query = initial_query

    def options(self, options: Iterable[str]) -> FuzzySelect:
        """Sets the candidate rows and returns ``self``."""
        self._options = list(options)
        return self

    def multi(self) -> FuzzySelect:
        """Enables multi-selection with checkboxes and returns ``self``."""
        self._multi = True
        return self

    def max_visible(self, rows: int) -> FuzzySelect:
        """Sets the maximum number of result rows and returns ``self``."""
        self._max_visible = max(rows, 1)
        return self

    def query(self, query: str) -> FuzzySelect:
        """Pre-fills the search query and returns ``self``."""
        self._initial_query = query
        return self

    def shortcuts(self, shortcuts: Iterable[Shortcut]) -> FuzzySelect:
        """Registers custom shortcuts and returns ``self``."""
        self._shortcuts = list(shortcuts)
        return self

    def run(self) -> Outcome[int]:
        """
        Runs a single-select fuzzy prompt and returns the chosen index.

        Returns
        -------
        Outcome[int]
            The submitted index, a cancellation, or a fired shortcut.

        Raises
        ------
        NoTerminalError
            If standard input or output is not an interactive terminal.
        """
        return _first_index(self._run_collect())

    def run_multi(self) -> Outcome[list[int]]:
        """
        Runs a multi-select fuzzy prompt and returns all checked indices.

        Returns
        -------
        Outcome[list[int]]
            The submitted indices, a cancellation, or a fired shortcut.

        Raises
        ------
        NoTerminalError
            If standard input or output is not an interactive terminal.
        """
        return self._run_collect()

    def run_with(self, source: EventSource) -> Outcome[list[int]]:
        """
        Runs the prompt against ``source`` and returns the checked indices.

        Parameters
        ----------
        source : EventSource
            The event source driving the prompt (a fake in tests).

        Returns
        -------
        Outcome[list[int]]
            The submitted indices, a cancellation, or a fired shortcut.
        """
        state = self._initial_state()
        return run_prompt(source, state, self._render, self._handle)

    def frame(self) -> Rendered:
        """Renders the opening frame without running the prompt."""
        return self._render(self._initial_state(), False)

    def _run_collect(self) -> Outcome[list[int]]:
        """Sets up the terminal and runs the prompt loop."""
        if not is_input_tty():
            raise NoTerminalError
        with TerminalGuard():
            return self.run_with(TerminalSource())

    def _initial_state(self) -> _State:
        """Builds the starting state, applying the initial query."""
        return _State(
            query=LineEditor(self._initial_query),
            filtered=self._filter(self._initial_query),
            checked=[False] * len(self._options),
        )

    def _render(self, state: _State, final_frame: bool) -> Rendered:
        """Builds the frame: the query field plus the filtered results."""
        active = theme()
        lines = [_query_line(self._prompt, state, active, final_frame)]
        end = min(state.offset + self._max_visible, len(state.filtered))
        for row in range(state.offset, end):
            lines.append(self._result_line(state, row, active))
        if not final_frame and self._shortcuts:
            lines.append(hint_line(self._shortcuts))
        return Rendered(lines)

    def _result_line(self, state: _State, row: int, active: Theme) -> Line:
        """Renders one result row at filtered position ``row``."""
        option_index = state.filtered[row]
        is_cursor = row == state.cursor
        marker = active.cursor_marker() if is_cursor else active.marker()
        spans = [Span.styled(marker, active.selection)]
        if self._multi:
            checkbox = (
                active.checkbox_on()
                if state.checked[option_index]
                else active.checkbox_off()
            )
            spans.append(Span.raw(checkbox))
        style = active.selection if is_cursor else Style.new()
        spans.append(Span.styled(self._options[option_index], style))
        return Line(spans)

    def _handle(self, state: _State, event: InputEvent) -> _Flow:
        """Handles one input event."""
        if event.kind is EventKind.PASTE and event.text is not None:
            state.query.insert_str(event.text)
            self._refilter(state)
            return _Flow.cont()
        if event.kind is EventKind.KEY and event.key is not None:
            return self._handle_key(state, event.key)
        return _Flow.cont()

    def _handle_key(self, state: _State, key: KeyPress) -> _Flow:
        """Handles a single key press."""
        shortcut_id = find(key, self._shortcuts)
        if shortcut_id is not None:
            return _Flow.shortcut(shortcut_id)
        if key.code == KeyCode.ESC:
            return _Flow.cancel()
        if key.code == KeyCode.ENTER:
            return self._submit(state)
        self._edit_or_move(state, key.code)
        return _Flow.cont()

    def _edit_or_move(self, state: _State, code: KeyCode) -> None:
        """Applies a navigation or query-editing key to the state."""
        if code == KeyCode.UP:
            self._move_cursor(state, -1)
        elif code == KeyCode.DOWN:
            self._move_cursor(state, 1)
        elif code == _SPACE and self._multi:
            self._toggle(state)
        elif code == KeyCode.BACKSPACE:
            state.query.backspace()
            self._refilter(state)
        elif code.kind is KeyKind.CHAR and code.ch is not None:
            state.query.insert_char(code.ch)
            self._refilter(state)

    def _submit(self, state: _State) -> _Flow:
        """Submits the current selection when possible."""
        if self._multi:
            indices = [
                index
                for index in range(len(self._options))
                if state.checked[index]
            ]
            return _Flow.submit(indices)
        if 0 <= state.cursor < len(state.filtered):
            return _Flow.submit([state.filtered[state.cursor]])
        return _Flow.cont()

    def _toggle(self, state: _State) -> None:
        """Toggles the checkbox of the row under the cursor."""
        if 0 <= state.cursor < len(state.filtered):
            option_index = state.filtered[state.cursor]
            state.checked[option_index] = not state.checked[option_index]

    def _refilter(self, state: _State) -> None:
        """Recomputes the filtered list and resets the cursor to the top."""
        state.filtered = self._filter(state.query.value())
        state.cursor = 0
        state.offset = 0

    def _move_cursor(self, state: _State, delta: int) -> None:
        """Moves the cursor within the results, keeping it visible."""
        length = len(state.filtered)
        if length == 0:
            return
        state.cursor = (state.cursor + delta) % length
        if state.cursor < state.offset:
            state.offset = state.cursor
        elif state.cursor >= state.offset + self._max_visible:
            state.offset = state.cursor + 1 - self._max_visible

    def _filter(self, query: str) -> list[int]:
        """Filters and ranks options for ``query`` (original order if empty)."""
        if not query:
            return list(range(len(self._options)))
        query_lower = query.lower()
        scored: list[tuple[int, int]] = []
        for index, option in enumerate(self._options):
            score = score_match(query_lower, option)
            if score is not None:
                scored.append((index, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        return [index for index, _ in scored]


def _query_line(
    prompt: str, state: _State, active: Theme, final_frame: bool
) -> Line:
    """Builds the query input line (the cursor is hidden on the final frame)."""
    spans = [Span.styled(f"{prompt} ", active.title)]
    spans.append(Span.raw(state.query.value()))
    if not final_frame:
        spans.append(Span.styled(" ", active.cursor))
    return Line(spans)


def _first_index(outcome: Outcome[list[int]]) -> Outcome[int]:
    """Reduces a collected outcome to its first index (single-select)."""
    if outcome.is_shortcut:
        return Outcome.shortcut(outcome.shortcut_id or 0)
    if outcome.is_submitted and outcome.value:
        return Outcome.submitted(outcome.value[0])
    return Outcome.cancelled()
