"""
Tests for resolving and splitting the external editor and pager commands.

Both commands come from the environment, so they are split with ``shlex``
rather than ``str.split`` and never reach a shell. These tests pin that
behavior, including the failure paths that must surface as ``SparcliError``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sparcli.core.command import split_command as _split_command
from sparcli.errors import ConfigError, TerminalError
from sparcli.input.editor import _resolve_command
from sparcli.output.pager import Pager

if TYPE_CHECKING:
    from pathlib import Path


class TestSplitCommand:
    def test_a_simple_command_becomes_one_argument(self) -> None:
        assert _split_command("vi") == ["vi"]

    def test_arguments_are_separated(self) -> None:
        assert _split_command("code --wait") == ["code", "--wait"]

    def test_a_quoted_path_with_spaces_stays_one_argument(self) -> None:
        # This is the whole reason for shlex: str.split() would break this
        # path into two useless argv entries.
        argv = _split_command('"/Applications/Sublime Text/subl" -w')
        assert argv == ["/Applications/Sublime Text/subl", "-w"]

    def test_an_empty_command_yields_no_arguments(self) -> None:
        assert _split_command("") == []

    def test_an_unbalanced_quote_yields_no_arguments(self) -> None:
        assert _split_command('vi "unterminated') == []

    def test_the_pager_uses_the_same_splitting(self) -> None:
        argv = _split_command('"/usr/bin/my pager" -R')
        assert argv == ["/usr/bin/my pager", "-R"]


class TestResolveEditorCommand:
    def test_an_explicit_command_wins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EDITOR", "nano")
        assert _resolve_command("vim") == "vim"

    def test_visual_is_preferred_over_editor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VISUAL", "code -w")
        monkeypatch.setenv("EDITOR", "nano")
        assert _resolve_command(None) == "code -w"

    def test_editor_is_used_when_visual_is_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.setenv("EDITOR", "nano")
        assert _resolve_command(None) == "nano"

    def test_a_blank_environment_falls_back_to_a_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VISUAL", "   ")
        monkeypatch.setenv("EDITOR", "")
        assert _resolve_command(None).strip() != ""


class TestPagerCommand:
    def test_an_explicit_command_wins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PAGER", "more")
        assert Pager(command="less -R").resolve_command() == "less -R"

    def test_the_environment_is_used_when_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PAGER", "more")
        assert Pager().resolve_command() == "more"

    def test_a_blank_environment_falls_back_to_a_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PAGER", "  ")
        assert Pager().resolve_command().strip() != ""

    def test_a_blank_command_falls_through_to_the_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A blank value counts as unset everywhere, matching the editor and
        # the way a shell treats an empty variable.
        monkeypatch.setenv("PAGER", "less -R")
        assert Pager(command="").resolve_command() == "less -R"
        assert Pager(command="   ").resolve_command() == "less -R"

    def test_an_unparsable_command_raises_config_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An unbalanced quote yields no argv at all, which is unusable.
        from sparcli.core.text import Text
        from sparcli.output.compose import vstack

        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        pager = Pager(command='less "unterminated', always=True)
        with pytest.raises(ConfigError):
            pager.page(vstack([Text.raw("x")]))

    def test_a_missing_pager_raises_terminal_error(
        self, tmp_path: Path
    ) -> None:
        # A pager that does not exist must surface as a SparcliError, not as a
        # raw FileNotFoundError from subprocess.
        from sparcli.core.text import Text
        from sparcli.output.compose import vstack

        missing = str(tmp_path / "definitely-not-a-pager")
        pager = Pager(command=missing, always=True)
        with pytest.raises(TerminalError):
            pager.page(vstack([Text.raw("x")]))
