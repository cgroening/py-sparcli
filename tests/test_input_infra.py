"""Tests for the input infrastructure: sources, editor core and helpers."""

from __future__ import annotations

from pathlib import Path

from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line
from sparcli.core.theme import theme
from sparcli.input.event import (
    EventKind,
    InputEvent,
    KeyCode,
    KeyKind,
    KeyPress,
    ScriptedSource,
)
from sparcli.input.field import (
    error_line,
    field_line,
    placeholder_line,
    value_line,
)
from sparcli.input.guard import TerminalGuard
from sparcli.input.history import History
from sparcli.input.line_edit import LineEditor
from sparcli.input.outcome import Outcome, OutcomeKind
from sparcli.input.prompt import Flow, run_prompt
from sparcli.input.shortcut import Shortcut, find, hint_line, key_name
from sparcli.input.validate import (
    alnum,
    alpha,
    decimal,
    digits,
    min_len,
    no_space,
    non_empty,
)


class State:
    """A tiny mutable prompt state for driving ``run_prompt``."""

    def __init__(self) -> None:
        self.editor = LineEditor()


def _render(state: State, final: bool) -> Rendered:
    """Renders the state as a single plain line."""
    return Rendered([Line.raw(state.editor.value())])


def _handle(state: State, event: InputEvent) -> Flow[str]:
    """Types characters, submits on Enter and cancels on Esc."""
    if event.kind is not EventKind.KEY or event.key is None:
        return Flow.cont()
    code = event.key.code
    if code == KeyCode.ENTER:
        return Flow.submit(state.editor.value())
    if code == KeyCode.ESC:
        return Flow.cancel()
    if code.kind is KeyKind.CHAR and code.ch is not None:
        state.editor.insert_char(code.ch)
    return Flow.cont()


class TestOutcome:
    def test_submitted_exposes_value(self) -> None:
        outcome = Outcome.submitted("hi")
        assert outcome.is_submitted
        assert outcome.value == "hi"
        assert outcome.kind is OutcomeKind.SUBMITTED

    def test_cancelled_has_no_value(self) -> None:
        outcome: Outcome[str] = Outcome.cancelled()
        assert outcome.is_cancelled
        assert outcome.submitted_or("x") == "x"

    def test_shortcut_carries_id(self) -> None:
        outcome: Outcome[str] = Outcome.shortcut(7)
        assert outcome.is_shortcut
        assert outcome.shortcut_id == 7

    def test_value_on_non_submission_raises(self) -> None:
        outcome: Outcome[str] = Outcome.cancelled()
        raised = False
        try:
            _ = outcome.value
        except Exception:
            raised = True
        assert raised

    def test_matches_on_kind(self) -> None:
        match Outcome.submitted(1):
            case Outcome(OutcomeKind.SUBMITTED):
                matched = True
            case _:
                matched = False
        assert matched


class TestScriptedSource:
    def test_replays_then_cancels(self) -> None:
        source = ScriptedSource.keys([KeyCode.char("a")])
        first = source.next_event()
        assert first.key == KeyPress.new(KeyCode.char("a"))
        second = source.next_event()
        assert second.key == KeyPress.new(KeyCode.ESC)

    def test_is_not_interactive(self) -> None:
        assert ScriptedSource([]).is_interactive() is False

    def test_accepts_raw_events(self) -> None:
        source = ScriptedSource([InputEvent.paste("hi")])
        event = source.next_event()
        assert event.kind is EventKind.PASTE
        assert event.text == "hi"


class TestRunPrompt:
    def test_submits_typed_value(self) -> None:
        source = ScriptedSource.keys(
            [KeyCode.char("h"), KeyCode.char("i"), KeyCode.ENTER]
        )
        outcome = run_prompt(source, State(), _render, _handle)
        assert outcome.is_submitted
        assert outcome.value == "hi"

    def test_cancels_on_esc(self) -> None:
        source = ScriptedSource.keys([KeyCode.char("x"), KeyCode.ESC])
        outcome = run_prompt(source, State(), _render, _handle)
        assert outcome.is_cancelled

    def test_cancels_on_exhaustion(self) -> None:
        outcome = run_prompt(ScriptedSource([]), State(), _render, _handle)
        assert outcome.is_cancelled

    def test_shortcut_flow_returns_shortcut(self) -> None:
        def handle(state: State, event: InputEvent) -> Flow[str]:
            return Flow.shortcut(3)

        outcome = run_prompt(
            ScriptedSource.keys([KeyCode.char("a")]), State(), _render, handle
        )
        assert outcome.is_shortcut
        assert outcome.shortcut_id == 3


