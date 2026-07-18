"""
sparcli.input.datepicker
========================

Defines :class:`DatePicker`, a month-grid calendar prompt.

The picker navigates a :class:`datetime.date` with the arrow and page keys,
submits on Enter and cancels on Esc. With :meth:`DatePicker.allow_clear`,
Delete or Backspace clears the selection to a "no date" state that submits as
``None``; any navigation key then resumes editing from today. The layout mirrors
the Rust port: a ``Month Year`` heading, a Monday-first weekday header and a day
grid with the selected day highlighted.
"""

from __future__ import annotations

import calendar
from datetime import MAXYEAR, MINYEAR, date, timedelta
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

# The picker's result payload: a selected date, or ``None`` when cleared.
_Result = date | None
# Flow specialized for this prompt, so control constructors bind their type.
_DateFlow = Flow[_Result]

# Number of days in a calendar week (Monday-first grid columns).
DAYS_PER_WEEK = 7
# Number of months in a year (used for month arithmetic and year jumps).
MONTHS_PER_YEAR = 12

# Monday-first weekday column header.
_WEEKDAY_HEADER = "Mo Tu We Th Fr Sa Su"
# Line shown while the selection is cleared.
_EMPTY_HINT = "(no date) - press an arrow to choose"
# Width of one day cell in the grid ("nn "), also the empty-lead placeholder.
_CELL = "   "
# English month names, indexed by ``month - 1``.
_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


class _State:
    """Mutable state of a running date picker (selection and help flag)."""

    __slots__ = ("help", "selected")

    def __init__(self, selected: date | None) -> None:
        self.selected: date | None = selected
        self.help: bool = False


class DatePicker:
    """
    A month-grid date picker prompt.

    Attributes
    ----------
    prompt : str
        The label shown above the calendar.

    Examples
    --------
    >>> import datetime
    >>> picker = DatePicker("When?").initial(datetime.date(2026, 6, 14))
    >>> picker.frame().height() > 0
    True
    """

    __slots__ = ("_allow_clear", "_initial", "_prompt", "_shortcuts")

    def __init__(
        self,
        prompt: str,
        *,
        initial: date | None = None,
        allow_clear: bool = False,
        shortcuts: Iterable[Shortcut] | None = None,
    ) -> None:
        self._prompt = prompt
        self._initial: date = initial if initial is not None else _today()
        self._allow_clear = allow_clear
        self._shortcuts: list[Shortcut] = (
            list(shortcuts) if shortcuts is not None else []
        )

    def initial(self, value: date) -> DatePicker:
        """Sets the initially selected date and returns ``self``."""
        self._initial = value
        return self

    def allow_clear(self) -> DatePicker:
        """Allows Delete/Backspace to clear to a "no date" state."""
        self._allow_clear = True
        return self

    def shortcuts(self, shortcuts: Iterable[Shortcut]) -> DatePicker:
        """Registers footer/help shortcuts and returns ``self``."""
        self._shortcuts = list(shortcuts)
        return self

    def run(self) -> Outcome[date | None]:
        """
        Runs the picker on the real terminal.

        Returns
        -------
        Outcome[date | None]
            The submitted date (``None`` when cleared), a cancellation, or a
            fired shortcut.

        Raises
        ------
        NoTerminalError
            If standard input or output is not an interactive terminal.
        """
        return run_on_terminal(self.run_with)

    def run_with(self, source: EventSource) -> Outcome[date | None]:
        """
        Runs the picker against any event source (used for tests).

        Parameters
        ----------
        source : EventSource
            The source of input events driving the prompt.

        Returns
        -------
        Outcome[date | None]
            The prompt result.
        """
        state = _State(self._initial)
        return run_prompt(source, state, self._render, self._handle)

    def frame(self) -> Rendered:
        """Renders the picker's static frame without running it."""
        return self._render(_State(self._initial), False)

    def _render(self, state: _State, final_frame: bool) -> Rendered:
        """Builds the calendar frame for the current state."""
        active = theme()
        if state.help:
            return Rendered(help_overlay(self._shortcuts))
        lines = [Line.styled(self._prompt, active.title)]
        if state.selected is None:
            lines.append(Line.styled(_EMPTY_HINT, active.secondary))
        else:
            lines.append(_header_line(state.selected, active))
            lines.append(_weekday_header(active))
            lines.extend(_month_grid(state.selected, active))
        if self._shortcuts:
            lines.append(hint_line(self._shortcuts))
        return Rendered(lines)

    def _handle(self, state: _State, event: InputEvent) -> Flow[date | None]:
        """Handles one event for the picker."""
        if event.kind is not EventKind.KEY or event.key is None:
            return _DateFlow.cont()
        key = event.key
        if state.help:
            state.help = False
            return _DateFlow.cont()
        if opens_help(key, self._shortcuts):
            state.help = True
            return _DateFlow.cont()
        fired = find(key, self._shortcuts)
        if fired is not None:
            return _DateFlow.shortcut(fired)
        return self._navigate(state, key)

    def _navigate(self, state: _State, key: KeyPress) -> Flow[date | None]:
        """Applies control and navigation keys to the selection."""
        if key.code == KeyCode.ESC:
            return _DateFlow.cancel()
        if key.code == KeyCode.ENTER:
            return _DateFlow.submit(state.selected)
        if self._allow_clear and key.code in (
            KeyCode.DELETE,
            KeyCode.BACKSPACE,
        ):
            state.selected = None
            return _DateFlow.cont()
        if state.selected is None:
            state.selected = _today()
            return _DateFlow.cont()
        state.selected = _apply_nav(state.selected, key)
        return _DateFlow.cont()


