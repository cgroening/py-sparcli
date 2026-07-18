"""Tests for the collaborators the input prompts are composed from.

``SelectionCursor``, ``Completion`` and ``HistoryRecall`` were extracted from
the prompts so each concern could be tested on its own; these are those tests.
"""

from __future__ import annotations

from sparcli.core.theme import theme
from sparcli.input.completion import MAX_DROPDOWN, Completion, MatchMode
from sparcli.input.outcome import Outcome
from sparcli.input.recall import HistoryRecall
from sparcli.input.selection import (
    SelectionCursor,
    checked_indices,
    first_index,
)


class _State:
    """A minimal scrollable state for the cursor tests."""

    def __init__(self, cursor: int = 0, offset: int = 0) -> None:
        self.cursor = cursor
        self.offset = offset


class TestSelectionCursor:
    def test_moving_down_advances_the_cursor(self) -> None:
        state = _State()
        SelectionCursor(5).move(state, 1, 4)
        assert state.cursor == 1

    def test_cycling_wraps_past_the_end(self) -> None:
        state = _State(cursor=3)
        SelectionCursor(5).move(state, 1, 4)
        assert state.cursor == 0

    def test_cycling_wraps_before_the_start(self) -> None:
        state = _State(cursor=0)
        SelectionCursor(5).move(state, -1, 4)
        assert state.cursor == 3

    def test_clamping_stops_at_the_end(self) -> None:
        state = _State(cursor=3)
        SelectionCursor(5, cycle=False).move(state, 1, 4)
        assert state.cursor == 3

    def test_clamping_stops_at_the_start(self) -> None:
        state = _State(cursor=0)
        SelectionCursor(5, cycle=False).move(state, -1, 4)
        assert state.cursor == 0

    def test_an_empty_list_leaves_the_cursor_alone(self) -> None:
        state = _State(cursor=0)
        SelectionCursor(5).move(state, 1, 0)
        assert state.cursor == 0

    def test_the_offset_follows_the_cursor_downwards(self) -> None:
        state = _State()
        cursor = SelectionCursor(3)
        cursor.set(state, 5)
        assert state.offset == 3

    def test_the_offset_follows_the_cursor_upwards(self) -> None:
        state = _State(cursor=5, offset=3)
        SelectionCursor(3).set(state, 1)
        assert state.offset == 1

    def test_the_offset_stays_put_inside_the_window(self) -> None:
        state = _State(cursor=1, offset=0)
        SelectionCursor(5).set(state, 2)
        assert state.offset == 0

    def test_a_page_jump_scrolls_the_window(self) -> None:
        state = _State()
        cursor = SelectionCursor(4)
        cursor.move(state, cursor.max_visible, 20)
        assert state.cursor == 4
        assert state.offset == 1

    def test_max_visible_is_at_least_one(self) -> None:
        assert SelectionCursor(0).max_visible == 1

    def test_opening_offset_shows_the_initial_cursor(self) -> None:
        assert SelectionCursor(3).opening_offset(0) == 0
        assert SelectionCursor(3).opening_offset(5) == 3


class TestCheckedIndices:
    def test_only_checked_positions_are_returned(self) -> None:
        assert checked_indices([False, True, False, True]) == [1, 3]

    def test_nothing_checked_yields_nothing(self) -> None:
        assert checked_indices([False, False]) == []

    def test_an_empty_list_yields_nothing(self) -> None:
        assert checked_indices([]) == []


class TestFirstIndex:
    def test_a_submitted_list_reduces_to_its_first_entry(self) -> None:
        assert first_index(Outcome.submitted([2, 5])).value == 2

    def test_an_empty_submission_becomes_a_cancellation(self) -> None:
        assert first_index(Outcome.submitted([])).is_cancelled

    def test_a_cancellation_stays_cancelled(self) -> None:
        assert first_index(Outcome.cancelled()).is_cancelled

    def test_a_shortcut_keeps_its_id(self) -> None:
        outcome = first_index(Outcome.shortcut(7))
        assert outcome.is_shortcut
        assert outcome.shortcut_id == 7