class TestKeyPress:
    def test_ctrl_helper_matches(self) -> None:
        assert KeyPress.ctrl_key("c").is_ctrl("c")
        assert not KeyPress.new(KeyCode.char("c")).is_ctrl("c")

    def test_key_codes_compare_by_value(self) -> None:
        assert KeyCode.char("a") == KeyCode.char("a")
        assert KeyCode.function(2) != KeyCode.function(3)


class TestLineEditor:
    def test_insert_and_value(self) -> None:
        editor = LineEditor()
        editor.insert_char("h")
        editor.insert_char("i")
        assert editor.value() == "hi"
        assert editor.cursor == 2

    def test_backspace_removes_previous(self) -> None:
        editor = LineEditor("ab")
        editor.backspace()
        assert editor.value() == "a"

    def test_selection_is_replaced_on_insert(self) -> None:
        editor = LineEditor("hello")
        editor.move_home(select=False)
        editor.move_right(select=True)
        editor.move_right(select=True)
        editor.insert_char("X")
        assert editor.value() == "Xllo"

    def test_delete_word_back(self) -> None:
        editor = LineEditor("foo bar")
        editor.delete_word_back()
        assert editor.value() == "foo "

    def test_kill_to_line_start_and_end(self) -> None:
        editor = LineEditor("hello")
        editor.move_home(select=False)
        editor.move_right(select=False)
        editor.move_right(select=False)
        editor.kill_to_line_end()
        assert editor.value() == "he"
        editor.kill_to_line_start()
        assert editor.value() == ""

    def test_single_line_converts_pasted_newlines(self) -> None:
        editor = LineEditor()
        editor.insert_str("a\nb")
        assert editor.value() == "a b"

    def test_multiline_navigates_between_rows(self) -> None:
        editor = LineEditor("ab\ncd", multiline=True)
        editor.move_home(select=False)
        editor.move_up(select=False)
        assert editor.cursor_line_col() == (0, 0)

    def test_up_down_preserve_column(self) -> None:
        editor = LineEditor("abc\nde\nfghi", multiline=True)
        # Caret at end (line 2, col 4); moving up lands on shorter middle line.
        editor.move_up(select=False)
        assert editor.cursor_line_col() == (1, 2)
        editor.move_up(select=False)
        assert editor.cursor_line_col() == (0, 2)

    def test_multiline_newline_inserts(self) -> None:
        editor = LineEditor(multiline=True)
        editor.insert_str("ab")
        editor.insert_newline()
        editor.insert_str("cd")
        assert editor.lines() == ["ab", "cd"]

    def test_cut_and_paste_round_trip(self) -> None:
        editor = LineEditor("hello")
        editor.select_all()
        editor.cut()
        assert editor.value() == ""
        editor.paste()
        assert editor.value() == "hello"


class TestField:
    def test_field_line_includes_prompt_and_value(self) -> None:
        line = field_line("Name", "ab", 2, Style.new(), theme())
        assert line.plain().startswith("Name ab")

    def test_cursor_in_middle_keeps_all_text(self) -> None:
        line = field_line("", "abc", 1, Style.new(), theme())
        assert line.plain() == "abc"

    def test_value_line_has_no_trailing_cursor(self) -> None:
        line = value_line("Name", "ab", Style.new(), theme())
        assert line.plain() == "Name ab"

    def test_placeholder_line_shows_placeholder(self) -> None:
        line = placeholder_line("Name", "type here", theme())
        assert "type here" in line.plain()

    def test_error_line_is_indented(self) -> None:
        assert error_line("bad", theme()).plain() == "  bad"


