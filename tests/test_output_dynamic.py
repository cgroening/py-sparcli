"""Tests for the dynamic output widgets: spinner, progress, pager."""

from __future__ import annotations

import pytest

from sparcli.core.color import Color
from sparcli.core.render import Renderable, Rendered
from sparcli.core.text import Text
from sparcli.errors import ConfigError
from sparcli.output.live import InPlace
from sparcli.output.multiprogress import MultiProgress
from sparcli.output.pager import Pager
from sparcli.output.progress import (
    ProgressBar,
    ProgressStyle,
    Thresholds,
)
from sparcli.output.spinner import Spinner, SpinnerStyle


def _plain(rendered: Rendered) -> str:
    """Returns the first line of a rendered block as plain text."""
    return rendered.lines[0].plain()


class TestSpinner:
    def test_frame_contains_glyph_and_label(self) -> None:
        spinner = Spinner("loading")
        line = _plain(spinner.frame())
        assert "⠋" in line
        assert "loading" in line

    def test_pipe_style_uses_ascii_frames(self) -> None:
        spinner = Spinner("").style(SpinnerStyle.PIPE)
        assert _plain(spinner.frame()) == "|"

    def test_dots_and_arrow_first_frames(self) -> None:
        assert _plain(Spinner("").style(SpinnerStyle.DOTS).frame()) == "⣾"
        assert _plain(Spinner("").style(SpinnerStyle.ARROW).frame()) == "←"

    def test_tick_advances_frame_index(self) -> None:
        spinner = Spinner("x", inplace=InPlace.silent())
        assert _plain(spinner.frame()).startswith("⠋")
        spinner.tick()
        assert _plain(spinner.frame()).startswith("⠙")

    def test_set_label_updates_text(self) -> None:
        spinner = Spinner("one")
        spinner.set_label("two")
        assert "two" in _plain(spinner.frame())

    def test_color_builder_sets_fill_color(self) -> None:
        spinner = Spinner("x").color(Color.RED)
        assert spinner.frame().lines[0].spans[0].style.fg == Color.RED

    def test_finish_success_shows_check_mark(self) -> None:
        spinner = Spinner("done", inplace=InPlace.silent())
        spinner.finish(success=True, label="ok")
        # Frame reflects the marker glyph and updated label.
        assert "ok" in _plain(spinner.frame())

    def test_clear_untouched_spinner_is_harmless(self) -> None:
        Spinner("loading").clear()


class TestProgressBar:
    def test_empty_bar_is_all_empty_glyphs(self) -> None:
        bar = ProgressBar().width(4).show_percent(False)
        assert _plain(bar.bar(0.0, 10.0)) == "░░░░"

    def test_full_bar_is_all_filled_glyphs(self) -> None:
        bar = ProgressBar().width(4).show_percent(False)
        assert _plain(bar.bar(10.0, 10.0)) == "████"

    def test_half_bar_is_half_filled(self) -> None:
        bar = ProgressBar().width(4).show_percent(False)
        assert _plain(bar.bar(5.0, 10.0)) == "██░░"

    def test_quarter_rounds_half_away_from_zero(self) -> None:
        bar = ProgressBar().width(2).show_percent(False)
        assert _plain(bar.bar(1.0, 4.0)) == "█░"

    def test_percent_suffix_is_shown(self) -> None:
        bar = ProgressBar().width(2)
        assert "25%" in _plain(bar.bar(1.0, 4.0))

    def test_zero_max_is_safe(self) -> None:
        bar = ProgressBar().width(3).show_percent(False)
        assert _plain(bar.bar(1.0, 0.0)) == "░░░"

    def test_ascii_style_glyphs(self) -> None:
        bar = (
            ProgressBar()
            .style(ProgressStyle.ASCII)
            .width(4)
            .show_percent(False)
        )
        assert _plain(bar.bar(2.0, 4.0)) == "##--"

    def test_caps_wrap_the_bar(self) -> None:
        bar = ProgressBar().width(2).show_percent(False).caps("[", "]")
        assert _plain(bar.bar(2.0, 2.0)) == "[██]"

    def test_label_precedes_the_bar(self) -> None:
        bar = ProgressBar().width(2).show_percent(False).label("job")
        assert _plain(bar.bar(0.0, 2.0)).startswith("job ░░")

    def test_show_value_suffix(self) -> None:
        bar = ProgressBar().width(2).show_percent(False).show_value(True)
        assert "(3/8)" in _plain(bar.bar(3.0, 8.0))

    def test_width_is_at_least_one(self) -> None:
        bar = ProgressBar().width(0).show_percent(False)
        assert _plain(bar.bar(0.0, 1.0)) == "░"

    def test_draw_is_headless_with_silent_inplace(self) -> None:
        bar = ProgressBar(inplace=InPlace.silent())
        bar.draw(1.0, 2.0)
        bar.finish(2.0, 2.0)


