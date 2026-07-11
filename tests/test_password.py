"""Tests for the masked :class:`PasswordInput` prompt, driven headlessly."""

from __future__ import annotations

from sparcli.input.event import (
    InputEvent,
    KeyCode,
    KeyPress,
    ScriptedSource,
)
from sparcli.input.password import PasswordInput
from sparcli.input.validate import min_len, no_space


def _run(prompt: PasswordInput, codes: list[KeyCode]) -> object:
    """Drives ``prompt`` with a scripted key sequence and returns the outcome."""
    return prompt.run_with(ScriptedSource.keys(codes))


class TestPasswordInput:
    def test_types_and_submits_password(self) -> None:
        outcome = _run(
            PasswordInput("pw"),
            [
                KeyCode.char("s"),
                KeyCode.char("e"),
                KeyCode.char("c"),
                KeyCode.ENTER,
            ],
        )
        assert outcome.is_submitted  # pyright: ignore[reportAttributeAccessIssue]
        assert outcome.value == "sec"  # pyright: ignore[reportAttributeAccessIssue]

    def test_esc_cancels(self) -> None:
        outcome = _run(PasswordInput("pw"), [KeyCode.ESC])
        assert outcome.is_cancelled  # pyright: ignore[reportAttributeAccessIssue]

    def test_value_is_masked_in_the_frame(self) -> None:
        frame = PasswordInput("pw").initial("abc").frame()
        plain = frame.plain()
        assert "***" in plain
        assert "abc" not in plain

    def test_empty_mask_hides_the_length(self) -> None:
        frame = PasswordInput("pw").mask("").initial("abc").frame()
        plain = frame.plain()
        assert "*" not in plain
        assert "abc" not in plain

    def test_custom_mask_glyph_is_used(self) -> None:
        frame = PasswordInput("pw").mask("#").initial("ab").frame()
        assert "##" in frame.plain()

    def test_validation_blocks_until_valid(self) -> None:
        outcome = _run(
            PasswordInput("pw").validate(min_len(2)),
            [
                KeyCode.char("a"),
                KeyCode.ENTER,
                KeyCode.char("b"),
                KeyCode.ENTER,
            ],
        )
        assert outcome.value == "ab"  # pyright: ignore[reportAttributeAccessIssue]

    def test_char_filter_rejects_whitespace(self) -> None:
        outcome = _run(
            PasswordInput("pw").char_filter(no_space()),
            [
                KeyCode.char("a"),
                KeyCode.char(" "),
                KeyCode.char("b"),
                KeyCode.ENTER,
            ],
        )
        assert outcome.value == "ab"  # pyright: ignore[reportAttributeAccessIssue]

    def test_max_chars_caps_input(self) -> None:
        outcome = _run(
            PasswordInput("pw").max_chars(2),
            [
                KeyCode.char("a"),
                KeyCode.char("b"),
                KeyCode.char("c"),
                KeyCode.ENTER,
            ],
        )
        assert outcome.value == "ab"  # pyright: ignore[reportAttributeAccessIssue]

    def test_ctrl_u_kills_to_line_start(self) -> None:
        source = ScriptedSource(
            [
                InputEvent.from_key(KeyPress.new(KeyCode.char("a"))),
                InputEvent.from_key(KeyPress.new(KeyCode.char("b"))),
                InputEvent.from_key(KeyPress.ctrl_key("u")),
                InputEvent.from_key(KeyPress.new(KeyCode.char("c"))),
                InputEvent.from_key(KeyPress.new(KeyCode.ENTER)),
            ]
        )
        outcome = PasswordInput("pw").run_with(source)
        assert outcome.value == "c"  # pyright: ignore[reportAttributeAccessIssue]

    def test_source_is_not_interactive(self) -> None:
        assert ScriptedSource.keys([]).is_interactive() is False
