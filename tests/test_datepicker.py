"""Tests for the month-grid date picker prompt."""

from __future__ import annotations

from datetime import date

from sparcli.input.datepicker import DatePicker
from sparcli.input.event import InputEvent, KeyCode, KeyPress, ScriptedSource
from sparcli.input.shortcut import Shortcut

_INITIAL = date(2026, 6, 14)


def _run(picker: DatePicker, codes: list[KeyCode]):
    """Drives ``picker`` headlessly over the given key codes."""
    return picker.run_with(ScriptedSource.keys(codes))


class TestDatePickerNavigation:
    def test_right_moves_one_day_forward(self) -> None:
        outcome = _run(
            DatePicker("When?").initial(_INITIAL),
            [KeyCode.RIGHT, KeyCode.ENTER],
        )
        assert outcome.value == date(2026, 6, 15)

    def test_left_moves_one_day_back(self) -> None:
        outcome = _run(
            DatePicker("When?").initial(_INITIAL),
            [KeyCode.LEFT, KeyCode.ENTER],
        )
        assert outcome.value == date(2026, 6, 13)

    def test_up_moves_one_week_back(self) -> None:
        outcome = _run(
            DatePicker("When?").initial(_INITIAL),
            [KeyCode.UP, KeyCode.ENTER],
        )
        assert outcome.value == date(2026, 6, 7)

    def test_down_moves_one_week_forward(self) -> None:
        outcome = _run(
            DatePicker("When?").initial(_INITIAL),
            [KeyCode.DOWN, KeyCode.ENTER],
        )
        assert outcome.value == date(2026, 6, 21)

    def test_page_down_moves_one_month_forward(self) -> None:
        outcome = _run(
            DatePicker("When?").initial(_INITIAL),
            [KeyCode.PAGE_DOWN, KeyCode.ENTER],
        )
        assert outcome.value == date(2026, 7, 14)

    def test_page_up_moves_one_month_back(self) -> None:
        outcome = _run(
            DatePicker("When?").initial(_INITIAL),
            [KeyCode.PAGE_UP, KeyCode.ENTER],
        )
        assert outcome.value == date(2026, 5, 14)

    def test_shift_page_down_moves_one_year_forward(self) -> None:
        source = ScriptedSource(
            [
                InputEvent.from_key(KeyPress(KeyCode.PAGE_DOWN, shift=True)),
                InputEvent.from_key(KeyPress.new(KeyCode.ENTER)),
            ]
        )
        outcome = DatePicker("When?").initial(_INITIAL).run_with(source)
        assert outcome.value == date(2027, 6, 14)

    def test_month_jump_clamps_day(self) -> None:
        outcome = _run(
            DatePicker("When?").initial(date(2026, 1, 31)),
            [KeyCode.PAGE_DOWN, KeyCode.ENTER],
        )
        assert outcome.value == date(2026, 2, 28)


class TestDatePickerDateBounds:
    def test_forward_navigation_clamps_at_max(self) -> None:
        outcome = _run(
            DatePicker("When?").initial(date.max),
            [KeyCode.RIGHT, KeyCode.DOWN, KeyCode.ENTER],
        )
        assert outcome.value == date.max

    def test_backward_navigation_clamps_at_min(self) -> None:
        outcome = _run(
            DatePicker("When?").initial(date.min),
            [KeyCode.LEFT, KeyCode.UP, KeyCode.ENTER],
        )
        assert outcome.value == date.min

    def test_year_jump_past_max_clamps(self) -> None:
        source = ScriptedSource(
            [
                InputEvent.from_key(KeyPress(KeyCode.PAGE_DOWN, shift=True)),
                InputEvent.from_key(KeyPress.new(KeyCode.ENTER)),
            ]
        )
        outcome = DatePicker("When?").initial(date.max).run_with(source)
        assert outcome.value == date.max


class TestDatePickerSubmitCancel:
    def test_enter_submits_initial_date(self) -> None:
        outcome = _run(DatePicker("When?").initial(_INITIAL), [KeyCode.ENTER])
        assert outcome.is_submitted
        assert outcome.value == _INITIAL

    def test_esc_cancels(self) -> None:
        outcome = _run(DatePicker("When?").initial(_INITIAL), [KeyCode.ESC])
        assert outcome.is_cancelled


class TestDatePickerClear:
    def test_delete_clears_and_submits_none(self) -> None:
        outcome = _run(
            DatePicker("When?").initial(_INITIAL).allow_clear(),
            [KeyCode.DELETE, KeyCode.ENTER],
        )
        assert outcome.is_submitted
        assert outcome.value is None

    def test_delete_ignored_without_allow_clear(self) -> None:
        outcome = _run(
            DatePicker("When?").initial(_INITIAL),
            [KeyCode.DELETE, KeyCode.ENTER],
        )
        assert outcome.value == _INITIAL

    def test_navigation_resumes_from_today_after_clear(self) -> None:
        outcome = _run(
            DatePicker("When?").initial(_INITIAL).allow_clear(),
            [KeyCode.DELETE, KeyCode.RIGHT, KeyCode.ENTER],
        )
        assert outcome.value == date.today()


class TestDatePickerShortcut:
    def test_shortcut_ends_with_its_id(self) -> None:
        picker = (
            DatePicker("When?")
            .initial(_INITIAL)
            .shortcuts([Shortcut(KeyPress.ctrl_key("t"), 9, "today")])
        )
        source = ScriptedSource([InputEvent.from_key(KeyPress.ctrl_key("t"))])
        outcome = picker.run_with(source)
        assert outcome.is_shortcut
        assert outcome.shortcut_id == 9

    def test_help_overlay_opens_and_closes(self) -> None:
        picker = (
            DatePicker("When?")
            .initial(_INITIAL)
            .shortcuts([Shortcut(KeyPress.ctrl_key("t"), 1, "today")])
        )
        outcome = _run(
            picker,
            [KeyCode.char("?"), KeyCode.char("x"), KeyCode.ENTER],
        )
        assert outcome.value == _INITIAL


class TestDatePickerFrame:
    def test_frame_renders_headless(self) -> None:
        rendered = DatePicker("When?").initial(_INITIAL).frame()
        plain = rendered.plain()
        assert "When?" in plain
        assert "June 2026" in plain
        assert "Mo Tu We Th Fr Sa Su" in plain
        assert "14" in plain

    def test_frame_grid_spans_multiple_weeks(self) -> None:
        rendered = DatePicker("When?").initial(_INITIAL).frame()
        # Prompt, heading, weekday header and at least four week rows.
        assert rendered.height() >= 7
