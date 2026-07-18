"""Tests for the single- and multi-select list prompt."""

from __future__ import annotations

import pytest

from sparcli.errors import NoTerminalError
from sparcli.input.event import InputEvent, KeyCode, KeyPress, ScriptedSource
from sparcli.input.select import Select
from sparcli.input.selection import first_index
from sparcli.input.shortcut import Shortcut


def _select() -> Select:
    """Builds a three-option single-select prompt."""
    return Select("pick", options=["a", "b", "c"])


class TestSingleSelect:
    def test_move_down_then_enter_selects_cursor(self) -> None:
        source = ScriptedSource.keys([KeyCode.DOWN, KeyCode.ENTER])
        outcome = _select().run_with(source)
        assert outcome.value == [1]

    def test_first_index_reduces_to_single(self) -> None:
        source = ScriptedSource.keys([KeyCode.DOWN, KeyCode.ENTER])
        outcome = first_index(_select().run_with(source))
        assert outcome.is_submitted
        assert outcome.value == 1

    def test_home_and_end_jump_to_edges(self) -> None:
        source = ScriptedSource.keys([KeyCode.END, KeyCode.ENTER])
        assert _select().run_with(source).value == [2]
        source = ScriptedSource.keys([KeyCode.END, KeyCode.HOME, KeyCode.ENTER])
        assert _select().run_with(source).value == [0]

    def test_vim_keys_move_cursor(self) -> None:
        source = ScriptedSource.keys(
            [KeyCode.char("j"), KeyCode.char("j"), KeyCode.ENTER]
        )
        assert _select().run_with(source).value == [2]

    def test_esc_cancels(self) -> None:
        outcome = _select().run_with(ScriptedSource.keys([KeyCode.ESC]))
        assert outcome.is_cancelled


class TestCycling:
    def test_cursor_cycles_past_the_top(self) -> None:
        source = ScriptedSource.keys([KeyCode.UP, KeyCode.ENTER])
        assert _select().run_with(source).value == [2]

    def test_no_cycle_clamps_at_the_top(self) -> None:
        source = ScriptedSource.keys([KeyCode.UP, KeyCode.ENTER])
        assert _select().no_cycle().run_with(source).value == [0]

    def test_no_cycle_clamps_at_the_bottom(self) -> None:
        source = ScriptedSource.keys(
            [KeyCode.DOWN, KeyCode.DOWN, KeyCode.DOWN, KeyCode.ENTER]
        )
        assert _select().no_cycle().run_with(source).value == [2]


class TestMultiSelect:
    def test_space_toggles_and_enter_collects(self) -> None:
        source = ScriptedSource.keys(
            [
                KeyCode.char(" "),
                KeyCode.DOWN,
                KeyCode.DOWN,
                KeyCode.char(" "),
                KeyCode.ENTER,
            ]
        )
        outcome = _select().multi().run_with(source)
        assert outcome.value == [0, 2]

    def test_initial_checked_are_preselected(self) -> None:
        prompt = _select().multi().checked([1])
        source = ScriptedSource.keys([KeyCode.ENTER])
        assert prompt.run_with(source).value == [1]

    def test_space_is_inert_in_single_mode(self) -> None:
        source = ScriptedSource.keys([KeyCode.char(" "), KeyCode.ENTER])
        assert _select().run_with(source).value == [0]


class TestScrolling:
    def test_window_follows_the_cursor(self) -> None:
        options = [f"item-{index}" for index in range(20)]
        prompt = Select("deep", options=options, max_visible=5)
        prompt = prompt.cursor(15)
        frame = prompt.frame()
        text = frame.plain()
        assert "item-15" in text
        assert "item-0" not in text
        # Title plus five visible rows fit the window.
        assert frame.height() == 6

    def test_end_selects_last_of_a_long_list(self) -> None:
        options = [f"item-{index}" for index in range(20)]
        prompt = Select("deep", options=options, max_visible=5)
        source = ScriptedSource.keys([KeyCode.END, KeyCode.ENTER])
        assert prompt.run_with(source).value == [19]


class TestEmptyOptions:
    def test_multi_submits_empty_list(self) -> None:
        outcome = Select("none").multi().run_with(ScriptedSource.keys([]))
        assert outcome.is_submitted
        assert outcome.value == []

    def test_single_reduces_empty_to_cancelled(self) -> None:
        outcome = first_index(Select("none").run_with(ScriptedSource.keys([])))
        assert outcome.is_cancelled


class TestShortcutsAndHelp:
    def test_shortcut_ends_with_its_id(self) -> None:
        shortcut = Shortcut(KeyPress.ctrl_key("n"), 7, "new")
        source = ScriptedSource([InputEvent.from_key(KeyPress.ctrl_key("n"))])
        outcome = _select().shortcuts([shortcut]).run_with(source)
        assert outcome.is_shortcut
        assert outcome.shortcut_id == 7

    def test_help_overlay_opens_and_closes(self) -> None:
        shortcut = Shortcut(KeyPress.ctrl_key("n"), 1, "new")
        source = ScriptedSource.keys(
            [KeyCode.char("?"), KeyCode.char("x"), KeyCode.ENTER]
        )
        outcome = _select().shortcuts([shortcut]).run_with(source)
        assert outcome.value == [0]


class TestFrame:
    def test_frame_renders_headless(self) -> None:
        frame = _select().frame()
        assert frame.height() == 4  # title plus three rows
        assert "pick" in frame.plain()


class TestRunGuard:
    def test_run_without_terminal_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SPARCLI_NO_TTY", "1")
        with pytest.raises(NoTerminalError):
            _select().run()

    def test_run_multi_without_terminal_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SPARCLI_NO_TTY", "1")
        with pytest.raises(NoTerminalError):
            _select().multi().run_multi()
