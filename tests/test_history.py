"""
Tests for persisted command history, including its path hardening.

The state directory and the application name both reach this code from
outside the process, so the tests cover the rejection of names that would
escape the state directory as well as the normal load/save round trip.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sparcli.input.history import History

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class TestHistoryEntries:
    def test_entries_start_empty(self) -> None:
        assert History().entries() == []

    def test_add_appends_in_order(self) -> None:
        history = History()
        history.add("first")
        history.add("second")
        assert history.entries() == ["first", "second"]

    def test_consecutive_duplicates_collapse_by_default(self) -> None:
        history = History()
        history.add("same")
        history.add("same")
        assert history.entries() == ["same"]

    def test_keep_duplicates_retains_them(self) -> None:
        history = History().keep_duplicates()
        history.add("same")
        history.add("same")
        assert history.entries() == ["same", "same"]

    def test_max_entries_drops_the_oldest(self) -> None:
        history = History().max_entries(2)
        for value in ("a", "b", "c"):
            history.add(value)
        assert history.entries() == ["b", "c"]

    def test_empty_values_are_ignored(self) -> None:
        history = History()
        history.add("")
        assert history.entries() == []


class TestHistoryPersistence:
    def test_save_then_load_round_trips(self, state_home: Path) -> None:
        assert state_home.is_dir()
        history = History.for_app("demo")
        history.add("one")
        history.add("two")
        history.save()

        reloaded = History.for_app("demo")
        reloaded.load()
        assert reloaded.entries() == ["one", "two"]

    def test_the_file_lands_under_the_state_directory(
        self, state_home: Path
    ) -> None:
        history = History.for_app("demo")
        history.add("x")
        history.save()
        assert (state_home / "demo" / "history").is_file()

    def test_loading_a_missing_file_is_silent(self, state_home: Path) -> None:
        assert state_home.is_dir()
        history = History.for_app("never-written")
        history.load()
        assert history.entries() == []

    def test_an_unbacked_history_saves_nothing(self, tmp_path: Path) -> None:
        history = History()
        history.add("x")
        history.save()
        assert list(tmp_path.iterdir()) == []


class TestHistoryPathHardening:
    def test_a_plain_name_is_accepted(self, state_home: Path) -> None:
        history = History.for_app("demo")
        history.add("x")
        history.save()
        assert (state_home / "demo" / "history").exists()

    def test_a_traversing_name_is_rejected(self, state_home: Path) -> None:
        # "../../etc" must never lead to a write outside the state directory.
        history = History.for_app("../../etc")
        history.add("x")
        history.save()
        assert not any(state_home.rglob("history"))

    def test_a_name_with_a_separator_is_rejected(
        self, state_home: Path
    ) -> None:
        history = History.for_app("a/b")
        history.add("x")
        history.save()
        assert not any(state_home.rglob("history"))

    def test_a_dot_name_is_rejected(self, state_home: Path) -> None:
        assert state_home.is_dir()
        history = History.for_app(".")
        history.load()
        assert history.entries() == []

    def test_an_empty_name_is_rejected(self, state_home: Path) -> None:
        assert state_home.is_dir()
        history = History.for_app("")
        history.load()
        assert history.entries() == []

    def test_no_state_directory_leaves_history_in_memory(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("XDG_STATE_HOME", raising=False)
        monkeypatch.delenv("HOME", raising=False)
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        history = History.for_app("demo")
        history.add("x")
        history.save()
        assert history.entries() == ["x"]


class TestHistoryLoadCap:
    def test_load_keeps_only_the_newest_max_entries(
        self, tmp_path: Path
    ) -> None:
        # The file is foreign input: an older build or another tool may have
        # left far more lines in it than this history is configured to hold.
        path = tmp_path / "history"
        path.write_text("a\nb\nc\nd\ne", encoding="utf-8")
        history = History().max_entries(2)
        history._path = path
        history.load()
        assert history.entries() == ["d", "e"]

    def test_a_saved_history_is_not_readable_by_other_accounts(
        self, tmp_path: Path
    ) -> None:
        import stat

        history = History()
        history._path = tmp_path / "history"
        history.add("a token someone pasted into a prompt")
        history.save()
        mode = stat.S_IMODE((tmp_path / "history").stat().st_mode)
        assert mode & 0o077 == 0