class TestThresholds:
    def _thresholds(self) -> Thresholds:
        return Thresholds(
            mid=0.5,
            high=0.9,
            low_color=Color.RED,
            mid_color=Color.YELLOW,
            high_color=Color.GREEN,
        )

    def _fill_color(self, ratio: float) -> Color | None:
        bar = ProgressBar().width(10).thresholds(self._thresholds())
        rendered = bar.bar(ratio, 1.0)
        # The filled span is the first span for a bar without label or cap.
        return rendered.lines[0].spans[0].style.fg

    def test_low_ratio_uses_low_color(self) -> None:
        assert self._fill_color(0.1) == Color.RED

    def test_mid_ratio_uses_mid_color(self) -> None:
        assert self._fill_color(0.5) == Color.YELLOW
        assert self._fill_color(0.7) == Color.YELLOW

    def test_high_ratio_uses_high_color(self) -> None:
        assert self._fill_color(0.9) == Color.GREEN
        assert self._fill_color(1.0) == Color.GREEN


class TestMultiProgress:
    def test_frame_has_one_line_per_bar(self) -> None:
        multi = MultiProgress(inplace=InPlace.silent())
        multi.add(ProgressBar().label("a"))
        multi.add(ProgressBar().label("b"))
        assert multi.frame().height() == 2

    def test_add_returns_sequential_indices(self) -> None:
        multi = MultiProgress(inplace=InPlace.silent())
        assert multi.add(ProgressBar()) == 0
        assert multi.add(ProgressBar()) == 1

    def test_update_reflects_new_value(self) -> None:
        multi = MultiProgress(inplace=InPlace.silent())
        multi.add(ProgressBar().width(4).show_percent(False))
        multi.update(0, 4.0, 4.0)
        assert _plain(multi.frame()) == "████"

    def test_update_ignores_out_of_range_index(self) -> None:
        multi = MultiProgress(inplace=InPlace.silent())
        multi.add(ProgressBar().width(2).show_percent(False))
        multi.update(5, 1.0, 1.0)
        assert _plain(multi.frame()) == "░░"

    def test_finish_and_transient_finish_are_headless(self) -> None:
        MultiProgress(inplace=InPlace.silent()).finish()
        MultiProgress(inplace=InPlace.silent()).transient().finish()


class _FakeWidget(Renderable):
    """A minimal renderable emitting a single fixed line."""

    def render(self, max_width: int) -> Rendered:
        return Rendered.from_text(Text.raw("hello pager"))


class TestPager:
    def test_resolves_explicit_command(self) -> None:
        pager = Pager().command("bat --paging always")
        assert pager.resolve_command() == "bat --paging always"

    def test_resolves_pager_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PAGER", "less -F")
        assert Pager().resolve_command() == "less -F"

    def test_blank_env_var_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PAGER", "   ")
        assert Pager().resolve_command() == _expected_default()

    def test_default_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PAGER", raising=False)
        assert Pager().resolve_command() == _expected_default()

    def test_page_off_terminal_prints_without_spawning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("SPARCLI_NO_TTY", "1")

        def _forbid_popen(*args: object, **kwargs: object) -> None:
            raise AssertionError("pager must not spawn a process")

        monkeypatch.setattr(
            "sparcli.output.pager.subprocess.Popen", _forbid_popen
        )
        Pager().page(_FakeWidget())
        assert "hello pager" in capsys.readouterr().out

    def test_page_empty_command_raises_config_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SPARCLI_NO_TTY", "1")
        with pytest.raises(ConfigError):
            Pager().command("   ").always().page(_FakeWidget())


def _expected_default() -> str:
    """Returns the platform default pager command for assertions."""
    import os

    return "more" if os.name == "nt" else "less -R"