class TestHistory:
    def test_add_skips_blank_and_duplicates(self) -> None:
        history = History()
        history.add("a")
        history.add("a")
        history.add("   ")
        history.add("b")
        assert history.entries() == ["a", "b"]

    def test_add_respects_max(self) -> None:
        history = History().max_entries(2)
        history.add("a")
        history.add("b")
        history.add("c")
        assert history.entries() == ["b", "c"]

    def test_keep_duplicates_retains_repeats(self) -> None:
        history = History().keep_duplicates()
        history.add("a")
        history.add("a")
        assert history.entries() == ["a", "a"]

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        source = History()
        source._path = tmp_path / "app" / "history"  # pyright: ignore[reportPrivateUsage]
        source.add("one")
        source.add("two")
        source.save()

        loaded = History()
        loaded._path = tmp_path / "app" / "history"  # pyright: ignore[reportPrivateUsage]
        loaded.load()
        assert loaded.entries() == ["one", "two"]

    def test_load_splits_only_on_newlines(self, tmp_path: Path) -> None:
        # Loading splits like Rust's str::lines (on newlines only), so an entry
        # containing an exotic line separator is not wrongly split in two.
        path = tmp_path / "history"
        path.write_text("a\x85b\nc", encoding="utf-8")
        history = History()
        history._path = path  # pyright: ignore[reportPrivateUsage]
        history.load()
        assert history.entries() == ["a\x85b", "c"]

    def test_save_leaves_no_temp_files(self, tmp_path: Path) -> None:
        # The atomic write renames its temp file over the target, so no
        # leftover temp files remain in the directory.
        history = History()
        history._path = tmp_path / "history"  # pyright: ignore[reportPrivateUsage]
        history.add("one")
        history.save()
        assert [p.name for p in tmp_path.iterdir()] == ["history"]

    def test_save_replaces_existing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "history"
        path.write_text("stale\n", encoding="utf-8")
        history = History()
        history._path = path  # pyright: ignore[reportPrivateUsage]
        history.add("fresh")
        history.save()
        assert path.read_text(encoding="utf-8") == "fresh"


class TestTerminalGuard:
    def test_degrades_to_a_no_op_off_a_terminal(self) -> None:
        # Off a real terminal ``termios.tcgetattr`` raises ``termios.error``
        # (not an ``OSError``); the guard must still degrade to a harmless
        # no-op rather than propagating it out of the ``with`` block.
        with TerminalGuard():
            pass


class TestShortcut:
    def test_find_matches_bound_key(self) -> None:
        shortcuts = [Shortcut(KeyPress.ctrl_key("s"), 1, "save")]
        assert find(KeyPress.ctrl_key("s"), shortcuts) == 1
        assert find(KeyPress.ctrl_key("x"), shortcuts) is None

    def test_key_name_includes_modifiers(self) -> None:
        assert key_name(KeyPress.ctrl_key("s")) == "Ctrl-S"
        assert key_name(KeyPress.new(KeyCode.function(2))) == "F2"
        assert key_name(KeyPress.new(KeyCode.BACK_TAB)) == "Shift-Tab"
        assert key_name(KeyPress.new(KeyCode.PAGE_UP)) == "PgUp"

    def test_hint_line_lists_shortcuts(self) -> None:
        shortcuts = [
            Shortcut(KeyPress.ctrl_key("s"), 1, "save"),
            Shortcut(KeyPress.new(KeyCode.ESC), 2, "cancel"),
        ]
        plain = hint_line(shortcuts).plain()
        assert "Ctrl-S save" in plain
        assert "Esc cancel" in plain


class TestValidate:
    def test_non_empty_rejects_blank(self) -> None:
        assert non_empty()("   ") == "must not be empty"
        assert non_empty()("x") is None

    def test_min_len_counts_characters(self) -> None:
        assert min_len(3)("ab") is not None
        assert min_len(3)("abc") is None

    def test_digit_filter_accepts_only_digits(self) -> None:
        assert digits()("5")
        assert not digits()("a")

    def test_decimal_filter_accepts_sign_and_point(self) -> None:
        assert decimal()("-")
        assert decimal()(".")
        assert not decimal()("a")

    def test_alpha_and_alnum(self) -> None:
        assert alpha()("a")
        assert not alpha()("1")
        assert alnum()("1")
        assert not alnum()("-")

    def test_no_space_rejects_whitespace(self) -> None:
        assert no_space()("a")
        assert not no_space()(" ")
