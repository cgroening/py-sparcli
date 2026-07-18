"""
sparcli.input.guard
===================

Defines :class:`TerminalGuard`, an RAII context manager for raw mode.

Entering the guard puts the terminal into raw mode and (best effort) enables
bracketed paste; leaving it - even on an exception - restores cooked mode and
disables bracketed paste. Restore failures are logged, never raised, so a
cancelled or crashing prompt cannot leave the terminal wedged. Off a TTY or on
platforms without ``termios`` the guard degrades to a harmless no-op.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from sparcli.core import cursor

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)

_ENABLE_PASTE = "\x1b[?2004h"
_DISABLE_PASTE = "\x1b[?2004l"


class TerminalGuard:
    """Enables raw mode for its lifetime and restores the terminal on exit."""

    __slots__ = ("_fd", "_paste", "_saved")

    def __init__(self) -> None:
        self._fd: int = -1
        self._saved: list[int | list[bytes | int]] | None = None
        self._paste: bool = False

    def __enter__(self) -> TerminalGuard:
        """Enables raw mode and bracketed paste, best effort."""
        self._enable()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Restores cooked mode and disables bracketed paste."""
        self._restore()

    def _enable(self) -> None:
        """Puts the terminal into raw mode and hides the cursor."""
        if sys.platform != "win32":
            self._enable_raw()
        self._enable_paste()
        cursor.hide()

    def _enable_raw(self) -> None:
        """Enables POSIX raw mode, saving the previous terminal settings."""
        import termios  # available on every non-win32 platform
        import tty

        try:
            self._fd = sys.stdin.fileno()
            self._saved = termios.tcgetattr(self._fd)
            tty.setraw(self._fd)
        except (OSError, ValueError, termios.error) as error:
            self._saved = None
            logger.warning("could not enable raw mode: %s", error)

    def _enable_paste(self) -> None:
        """Requests bracketed paste from the terminal, best effort."""
        try:
            sys.stdout.write(_ENABLE_PASTE)
            sys.stdout.flush()
            self._paste = True
        except (OSError, ValueError) as error:
            logger.warning("could not enable bracketed paste: %s", error)

    def _restore(self) -> None:
        """Restores cooked mode, disables bracketed paste, shows the cursor."""
        cursor.show()
        if self._paste:
            self._disable_paste()
        if self._saved is None:
            return
        import termios  # available on every non-win32 platform

        try:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
        except (OSError, ValueError, termios.error) as error:
            logger.warning(
                "could not restore terminal from raw mode: %s", error
            )

    def _disable_paste(self) -> None:
        """Disables bracketed paste, best effort."""
        try:
            sys.stdout.write(_DISABLE_PASTE)
            sys.stdout.flush()
        except (OSError, ValueError) as error:
            logger.warning("could not disable bracketed paste: %s", error)
