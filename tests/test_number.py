"""Tests for the numeric input prompt and its calculator evaluator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sparcli.input.calc import (
    CalcError,
    CalcErrorKind,
    evaluate,
    parse_number,
)
from sparcli.input.event import (
    InputEvent,
    KeyCode,
    KeyPress,
    ScriptedSource,
)
from sparcli.input.number import NumberInput

if TYPE_CHECKING:
    from sparcli.input.outcome import Outcome


def _run(prompt: NumberInput, codes: list[KeyCode]) -> Outcome[float]:
    """Drives ``prompt`` headlessly with a scripted key sequence."""
    return prompt.run_with(ScriptedSource.keys(codes))


class TestCalc:
    def test_evaluates_with_precedence(self) -> None:
        assert evaluate("2 + 3 * 4") == 14.0

    def test_parentheses_override_precedence(self) -> None:
        assert evaluate("(2 + 3) * 4") == 20.0

    def test_unary_minus(self) -> None:
        assert evaluate("-3 + 5") == 2.0

    def test_comma_is_a_decimal_separator(self) -> None:
        assert evaluate("1,5 + 1,5") == 3.0

    def test_division_by_zero_raises(self) -> None:
        with pytest.raises(CalcError) as info:
            evaluate("1 / 0")
        assert info.value.kind is CalcErrorKind.DIVISION_BY_ZERO

    def test_trailing_input_raises(self) -> None:
        with pytest.raises(CalcError) as info:
            evaluate("1 2")
        assert info.value.kind is CalcErrorKind.TRAILING_INPUT

    def test_missing_parenthesis_raises(self) -> None:
        with pytest.raises(CalcError) as info:
            evaluate("(1 + 2")
        assert info.value.kind is CalcErrorKind.MISSING_PARENTHESIS

    def test_parse_number_accepts_comma_and_trims(self) -> None:
        assert parse_number("  3,5 ") == 3.5

    def test_parse_number_rejects_empty(self) -> None:
        with pytest.raises(CalcError) as info:
            parse_number("")
        assert info.value.kind is CalcErrorKind.NOT_A_NUMBER


class TestNumberInput:
    def test_types_and_submits_number(self) -> None:
        outcome = _run(
            NumberInput("n"),
            [KeyCode.char("4"), KeyCode.char("2"), KeyCode.ENTER],
        )
        assert outcome.is_submitted
        assert outcome.value == 42.0

    def test_value_is_clamped_to_range(self) -> None:
        outcome = _run(
            NumberInput("n").range(0.0, 10.0),
            [KeyCode.char("9"), KeyCode.char("9"), KeyCode.ENTER],
        )
        assert outcome.value == 10.0

    def test_lower_bound_clamps(self) -> None:
        outcome = _run(
            NumberInput("n").range(0.0, 10.0).initial(5.0).step(20.0),
            [KeyCode.DOWN, KeyCode.ENTER],
        )
        assert outcome.value == 0.0

    def test_up_arrow_adds_step(self) -> None:
        outcome = _run(
            NumberInput("n").initial(5.0).step(2.0),
            [KeyCode.UP, KeyCode.ENTER],
        )
        assert outcome.value == 7.0

    def test_down_arrow_subtracts_step(self) -> None:
        outcome = _run(
            NumberInput("n").initial(5.0),
            [KeyCode.DOWN, KeyCode.ENTER],
        )
        assert outcome.value == 4.0

    def test_decimals_format_step_adjustment(self) -> None:
        prompt = NumberInput("n").initial(1.0).step(0.5).decimals(2)
        outcome = _run(prompt, [KeyCode.UP, KeyCode.ENTER])
        assert outcome.value == 1.5
        # The field formats the initial value with the configured decimals.
        assert "1.00" in prompt.frame().plain()

    def test_negative_decimals_are_clamped_to_zero(self) -> None:
        # A negative decimals setting would break str formatting; it is
        # clamped so the field renders without raising.
        prompt = NumberInput("n").initial(1.0).decimals(-3)
        assert "1" in prompt.frame().plain()
        prompt_kw = NumberInput("n", initial=2.0, decimals=-1)
        assert "2" in prompt_kw.frame().plain()

    def test_non_calculator_rejects_operators(self) -> None:
        # '+' is not accepted without calculator mode, so only '2' is typed.
        outcome = _run(
            NumberInput("n"),
            [KeyCode.char("2"), KeyCode.char("+"), KeyCode.ENTER],
        )
        assert outcome.value == 2.0

    def test_calculator_evaluates_expression(self) -> None:
        outcome = _run(
            NumberInput("n").calculator(),
            [
                KeyCode.char("2"),
                KeyCode.char("+"),
                KeyCode.char("3"),
                KeyCode.char("*"),
                KeyCode.char("4"),
                KeyCode.ENTER,
            ],
        )
        assert outcome.value == 14.0

    def test_calculator_evaluates_parentheses(self) -> None:
        # Clear the default "0" before an expression that starts with "(".
        codes = [KeyCode.BACKSPACE]
        codes.extend(KeyCode.char(ch) for ch in "(2+3)*4")
        codes.append(KeyCode.ENTER)
        outcome = _run(NumberInput("n").calculator(), codes)
        assert outcome.value == 20.0

    def test_calculator_accepts_comma_decimal(self) -> None:
        codes = [KeyCode.char(ch) for ch in "1,5+1,5"]
        codes.append(KeyCode.ENTER)
        outcome = _run(NumberInput("n").calculator(), codes)
        assert outcome.value == 3.0

    def test_division_by_zero_is_surfaced_without_crashing(self) -> None:
        # Bad expression keeps the prompt open; exhaustion then cancels it.
        codes = [KeyCode.char(ch) for ch in "1/0"]
        codes.append(KeyCode.ENTER)
        outcome = _run(NumberInput("n").calculator(), codes)
        assert outcome.is_cancelled

    def test_trailing_input_is_surfaced_without_crashing(self) -> None:
        codes = [KeyCode.char("1"), KeyCode.char(" "), KeyCode.char("2")]
        codes.append(KeyCode.ENTER)
        outcome = _run(NumberInput("n").calculator(), codes)
        assert outcome.is_cancelled

    def test_esc_cancels(self) -> None:
        outcome = _run(NumberInput("n"), [KeyCode.ESC])
        assert outcome.is_cancelled

    def test_ctrl_u_clears_the_field(self) -> None:
        source = ScriptedSource(
            [
                InputEvent.from_key(KeyPress.new(KeyCode.char("7"))),
                InputEvent.from_key(KeyPress.new(KeyCode.char("5"))),
                InputEvent.from_key(KeyPress.ctrl_key("u")),
                InputEvent.from_key(KeyPress.new(KeyCode.char("3"))),
                InputEvent.from_key(KeyPress.new(KeyCode.ENTER)),
            ]
        )
        outcome = NumberInput("n").initial(9.0).run_with(source)
        assert outcome.value == 3.0

    def test_frame_renders_headless(self) -> None:
        rendered = NumberInput("Age").initial(21.0).frame()
        assert "Age" in rendered.plain()
        assert "21" in rendered.plain()