def _today() -> date:
    """
    Returns today's date in the local time zone.

    This is a deliberate divergence from the Rust port, which uses UTC because
    it has no local-time API without a dependency. Near midnight the default
    day can therefore differ by one between the two ports; see ``CLAUDE.md``.

    Returns
    -------
    date
        The current local date.
    """
    return date.today()  # noqa: DTZ011


def _header_line(value: date, active: Theme) -> Line:
    """Builds the "Month Year" heading line."""
    label = f"{_MONTH_NAMES[value.month - 1]} {value.year}"
    return Line.styled(label, active.heading)


def _weekday_header(active: Theme) -> Line:
    """Builds the Monday-first weekday column header."""
    return Line.styled(_WEEKDAY_HEADER, active.secondary)


def _month_grid(selected: date, active: Theme) -> list[Line]:
    """Builds the day grid, highlighting the selected day."""
    lead = selected.replace(day=1).weekday()
    _, days = calendar.monthrange(selected.year, selected.month)
    lines: list[Line] = []
    spans: list[Span] = [Span.raw(_CELL * lead)]
    column = lead
    for day in range(1, days + 1):
        spans.append(_day_span(day, day == selected.day, active))
        column += 1
        if column == DAYS_PER_WEEK:
            lines.append(Line(spans))
            spans = []
            column = 0
    if spans:
        lines.append(Line(spans))
    return lines


def _day_span(day: int, selected: bool, active: Theme) -> Span:
    """Renders one day cell, highlighting the selection."""
    style = active.selection if selected else Style.new()
    return Span.styled(f"{day:>2} ", style)


def _apply_nav(current: date, key: KeyPress) -> date:
    """Returns the selection shifted by a navigation key press."""
    code = key.code
    if code == KeyCode.LEFT:
        return _shift_days(current, -1)
    if code == KeyCode.RIGHT:
        return _shift_days(current, 1)
    if code == KeyCode.UP:
        return _shift_days(current, -DAYS_PER_WEEK)
    if code == KeyCode.DOWN:
        return _shift_days(current, DAYS_PER_WEEK)
    if code == KeyCode.PAGE_UP:
        return _add_months(current, -MONTHS_PER_YEAR if key.shift else -1)
    if code == KeyCode.PAGE_DOWN:
        return _add_months(current, MONTHS_PER_YEAR if key.shift else 1)
    return current


def _shift_days(current: date, delta: int) -> date:
    """Returns ``current`` shifted by ``delta`` days, clamped to the range."""
    try:
        return current + timedelta(days=delta)
    except OverflowError:
        return date.max if delta > 0 else date.min


def _add_months(value: date, delta: int) -> date:
    """Returns ``value`` shifted by ``delta`` months, clamping the day."""
    zero_based = value.month - 1 + delta
    year = value.year + zero_based // MONTHS_PER_YEAR
    month = zero_based % MONTHS_PER_YEAR + 1
    if year < MINYEAR:
        return date.min
    if year > MAXYEAR:
        return date.max
    _, last = calendar.monthrange(year, month)
    return date(year, month, min(value.day, last))
