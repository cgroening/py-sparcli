"""Tests for the single-line :class:`TextInput` prompt, driven headlessly."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

import pytest

from sparcli.input.event import KeyCode, ScriptedSource
from sparcli.input.text import TextInput
from sparcli.input.validate import digits, min_len, non_empty


def _run(prompt: TextInput, codes: list[KeyCode]) -> object:
    """Drives ``prompt`` with a scripted key sequence and returns the outcome."""
    return prompt.run_with(ScriptedSource.keys(codes))


class TestTextInput:
    def test_types_and_submits_value(self) -> None:
        outcome = _run(
            TextInput("Name"),
            [KeyCode.char("h"), KeyCode.char("i"), KeyCode.ENTER],
        )
        assert outcome.is_submitted  # pyright: ignore[reportAttributeAccessIssue]
        assert outcome.value == "hi"  # pyright: ignore[reportAttributeAccessIssue]

    def test_backspace_edits_initial_value(self) -> None:
        outcome = _run(
            TextInput("x").initial("ab"), [KeyCode.BACKSPACE, KeyCode.ENTER]
        )
        assert outcome.value == "a"  # pyright: ignore[reportAttributeAccessIssue]

    def test_editor_runs_with_raw_mode_suspended(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The external editor must run in cooked mode: the round-trip has to
        # happen inside the suspended-raw-mode context.
        events: list[str] = []

        @contextlib.contextmanager
        def fake_suspend() -> Iterator[None]:
            events.append("suspend")
            try:
                yield
            finally:
                events.append("resume")

        def fake_edit(command: str | None, value: str, suffix: str) -> str:
            events.append("edit")
            return f"{value}!"

        monkeypatch.setattr(
            "sparcli.input.text.suspended_raw_mode", fake_suspend
        )
        monkeypatch.setattr("sparcli.input.text.edit_text", fake_edit)
        prompt = TextInput("x").editor()
        result = prompt._edit_value("hi")  # pyright: ignore[reportPrivateUsage]
        assert result == "hi!"
        assert events == ["suspend", "edit", "resume"]

    def test_esc_cancels(self) -> None:
        outcome = _run(TextInput("x"), [KeyCode.ESC])
        assert outcome.is_cancelled  # pyright: ignore[reportAttributeAccessIssue]

    def test_source_is_not_interactive(self) -> None:
        assert ScriptedSource.keys([]).is_interactive() is False

    def test_validation_blocks_until_valid(self) -> None:
        # First Enter fails (empty), then a char, then Enter succeeds.
        outcome = _run(
            TextInput("x").validate(non_empty()),
            [KeyCode.ENTER, KeyCode.char("a"), KeyCode.ENTER],
        )
        assert outcome.value == "a"  # pyright: ignore[reportAttributeAccessIssue]

    def test_min_len_validator_is_enforced(self) -> None:
        outcome = _run(
            TextInput("x").validate(min_len(2)),
            [
                KeyCode.char("a"),
                KeyCode.ENTER,
                KeyCode.char("b"),
                KeyCode.ENTER,
            ],
        )
        assert outcome.value == "ab"  # pyright: ignore[reportAttributeAccessIssue]

    def test_char_filter_rejects_disallowed(self) -> None:
        outcome = _run(
            TextInput("x").char_filter(digits()),
            [KeyCode.char("a"), KeyCode.char("1"), KeyCode.ENTER],
        )
        assert outcome.value == "1"  # pyright: ignore[reportAttributeAccessIssue]

    def test_max_chars_caps_input(self) -> None:
        outcome = _run(
            TextInput("x").max_chars(2),
            [
                KeyCode.char("a"),
                KeyCode.char("b"),
                KeyCode.char("c"),
                KeyCode.ENTER,
            ],
        )
        assert outcome.value == "ab"  # pyright: ignore[reportAttributeAccessIssue]

    def test_tab_accepts_ghost_suggestion(self) -> None:
        outcome = _run(
            TextInput("x").suggestions(["hello"]),
            [KeyCode.char("h"), KeyCode.TAB, KeyCode.ENTER],
        )
        assert outcome.value == "hello"  # pyright: ignore[reportAttributeAccessIssue]

    def test_dropdown_navigates_and_enter_accepts(self) -> None:
        # Type "ap" -> apple/apricot; Down highlights apple; Enter fills it
        # (stays open), the second Enter submits.
        outcome = _run(
            TextInput("x")
            .dropdown()
            .suggestions(["apple", "apricot", "banana"]),
            [
                KeyCode.char("a"),
                KeyCode.char("p"),
                KeyCode.DOWN,
                KeyCode.ENTER,
                KeyCode.ENTER,
            ],
        )
        assert outcome.value == "apple"  # pyright: ignore[reportAttributeAccessIssue]

    def test_fuzzy_suggestions_match_subsequence(self) -> None:
        outcome = _run(
            TextInput("x")
            .dropdown()
            .fuzzy_suggestions()
            .suggestions(["foobar"]),
            [
                KeyCode.char("f"),
                KeyCode.char("b"),
                KeyCode.TAB,
                KeyCode.ENTER,
            ],
        )
        assert outcome.value == "foobar"  # pyright: ignore[reportAttributeAccessIssue]

    def test_history_recall_with_up(self) -> None:
        outcome = _run(
            TextInput("x").history(["first", "second"]),
            [KeyCode.UP, KeyCode.ENTER],
        )
        assert outcome.value == "second"  # pyright: ignore[reportAttributeAccessIssue]

    def test_history_down_after_up_clears(self) -> None:
        outcome = _run(
            TextInput("x").history(["first", "second"]),
            [KeyCode.UP, KeyCode.DOWN, KeyCode.char("z"), KeyCode.ENTER],
        )
        assert outcome.value == "z"  # pyright: ignore[reportAttributeAccessIssue]

    def test_frame_renders_without_a_tty(self) -> None:
        frame = TextInput("Name").initial("hi").frame()
        assert frame.plain().startswith("Name hi")

    def test_frame_shows_placeholder_when_empty(self) -> None:
        frame = TextInput("Name").placeholder("type here").frame()
        assert "type here" in frame.plain()
