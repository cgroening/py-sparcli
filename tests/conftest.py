"""Shared fixtures and rendering helpers for the sparcli test suite."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sparcli.core.render import write_rendered
from sparcli.core.terminal import ColorSupport
from sparcli.core.theme import Theme, set_theme

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from sparcli.core.render import Rendered


def plain_lines(rendered: Rendered) -> list[str]:
    """Returns the plain text of each rendered line."""
    return [line.plain() for line in rendered.lines]


def joined(rendered: Rendered) -> str:
    """Returns the plain text of all lines, joined by newlines."""
    return "\n".join(line.plain() for line in rendered.lines)


def render_to_string(rendered: Rendered, support: ColorSupport) -> str:
    """Writes a block to a string with the given color support."""
    import io

    buffer = io.StringIO()
    write_rendered(buffer, rendered, support)
    return buffer.getvalue()


def ansi(rendered: Rendered) -> str:
    """Writes a block to a string with full color, escapes included."""
    return render_to_string(rendered, ColorSupport.TRUECOLOR)


@pytest.fixture(autouse=True)
def _reset_theme() -> Iterator[None]:
    """
    Restores the default theme after every test.

    The theme is process-wide state, so a test that sets one would otherwise
    leak into whatever runs next.
    """
    yield
    set_theme(Theme())


@pytest.fixture
def state_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Points the history state directory at an isolated temp directory."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    return tmp_path
