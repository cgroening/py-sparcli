"""
Time-based and interactive output widgets.

Covers the spinner, a single progress bar, a multi-progress group, a live
in-place redraw and the pager. Run it in a real terminal for the full effect:
``python examples/output_dynamic.py``.

Off a terminal (piped or redirected) the animations collapse to a single final
frame and the pager prints its content directly, so the example still runs
cleanly headless. The per-frame pauses are skipped when there is no terminal.
"""

from __future__ import annotations

import time

from sparcli import (
    Line,
    Live,
    MultiProgress,
    Pager,
    Panel,
    ProgressBar,
    Renderable,
    Rendered,
    Spinner,
    is_output_tty,
)


class _Block(Renderable):
    """Wraps a pre-rendered block so the pager can page it."""

    def __init__(self, block: Rendered) -> None:
        self._block = block

    def render(self, max_width: int) -> Rendered:
        return self._block


def _pause(seconds: float) -> None:
    """Sleeps only on a real terminal, so headless runs stay instant."""
    if is_output_tty():
        time.sleep(seconds)


def spinner() -> None:
    """Animates a spinner for a moment, then finishes with a success mark."""
    spin = Spinner("working")
    for _ in range(12):
        spin.tick()
        _pause(0.08)
    spin.finish(success=True, label="done")


def progress() -> None:
    """Fills a single progress bar from 0 to 100 percent."""
    bar = ProgressBar().label("download").width(30)
    for step in range(21):
        bar.draw(float(step), 20.0)
        _pause(0.05)
    bar.finish(20.0, 20.0)


def multi_progress() -> None:
    """Advances two bars together in a single block."""
    multi = MultiProgress()
    downloads = multi.add(ProgressBar().label("downloads").width(20))
    installs = multi.add(ProgressBar().label("installs ").width(20))
    for step in range(21):
        multi.update(downloads, float(step), 20.0)
        multi.update(installs, float(step) * 0.6, 20.0)
        _pause(0.06)
    multi.finish()


def live() -> None:
    """Redraws a panel in place a few times."""
    view = Live()
    for tick in range(1, 9):
        view.update(Panel(f"live tick {tick}").title("Live").width(30))
        _pause(0.12)
    view.finish()


def pager() -> None:
    """Pages a long block of lines (spawns $PAGER on a terminal)."""
    lines = [Line.raw(f"line {number}") for number in range(1, 201)]
    Pager().page(_Block(Rendered(lines)))


def main() -> None:
    """Runs each time-based output widget in turn."""
    spinner()
    progress()
    multi_progress()
    live()
    pager()


if __name__ == "__main__":
    main()
