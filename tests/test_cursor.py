"""Tests for hiding and restoring the terminal cursor around redraws."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sparcli.core import cursor
from sparcli.core.render import Rendered
from sparcli.core.text import Line
from sparcli.output.live import InPlace

if TYPE_CHECKING:
    from collections.abc import Iterator

HIDE = "\x1b[?25l"
SHOW = "\x1b[?25h"


@pytest.fixture(autouse=True)
def reset_cursor() -> Iterator[None]:
    """Resets the module hidden-flag around each test."""
    cursor._hidden = False
    yield
    cursor._hidden = False


def _frame() -> Rendered:
    """Returns a one-line frame for driving the engine."""
    return Rendered([Line.raw("x")])


class TestCursorModule:
    def test_hide_writes_the_escape_once(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cursor.hide()
        cursor.hide()
        assert capsys.readouterr().out == HIDE
        assert cursor.is_hidden()

    def test_show_is_a_no_op_when_not_hidden(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cursor.show()
        assert capsys.readouterr().out == ""

    def test_show_restores_after_hide(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cursor.hide()
        capsys.readouterr()
        cursor.show()
        assert capsys.readouterr().out == SHOW
        assert not cursor.is_hidden()


class TestInPlaceCursor:
    def test_interactive_draw_hides_the_cursor(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        InPlace(interactive=True, silent=False).draw(_frame())
        assert HIDE in capsys.readouterr().out

    def test_second_draw_does_not_hide_again(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        engine = InPlace(interactive=True, silent=False)
        engine.draw(_frame())
        capsys.readouterr()
        engine.draw(_frame())
        assert HIDE not in capsys.readouterr().out

    def test_finish_shows_the_cursor(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        engine = InPlace(interactive=True, silent=False)
        engine.draw(_frame())
        engine.finish()
        assert SHOW in capsys.readouterr().out

    def test_clear_shows_the_cursor(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        engine = InPlace(interactive=True, silent=False)
        engine.draw(_frame())
        capsys.readouterr()
        engine.clear()
        assert SHOW in capsys.readouterr().out

    def test_silent_emits_no_cursor_escapes(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        engine = InPlace.silent()
        engine.draw(_frame())
        engine.finish()
        captured = capsys.readouterr().out
        assert HIDE not in captured
        assert SHOW not in captured

    def test_non_interactive_emits_no_cursor_escapes(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        engine = InPlace(interactive=False, silent=False)
        engine.draw(_frame())
        engine.finish()
        captured = capsys.readouterr().out
        assert HIDE not in captured
        assert SHOW not in captured
