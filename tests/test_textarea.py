"""Tests for the multi-line textarea prompt."""

from __future__ import annotations

from sparcli.input.event import (
    InputEvent,
    KeyCode,
    KeyPress,
    ScriptedSource,
)
from sparcli.input.textarea import Textarea


def _keys(*presses: KeyPress) -> ScriptedSource:
    """Builds a scripted source from key presses."""
    return ScriptedSource([InputEvent.from_key(press) for press in presses])


class TestTextareaEntry:
    def test_enter_inserts_newline_and_ctrl_d_submits(self) -> None:
        source = _keys(
            KeyPress.new(KeyCode.char("a")),
            KeyPress.new(KeyCode.ENTER),
            KeyPress.new(KeyCode.char("b")),
            KeyPress.ctrl_key("d"),
        )
        outcome = Textarea("Notes").run_with(source)
        assert outcome.is_submitted
        assert outcome.value == "a\nb"

    def test_ctrl_d_submits_full_initial_text(self) -> None:
        source = _keys(KeyPress.ctrl_key("d"))
        outcome = Textarea("Notes").initial("one\ntwo").run_with(source)
        assert outcome.value == "one\ntwo"

    def test_paste_inserts_multiline_text(self) -> None:
        source = ScriptedSource(
            [
                InputEvent.paste("x\ny"),
                InputEvent.from_key(KeyPress.ctrl_key("d")),
            ]
        )
        outcome = Textarea("Notes").run_with(source)
        assert outcome.value == "x\ny"


class TestTextareaCancel:
    def test_esc_cancels(self) -> None:
        outcome = Textarea("Notes").run_with(ScriptedSource.keys([KeyCode.ESC]))
        assert outcome.is_cancelled

    def test_exhaustion_cancels(self) -> None:
        outcome = Textarea("Notes").run_with(ScriptedSource([]))
        assert outcome.is_cancelled


class TestTextareaCursorMovement:
    def test_up_then_type_edits_previous_row(self) -> None:
        source = _keys(
            KeyPress.new(KeyCode.char("a")),
            KeyPress.new(KeyCode.ENTER),
            KeyPress.new(KeyCode.char("b")),
            KeyPress.new(KeyCode.UP),
            KeyPress.new(KeyCode.char("X")),
            KeyPress.ctrl_key("d"),
        )
        outcome = Textarea("Notes").run_with(source)
        # Up from row 1 col 1 lands on row 0 col 1 (after 'a'); X appends there.
        assert outcome.value == "aX\nb"

    def test_home_moves_to_line_start(self) -> None:
        source = _keys(
            KeyPress.new(KeyCode.char("a")),
            KeyPress.new(KeyCode.char("b")),
            KeyPress.new(KeyCode.HOME),
            KeyPress.new(KeyCode.char("Z")),
            KeyPress.ctrl_key("d"),
        )
        outcome = Textarea("Notes").run_with(source)
        assert outcome.value == "Zab"


class TestTextareaEditOps:
    def test_backspace_deletes_previous_char(self) -> None:
        source = _keys(
            KeyPress.new(KeyCode.char("a")),
            KeyPress.new(KeyCode.char("b")),
            KeyPress.new(KeyCode.BACKSPACE),
            KeyPress.ctrl_key("d"),
        )
        outcome = Textarea("Notes").run_with(source)
        assert outcome.value == "a"

    def test_ctrl_u_kills_to_line_start(self) -> None:
        source = _keys(
            KeyPress.new(KeyCode.char("a")),
            KeyPress.new(KeyCode.char("b")),
            KeyPress.ctrl_key("u"),
            KeyPress.ctrl_key("d"),
        )
        outcome = Textarea("Notes").run_with(source)
        assert outcome.value == ""


class TestTextareaFrame:
    def test_frame_renders_headless(self) -> None:
        rendered = Textarea("Notes").initial("a\nb").frame()
        plain = rendered.plain()
        assert "Notes" in plain
        assert rendered.height() == 3
