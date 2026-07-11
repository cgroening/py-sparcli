"""
sparcli.input.calc
==================

Defines the calculator-mode expression evaluator behind ``NumberInput``.

:func:`evaluate` is a small recursive-descent parser for the four arithmetic
operators, parentheses and unary minus, with the usual precedence.
:func:`parse_number` reads a single number for the plain (non-calculator)
submit path. Both accept ``,`` or ``.`` as the decimal separator and report
failures through :class:`CalcError`, whose message becomes the prompt's error
line. This module is an implementation detail, not part of the public API.
"""

from __future__ import annotations

import enum


class CalcErrorKind(enum.Enum):
    """The reason a numeric expression could not be evaluated."""

    NOT_A_NUMBER = "not a number"
    INVALID_NUMBER = "invalid number"
    DIVISION_BY_ZERO = "division by zero"
    MISSING_PARENTHESIS = "missing closing parenthesis"
    TRAILING_INPUT = "unexpected trailing input"


class CalcError(Exception):
    """
    Raised when parsing or evaluating a numeric expression fails.

    Attributes
    ----------
    kind : CalcErrorKind
        Which failure occurred; its value is the human-readable message.
    """

    def __init__(self, kind: CalcErrorKind) -> None:
        super().__init__(kind.value)
        self.kind = kind


def parse_number(text: str) -> float:
    """
    Parses a single number, accepting ``,`` or ``.`` as the separator.

    Parameters
    ----------
    text : str
        The raw field text; surrounding whitespace is ignored.

    Returns
    -------
    float
        The parsed value.

    Raises
    ------
    CalcError
        With :attr:`CalcErrorKind.NOT_A_NUMBER` if ``text`` is empty or not a
        valid number.

    Examples
    --------
    >>> parse_number("3,5")
    3.5
    """
    normalized = text.strip().replace(",", ".")
    if not normalized:
        raise CalcError(CalcErrorKind.NOT_A_NUMBER)
    try:
        return float(normalized)
    except ValueError:
        raise CalcError(CalcErrorKind.NOT_A_NUMBER) from None


def evaluate(expr: str) -> float:
    """
    Evaluates an arithmetic expression with ``+ - * / ( )``.

    Accepts ``,`` or ``.`` as the decimal separator and honours the usual
    operator precedence and unary minus.

    Parameters
    ----------
    expr : str
        The expression to evaluate.

    Returns
    -------
    float
        The value of the expression.

    Raises
    ------
    CalcError
        On malformed input or division by zero.

    Examples
    --------
    >>> evaluate("2 + 3 * 4")
    14.0
    >>> evaluate("(2 + 3) * 4")
    20.0
    """
    parser = _Parser(expr.replace(",", "."))
    value = parser.expression()
    parser.skip_spaces()
    if not parser.at_end():
        raise CalcError(CalcErrorKind.TRAILING_INPUT)
    return value


class _Parser:
    """A minimal recursive-descent arithmetic parser over a character list."""

    __slots__ = ("_chars", "_pos")

    def __init__(self, text: str) -> None:
        self._chars: list[str] = list(text)
        self._pos: int = 0

    def expression(self) -> float:
        """Parses ``term (('+'|'-') term)*``."""
        value = self.term()
        while True:
            self.skip_spaces()
            operator = self._peek()
            if operator == "+":
                self._pos += 1
                value += self.term()
            elif operator == "-":
                self._pos += 1
                value -= self.term()
            else:
                return value

    def term(self) -> float:
        """Parses ``factor (('*'|'/') factor)*``."""
        value = self.factor()
        while True:
            self.skip_spaces()
            operator = self._peek()
            if operator == "*":
                self._pos += 1
                value *= self.factor()
            elif operator == "/":
                self._pos += 1
                value = self._divide(value)
            else:
                return value

    def factor(self) -> float:
        """Parses a number, a parenthesized expression or a unary minus."""
        self.skip_spaces()
        char = self._peek()
        if char == "(":
            return self._grouped()
        if char == "-":
            self._pos += 1
            return -self.factor()
        return self._number()

    def skip_spaces(self) -> None:
        """Advances past any run of spaces."""
        while self._peek() == " ":
            self._pos += 1

    def at_end(self) -> bool:
        """Returns whether the whole input has been consumed."""
        return self._pos >= len(self._chars)

    def _divide(self, value: float) -> float:
        """Consumes the divisor factor and divides, guarding against zero."""
        divisor = self.factor()
        if divisor == 0.0:
            raise CalcError(CalcErrorKind.DIVISION_BY_ZERO)
        return value / divisor

    def _grouped(self) -> float:
        """Parses a parenthesized subexpression, requiring a closing ``)``."""
        self._pos += 1
        value = self.expression()
        self.skip_spaces()
        if self._peek() != ")":
            raise CalcError(CalcErrorKind.MISSING_PARENTHESIS)
        self._pos += 1
        return value

    def _number(self) -> float:
        """Parses a decimal number literal (digits and a decimal point)."""
        start = self._pos
        while _is_number_char(self._peek()):
            self._pos += 1
        text = "".join(self._chars[start : self._pos])
        try:
            return float(text)
        except ValueError:
            raise CalcError(CalcErrorKind.INVALID_NUMBER) from None

    def _peek(self) -> str | None:
        """Returns the current character without consuming it."""
        if self._pos >= len(self._chars):
            return None
        return self._chars[self._pos]


def _is_number_char(char: str | None) -> bool:
    """Returns whether ``char`` may appear inside a number literal."""
    return char is not None and (
        char.isascii() and char.isdigit() or char == "."
    )
