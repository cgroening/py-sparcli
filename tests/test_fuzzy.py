"""Tests for the inline fuzzy-select prompt and its scorer."""

from __future__ import annotations

import pytest

from sparcli.errors import NoTerminalError
from sparcli.input.event import InputEvent, KeyCode, KeyPress, ScriptedSource
from sparcli.input.fuzzy import FuzzySelect, score_match
from sparcli.input.shortcut import Shortcut


def _fuzzy() -> FuzzySelect:
    """Builds a four-option fuzzy prompt."""
    return FuzzySelect("find", options=["apple", "banana", "cherry", "grape"])


class TestScorer:
    def test_missing_character_does_not_match(self) -> None:
        assert score_match("z", "apple") is None

    def test_out_of_order_does_not_match(self) -> None:
        assert score_match("ba", "ab") is None

    def test_contiguous_beats_scattered(self) -> None:
        tight = score_match("ab", "ab")
        loose = score_match("ab", "axb")
        assert tight is not None
        assert loose is not None
        assert tight > loose

    def test_word_start_beats_mid_word(self) -> None:
        aligned = score_match("c", "cat")
        buried = score_match("c", "scat")
        assert aligned is not None
        assert buried is not None
        assert aligned > buried


class TestFiltering:
    def test_typing_filters_and_enter_selects(self) -> None:
        source = ScriptedSource.keys(
            [KeyCode.char("c"), KeyCode.char("h"), KeyCode.ENTER]
        )
        assert _fuzzy().run_with(source).value == [2]

    def test_empty_query_shows_all_in_order(self) -> None:
        outcome = _fuzzy().run_with(ScriptedSource.keys([KeyCode.ENTER]))
        assert outcome.value == [0]

    def test_best_match_is_ranked_first(self) -> None:
        prompt = FuzzySelect("find", options=["xapp", "app"])
        source = ScriptedSource.keys(
            [KeyCode.char("a"), KeyCode.char("p"), KeyCode.ENTER]
        )
        # 'app' scores higher (word start + contiguous) so it ranks first.
        assert prompt.run_with(source).value == [1]

    def test_backspace_reverts_the_query(self) -> None:
        source = ScriptedSource.keys(
            [
                KeyCode.char("x"),
                KeyCode.BACKSPACE,
                KeyCode.char("c"),
                KeyCode.char("h"),
                KeyCode.ENTER,
            ]
        )
        assert _fuzzy().run_with(source).value == [2]

    def test_initial_query_filters_up_front(self) -> None:
        prompt = _fuzzy().query("gr")
        assert prompt.run_with(ScriptedSource.keys([KeyCode.ENTER])).value == [
            3
        ]


class TestNavigation:
    def test_down_moves_within_results(self) -> None:
        source = ScriptedSource.keys([KeyCode.DOWN, KeyCode.ENTER])
        assert _fuzzy().run_with(source).value == [1]

    def test_up_cycles_to_the_bottom(self) -> None:
        source = ScriptedSource.keys([KeyCode.UP, KeyCode.ENTER])
        assert _fuzzy().run_with(source).value == [3]

    def test_esc_cancels(self) -> None:
        assert (
            _fuzzy().run_with(ScriptedSource.keys([KeyCode.ESC])).is_cancelled
        )


class TestMultiSelect:
    def test_space_toggles_and_enter_collects(self) -> None:
        source = ScriptedSource.keys(
            [
                KeyCode.char(" "),
                KeyCode.DOWN,
                KeyCode.char(" "),
                KeyCode.ENTER,
            ]
        )
        assert _fuzzy().multi().run_with(source).value == [0, 1]

    def test_empty_options_submit_empty_list(self) -> None:
        outcome = (
            FuzzySelect("none")
            .multi()
            .run_with(ScriptedSource.keys([KeyCode.ENTER]))
        )
        assert outcome.value == []


class TestPasteAndShortcuts:
    def test_paste_inserts_into_the_query(self) -> None:
        source = ScriptedSource([InputEvent.paste("ch"), _enter_event()])
        assert _fuzzy().run_with(source).value == [2]

    def test_shortcut_ends_with_its_id(self) -> None:
        shortcut = Shortcut(KeyPress.ctrl_key("n"), 5, "new")
        source = ScriptedSource([InputEvent.from_key(KeyPress.ctrl_key("n"))])
        outcome = _fuzzy().shortcuts([shortcut]).run_with(source)
        assert outcome.is_shortcut
        assert outcome.shortcut_id == 5


class TestFrame:
    def test_frame_renders_headless(self) -> None:
        frame = _fuzzy().frame()
        assert "find" in frame.plain()
        assert frame.height() == 5  # query line plus four results


class TestRunGuard:
    def test_run_without_terminal_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SPARCLI_NO_TTY", "1")
        with pytest.raises(NoTerminalError):
            _fuzzy().run()

    def test_run_multi_without_terminal_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SPARCLI_NO_TTY", "1")
        with pytest.raises(NoTerminalError):
            _fuzzy().multi().run_multi()


def _enter_event() -> InputEvent:
    """Returns an Enter key event."""
    return InputEvent.from_key(KeyPress.new(KeyCode.ENTER))
