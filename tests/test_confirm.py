"""Tests for the yes/no confirmation prompt."""

from __future__ import annotations

from sparcli.input.confirm import Confirm
from sparcli.input.event import (
    InputEvent,
    KeyCode,
    KeyPress,
    ScriptedSource,
)
from sparcli.input.outcome import Outcome
from sparcli.input.shortcut import Shortcut


def _run(prompt: Confirm, codes: list[KeyCode]) -> Outcome[bool]:
    """Drives ``prompt`` headlessly with a scripted key sequence."""
    return prompt.run_with(ScriptedSource.keys(codes))


class TestConfirm:
    def test_y_submits_true(self) -> None:
        outcome = _run(Confirm("ok?"), [KeyCode.char("y")])
        assert outcome.value is True

    def test_uppercase_y_submits_true(self) -> None:
        outcome = _run(Confirm("ok?"), [KeyCode.char("Y")])
        assert outcome.value is True

    def test_n_submits_false(self) -> None:
        outcome = _run(Confirm("ok?").default_yes(), [KeyCode.char("n")])
        assert outcome.value is False

    def test_enter_uses_default_no(self) -> None:
        outcome = _run(Confirm("ok?"), [KeyCode.ENTER])
        assert outcome.value is False

    def test_enter_uses_default_yes(self) -> None:
        outcome = _run(Confirm("ok?").default_yes(), [KeyCode.ENTER])
        assert outcome.value is True

    def test_arrow_toggles_selection(self) -> None:
        outcome = _run(
            Confirm("ok?").default_yes(), [KeyCode.LEFT, KeyCode.ENTER]
        )
        assert outcome.value is False

    def test_tab_toggles_selection(self) -> None:
        outcome = _run(Confirm("ok?"), [KeyCode.TAB, KeyCode.ENTER])
        assert outcome.value is True

    def test_l_and_h_toggle_selection(self) -> None:
        outcome = _run(
            Confirm("ok?"),
            [KeyCode.char("l"), KeyCode.char("h"), KeyCode.ENTER],
        )
        assert outcome.value is False

    def test_esc_cancels(self) -> None:
        outcome = _run(Confirm("ok?"), [KeyCode.ESC])
        assert outcome.is_cancelled

    def test_ctrl_c_cancels(self) -> None:
        source = ScriptedSource([InputEvent.from_key(KeyPress.ctrl_key("c"))])
        outcome = Confirm("ok?").run_with(source)
        assert outcome.is_cancelled

    def test_registered_shortcut_ends_with_its_id(self) -> None:
        shortcut = Shortcut(KeyPress.ctrl_key("r"), 3, "reset")
        source = ScriptedSource([InputEvent.from_key(KeyPress.ctrl_key("r"))])
        outcome = Confirm("ok?").shortcuts([shortcut]).run_with(source)
        assert outcome.is_shortcut
        assert outcome.shortcut_id == 3

    def test_help_overlay_opens_and_any_key_closes(self) -> None:
        shortcut = Shortcut(KeyPress.ctrl_key("r"), 3, "reset")
        prompt = Confirm("ok?").shortcuts([shortcut])
        # '?' opens help; the next key closes it; then Enter submits default.
        outcome = _run(
            prompt, [KeyCode.char("?"), KeyCode.char("x"), KeyCode.ENTER]
        )
        assert outcome.value is False

    def test_labels_appear_in_frame(self) -> None:
        rendered = Confirm("Proceed?").labels("Go", "Stop").frame()
        plain = rendered.plain()
        assert "Proceed?" in plain
        assert "Go" in plain
        assert "Stop" in plain

    def test_frame_shows_footer_hint_with_shortcuts(self) -> None:
        shortcut = Shortcut(KeyPress.ctrl_key("r"), 3, "reset")
        rendered = Confirm("ok?").shortcuts([shortcut]).frame()
        assert "reset" in rendered.plain()
