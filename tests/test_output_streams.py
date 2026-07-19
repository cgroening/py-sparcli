"""
Tests for the CLI output rules of section 1.6 of the style guide.

Two rules are load-bearing for a program that pipes its output onward: payload
goes to stdout while progress goes to stderr, and nothing is truncated when
there is no terminal whose width to respect.
"""

from __future__ import annotations

import io
import sys

from sparcli.core.command import resolve_from_env, split_command
from sparcli.core.inplace import InPlace
from sparcli.core.terminal import UNCONSTRAINED_WIDTH, output_width
from sparcli.core.width import strip_ansi
from sparcli.output.card.card import Card
from sparcli.output.table.table import Table


class TestProgressStream:
    def test_progress_draws_on_standard_error(self) -> None:
        # A progress bar is not payload. Drawing it on stdout would put
        # animation frames into whatever a caller pipes the output into.
        assert InPlace.progress()._stream is sys.stderr

    def test_a_live_display_stays_on_standard_output(self) -> None:
        assert InPlace.create()._stream is sys.stdout


class TestUnconstrainedWidth:
    def test_output_width_is_unconstrained_without_a_terminal(
        self, monkeypatch: object
    ) -> None:
        # Under pytest stdout is not a terminal, which is exactly the piped
        # case the rule is about.
        assert output_width() == UNCONSTRAINED_WIDTH

    def test_printing_without_a_terminal_does_not_truncate(self) -> None:
        wide = "w" * 200
        table = Table().columns(["id", "value"]).row(["1", wide])
        buffer = io.StringIO()
        table.print_to(buffer)
        text = strip_ansi(buffer.getvalue())
        assert wide in text, "the full value survives the pipe"
        assert "…" not in text, "nothing was clipped"

    def test_an_explicit_render_width_still_truncates(self) -> None:
        # The rule applies to print/print_to, which resolve the width
        # themselves. An explicit width is the caller's decision.
        wide = "w" * 200
        table = Table().columns(["id", "value"]).row(["1", wide])
        text = strip_ansi(table.render(40).plain())
        assert "…" in text

    def test_an_unconstrained_card_shrinks_to_its_content(self) -> None:
        # "Fill the terminal width" is meaningless without a terminal, so the
        # card lays out at its natural width instead of stretching.
        out = Card("body").render(UNCONSTRAINED_WIDTH)
        assert out.lines[0].width() == 6, "body plus one padding column a side"
        assert "body" in out.plain()

    def test_an_unconstrained_card_still_honors_an_explicit_width(
        self,
    ) -> None:
        out = Card("body").width(20).render(UNCONSTRAINED_WIDTH)
        for line in out.lines:
            assert line.width() == 20


class TestSharedCommandResolution:
    def test_an_override_wins_over_the_environment(self) -> None:
        assert resolve_from_env("nano", ("PATH",), "vi") == "nano"

    def test_a_blank_value_counts_as_unset(self) -> None:
        assert resolve_from_env("   ", (), "vi") == "vi"
        assert resolve_from_env(None, (), "vi") == "vi"

    def test_keys_are_consulted_in_order(self, monkeypatch: object) -> None:
        monkeypatch.setenv("SPARCLI_TEST_A", "  ")  # type: ignore[attr-defined]
        monkeypatch.setenv("SPARCLI_TEST_B", "second")  # type: ignore[attr-defined]
        keys = ("SPARCLI_TEST_A", "SPARCLI_TEST_B")
        assert resolve_from_env(None, keys, "vi") == "second"

    def test_an_unbalanced_quote_yields_no_argv(self) -> None:
        assert split_command('vi "unterminated') == []

    def test_a_quoted_path_with_spaces_stays_one_argument(self) -> None:
        argv = split_command('"/Applications/Sublime Text/subl" -w')
        assert argv == ["/Applications/Sublime Text/subl", "-w"]
