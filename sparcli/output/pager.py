"""
sparcli.output.pager
====================

Pipes long output through ``$PAGER``, ``less`` or ``more``.

When output is not a terminal (and the pager is not forced), content is printed
directly instead of spawning a pager. Otherwise the widget renders at the
terminal width, spawns the resolved pager as an argument list (never through a
shell) and pipes the ANSI-encoded content into its standard input.
"""

from __future__ import annotations

import io
import os
import subprocess

from sparcli.core.render import Renderable, write_rendered
from sparcli.core.terminal import ColorSupport, is_output_tty, term_width
from sparcli.errors import ConfigError

# The default pager command string for the current platform.
_DEFAULT_PAGER = "more" if os.name == "nt" else "less -R"


class Pager:
    """Pages content through an external pager."""

    __slots__ = ("_command", "_always")

    def __init__(
        self, *, command: str | None = None, always: bool = False
    ) -> None:
        self._command = command
        self._always = always

    def command(self, command: str) -> Pager:
        """Overrides the pager command (whitespace-split, no shell)."""
        self._command = command
        return self

    def always(self) -> Pager:
        """Pages even when output is not a terminal and returns the pager."""
        self._always = True
        return self

    def page(self, content: Renderable) -> None:
        """
        Pages ``content``, falling back to a direct print off-terminal.

        Parameters
        ----------
        content : Renderable
            The widget to page.

        Raises
        ------
        ConfigError
            If the resolved pager command is empty.
        """
        if not self._always and not is_output_tty():
            content.print()
            return
        rendered = content.render(term_width())
        argv = self.resolve_command().split()
        if not argv:
            raise ConfigError("empty pager")
        buffer = io.StringIO()
        write_rendered(buffer, rendered, ColorSupport.TRUECOLOR)
        with subprocess.Popen(  # noqa: S603
            argv, stdin=subprocess.PIPE, text=True
        ) as process:
            process.communicate(buffer.getvalue())

    def resolve_command(self) -> str:
        """Resolves the pager command string."""
        if self._command is not None:
            return self._command
        value = os.environ.get("PAGER")
        if value is not None and value.strip():
            return value
        return _DEFAULT_PAGER
