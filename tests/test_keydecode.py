"""Tests for the byte-level primitives behind the terminal event source."""

from __future__ import annotations

from sparcli.input.keydecode import (
    CSI_FINAL_MAX,
    CSI_FINAL_MIN,
    CTRL_LETTER_BASE,
    ESC_BYTE,
    decode_modifier,
    poll_ready,
    to_int,
    utf8_continuation_count,
)


class TestDecodeModifier:
    def test_empty_parameter_sets_no_modifier(self) -> None:
        assert decode_modifier("") == (False, False, False)

    def test_garbage_parameter_sets_no_modifier(self) -> None:
        assert decode_modifier("not-a-number") == (False, False, False)

    def test_shift_is_parameter_two(self) -> None:
        assert decode_modifier("2") == (False, False, True)

    def test_alt_is_parameter_three(self) -> None:
        assert decode_modifier("3") == (False, True, False)

    def test_ctrl_is_parameter_five(self) -> None:
        assert decode_modifier("5") == (True, False, False)

    def test_ctrl_shift_is_parameter_six(self) -> None:
        assert decode_modifier("6") == (True, False, True)

    def test_all_three_is_parameter_eight(self) -> None:
        assert decode_modifier("8") == (True, True, True)


class TestToInt:
    def test_digits_parse(self) -> None:
        assert to_int("42") == 42

    def test_empty_string_is_zero(self) -> None:
        assert to_int("") == 0

    def test_non_numeric_is_zero(self) -> None:
        assert to_int("12a") == 0


class TestUtf8ContinuationCount:
    def test_ascii_needs_no_continuation(self) -> None:
        assert utf8_continuation_count(0x41) == 0

    def test_two_byte_lead(self) -> None:
        assert utf8_continuation_count(0xC3) == 1

    def test_three_byte_lead(self) -> None:
        assert utf8_continuation_count(0xE2) == 2

    def test_four_byte_lead(self) -> None:
        assert utf8_continuation_count(0xF0) == 3

    def test_lead_bytes_of_a_real_character(self) -> None:
        # "ä" encodes as two bytes, "…" as three, an emoji as four.
        assert utf8_continuation_count("ä".encode()[0]) == 1
        assert utf8_continuation_count("…".encode()[0]) == 2
        assert utf8_continuation_count("😀".encode()[0]) == 3


class TestPollReady:
    def test_a_closed_descriptor_is_never_ready(self) -> None:
        assert poll_ready(-1, 0.0) is False


class TestByteConstants:
    def test_esc_is_the_escape_byte(self) -> None:
        assert ord("\x1b") == ESC_BYTE

    def test_ctrl_letter_base_maps_control_bytes_to_letters(self) -> None:
        # Ctrl-A arrives as 0x01 and must decode back to "a".
        assert chr(0x01 + CTRL_LETTER_BASE) == "a"
        assert chr(0x1A + CTRL_LETTER_BASE) == "z"

    def test_csi_final_range_covers_the_usual_terminators(self) -> None:
        for final in ("A", "B", "~", "Z"):
            assert CSI_FINAL_MIN <= ord(final) <= CSI_FINAL_MAX