class TestCompletion:
    def test_prefix_matching_finds_the_candidates(self) -> None:
        completion = Completion(["apple", "apricot", "banana"])
        assert completion.matches("ap") == [0, 1]

    def test_matching_is_case_insensitive(self) -> None:
        assert Completion(["Apple"]).matches("ap") == [0]

    def test_an_empty_value_matches_nothing(self) -> None:
        assert Completion(["apple"]).matches("") == []

    def test_subsequence_matching_is_looser(self) -> None:
        completion = Completion(["foobar"], match_mode=MatchMode.SUBSEQUENCE)
        assert completion.matches("fb") == [0]

    def test_subsequence_respects_the_order(self) -> None:
        completion = Completion(["foobar"], match_mode=MatchMode.SUBSEQUENCE)
        assert completion.matches("bf") == []

    def test_ghost_returns_the_missing_suffix(self) -> None:
        assert Completion(["hello"]).ghost("he") == "llo"

    def test_ghost_is_none_without_a_candidate(self) -> None:
        assert Completion(["hello"]).ghost("xy") is None

    def test_ghost_is_none_for_an_exact_match(self) -> None:
        assert Completion(["hello"]).ghost("hello") is None

    def test_ghost_is_none_for_an_empty_value(self) -> None:
        assert Completion(["hello"]).ghost("") is None

    def test_accept_appends_the_ghost_in_inline_mode(self) -> None:
        assert Completion(["hello"]).accept("he", None) == "hello"

    def test_accept_returns_none_when_nothing_completes(self) -> None:
        assert Completion(["hello"]).accept("xy", None) is None

    def test_accept_takes_the_highlighted_row_in_dropdown_mode(self) -> None:
        completion = Completion(["apple", "apricot"], dropdown=True)
        assert completion.accept("ap", 1) == "apricot"

    def test_accept_falls_back_to_the_first_row(self) -> None:
        completion = Completion(["apple", "apricot"], dropdown=True)
        assert completion.accept("ap", None) == "apple"

    def test_move_starts_at_the_top_going_down(self) -> None:
        completion = Completion(["apple", "apricot"], dropdown=True)
        assert completion.move("ap", None, 1) == 0

    def test_move_starts_at_the_bottom_going_up(self) -> None:
        completion = Completion(["apple", "apricot"], dropdown=True)
        assert completion.move("ap", None, -1) == 1

    def test_move_cycles_through_the_rows(self) -> None:
        completion = Completion(["apple", "apricot"], dropdown=True)
        assert completion.move("ap", 1, 1) == 0

    def test_move_is_none_without_matches(self) -> None:
        completion = Completion(["apple"], dropdown=True)
        assert completion.move("zz", 0, 1) is None

    def test_rows_are_capped_at_the_dropdown_limit(self) -> None:
        completion = Completion(
            [f"item{n}" for n in range(MAX_DROPDOWN + 5)], dropdown=True
        )
        assert len(completion.rows("item", None, theme())) == MAX_DROPDOWN

    def test_rows_render_the_matching_labels(self) -> None:
        completion = Completion(["apple", "apricot"], dropdown=True)
        rows = completion.rows("ap", 0, theme())
        assert "apple" in rows[0].plain()


class TestHistoryRecall:
    def test_previous_walks_backwards_from_the_newest(self) -> None:
        recall = HistoryRecall(["first", "second"])
        assert recall.previous() == "second"
        assert recall.previous() == "first"

    def test_previous_stops_at_the_oldest(self) -> None:
        recall = HistoryRecall(["only"])
        assert recall.previous() == "only"
        assert recall.previous() == "only"

    def test_previous_is_none_without_entries(self) -> None:
        assert HistoryRecall([]).previous() is None

    def test_following_without_a_walk_is_none(self) -> None:
        assert HistoryRecall(["a", "b"]).following() is None

    def test_following_walks_forward_again(self) -> None:
        recall = HistoryRecall(["first", "second"])
        recall.previous()
        recall.previous()
        assert recall.following() == "second"

    def test_walking_past_the_newest_clears_the_field(self) -> None:
        recall = HistoryRecall(["only"])
        recall.previous()
        assert recall.following() == ""

    def test_remember_is_a_no_op_without_a_store(self) -> None:
        recall = HistoryRecall(["a"])
        recall.remember("b")
        assert recall.entries == ["a"]

    def test_for_app_without_a_name_uses_the_fallback(self) -> None:
        recall = HistoryRecall.for_app(None, ["x", "y"])
        assert recall.entries == ["x", "y"]
