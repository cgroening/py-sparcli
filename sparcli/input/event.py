"""
sparcli.input.event
===================

Defines the keyboard-event abstraction and its event sources.

Prompts read :class:`InputEvent` values from an :class:`EventSource`. A
:class:`KeyCode` is a backend-independent logical key; a :class:`KeyPress`
bundles it with modifier flags. :class:`TerminalSource` reads real keystrokes
from the terminal using the standard library (``termios``/``tty`` on POSIX,
``msvcrt`` on Windows) and parses escape sequences into events.
:class:`ScriptedSource` is the test fake that replays a queued list of keys and
auto-cancels on exhaustion, so prompts can be driven headlessly.
"""

from __future__ import annotations

import enum
import os
import select
import sys
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, replace
from typing import ClassVar

# Timeout (seconds) used to disambiguate a lone Esc from an escape sequence.
_ESC_TIMEOUT = 0.05
# Timeout (seconds) used while draining a bracketed-paste payload.
_PASTE_TIMEOUT = 0.2

# Byte offset that turns a Ctrl-letter control byte into its ASCII letter.
_CTRL_LETTER_BASE = 0x60


class KeyKind(enum.Enum):
    """The logical category of a :class:`KeyCode`."""

    CHAR = enum.auto()
    ENTER = enum.auto()
    ESC = enum.auto()
    TAB = enum.auto()
    BACK_TAB = enum.auto()
    BACKSPACE = enum.auto()
    DELETE = enum.auto()
    UP = enum.auto()
    DOWN = enum.auto()
    LEFT = enum.auto()
    RIGHT = enum.auto()
    HOME = enum.auto()
    END = enum.auto()
    PAGE_UP = enum.auto()
    PAGE_DOWN = enum.auto()
    FUNCTION = enum.auto()
    UNKNOWN = enum.auto()


@dataclass(frozen=True, slots=True)
class KeyCode:
    """
    A logical key, independent of the terminal backend.

    Parameterless keys are available as class constants (``KeyCode.ENTER``);
    printable characters and function keys are built with :meth:`char` and
    :meth:`function`.

    Attributes
    ----------
    kind : KeyKind
        The key category.
    ch : str | None
        The character for :attr:`KeyKind.CHAR`, otherwise ``None``.
    n : int | None
        The number for :attr:`KeyKind.FUNCTION`, otherwise ``None``.
    """

    kind: KeyKind
    ch: str | None = None
    n: int | None = None

    ENTER: ClassVar[KeyCode]
    ESC: ClassVar[KeyCode]
    TAB: ClassVar[KeyCode]
    BACK_TAB: ClassVar[KeyCode]
    BACKSPACE: ClassVar[KeyCode]
    DELETE: ClassVar[KeyCode]
    UP: ClassVar[KeyCode]
    DOWN: ClassVar[KeyCode]
    LEFT: ClassVar[KeyCode]
    RIGHT: ClassVar[KeyCode]
    HOME: ClassVar[KeyCode]
    END: ClassVar[KeyCode]
    PAGE_UP: ClassVar[KeyCode]
    PAGE_DOWN: ClassVar[KeyCode]
    UNKNOWN: ClassVar[KeyCode]

    @classmethod
    def char(cls, ch: str) -> KeyCode:
        """Returns a printable-character key."""
        return cls(KeyKind.CHAR, ch=ch)

    @classmethod
    def function(cls, n: int) -> KeyCode:
        """Returns a function key ``F<n>``."""
        return cls(KeyKind.FUNCTION, n=n)


_SIMPLE_CODES: dict[str, KeyKind] = {
    "ENTER": KeyKind.ENTER,
    "ESC": KeyKind.ESC,
    "TAB": KeyKind.TAB,
    "BACK_TAB": KeyKind.BACK_TAB,
    "BACKSPACE": KeyKind.BACKSPACE,
    "DELETE": KeyKind.DELETE,
    "UP": KeyKind.UP,
    "DOWN": KeyKind.DOWN,
    "LEFT": KeyKind.LEFT,
    "RIGHT": KeyKind.RIGHT,
    "HOME": KeyKind.HOME,
    "END": KeyKind.END,
    "PAGE_UP": KeyKind.PAGE_UP,
    "PAGE_DOWN": KeyKind.PAGE_DOWN,
    "UNKNOWN": KeyKind.UNKNOWN,
}


def _install_simple_codes() -> None:
    """Attaches a class constant for every parameterless key code."""
    for name, kind in _SIMPLE_CODES.items():
        setattr(KeyCode, name, KeyCode(kind))


_install_simple_codes()


@dataclass(frozen=True, slots=True)
class KeyPress:
    """
    A key press with its modifier flags.

    Attributes
    ----------
    code : KeyCode
        The logical key.
    ctrl, alt, shift : bool
        The active modifier flags.
    """

    code: KeyCode
    ctrl: bool = False
    alt: bool = False
    shift: bool = False

    @classmethod
    def new(cls, code: KeyCode) -> KeyPress:
        """Returns a key press with no modifiers."""
        return cls(code)

    @classmethod
    def ctrl_key(cls, letter: str) -> KeyPress:
        """Returns a Ctrl + letter key press."""
        return cls(KeyCode.char(letter), ctrl=True)

    def is_ctrl(self, letter: str) -> bool:
        """Returns whether this is Ctrl + the given letter."""
        return self.ctrl and self.code == KeyCode.char(letter)


class EventKind(enum.Enum):
    """The category of an :class:`InputEvent`."""

    KEY = enum.auto()
    PASTE = enum.auto()
    RESIZE = enum.auto()


@dataclass(frozen=True, slots=True)
class InputEvent:
    """
    An input event delivered to a prompt.

    Attributes
    ----------
    kind : EventKind
        Which flavour of event this is.
    key : KeyPress | None
        The key press for :attr:`EventKind.KEY`, otherwise ``None``.
    text : str | None
        The pasted payload for :attr:`EventKind.PASTE`, otherwise ``None``.
    """

    kind: EventKind
    key: KeyPress | None = None
    text: str | None = None

    RESIZE: ClassVar[InputEvent]

    @classmethod
    def from_key(cls, key: KeyPress) -> InputEvent:
        """Returns a key event."""
        return cls(EventKind.KEY, key=key)

    @classmethod
    def paste(cls, text: str) -> InputEvent:
        """Returns a bracketed-paste event."""
        return cls(EventKind.PASTE, text=text)


InputEvent.RESIZE = InputEvent(EventKind.RESIZE)


class EventSource(ABC):
    """A source of input events."""

    @abstractmethod
    def next_event(self) -> InputEvent:
        """
        Blocks until the next event is available and returns it.

        Returns
        -------
        InputEvent
            The next event from the source.
        """
        raise NotImplementedError

    def is_interactive(self) -> bool:
        """
        Returns whether this source drives a real, interactive terminal.

        Non-interactive sources (scripted tests) must not draw to the terminal,
        so the prompt loop skips rendering for them.
        """
        return True


def _esc_event() -> InputEvent:
    """Returns an Esc key event, used as a safe fallback."""
    return InputEvent.from_key(KeyPress.new(KeyCode.ESC))


def _decode_modifier(text: str) -> tuple[bool, bool, bool]:
    """Decodes a CSI modifier parameter into ``(ctrl, alt, shift)``."""
    if not text:
        return (False, False, False)
    try:
        mask = int(text) - 1
    except ValueError:
        return (False, False, False)
    return (bool(mask & 4), bool(mask & 2), bool(mask & 1))


def _poll_ready(fd: int, timeout: float) -> bool:
    """Returns whether ``fd`` has data ready within ``timeout`` seconds."""
    try:
        ready, _, _ = select.select([fd], [], [], timeout)
    except (OSError, ValueError):
        return False
    return bool(ready)


class ScriptedSource(EventSource):
    """
    A scripted event source for tests: replays queued events in order.

    On exhaustion it yields Esc, cancelling the prompt and preventing infinite
    loops in headless tests.
    """

    __slots__ = ("_events",)

    def __init__(self, script: list[KeyCode | InputEvent]) -> None:
        self._events: deque[InputEvent] = deque(
            item
            if isinstance(item, InputEvent)
            else InputEvent.from_key(KeyPress.new(item))
            for item in script
        )

    @classmethod
    def keys(cls, codes: list[KeyCode]) -> ScriptedSource:
        """Builds a source from a sequence of key codes."""
        return cls(list(codes))

    def next_event(self) -> InputEvent:
        """Returns the next queued event, or Esc once exhausted."""
        if not self._events:
            return _esc_event()
        return self._events.popleft()

    def is_interactive(self) -> bool:
        """Returns ``False``: a scripted source never draws to a terminal."""
        return False


# CSI final letters shared by cursor and editing keys.
_CSI_LETTER: dict[str, KeyCode] = {
    "A": KeyCode.UP,
    "B": KeyCode.DOWN,
    "C": KeyCode.RIGHT,
    "D": KeyCode.LEFT,
    "H": KeyCode.HOME,
    "F": KeyCode.END,
    "Z": KeyCode.BACK_TAB,
}

# CSI ``<n>~`` numeric keys (navigation and function keys).
_CSI_TILDE: dict[int, KeyCode] = {
    1: KeyCode.HOME,
    2: KeyCode.UNKNOWN,
    3: KeyCode.DELETE,
    4: KeyCode.END,
    5: KeyCode.PAGE_UP,
    6: KeyCode.PAGE_DOWN,
    7: KeyCode.HOME,
    8: KeyCode.END,
    11: KeyCode.function(1),
    12: KeyCode.function(2),
    13: KeyCode.function(3),
    14: KeyCode.function(4),
    15: KeyCode.function(5),
    17: KeyCode.function(6),
    18: KeyCode.function(7),
    19: KeyCode.function(8),
    20: KeyCode.function(9),
    21: KeyCode.function(10),
    23: KeyCode.function(11),
    24: KeyCode.function(12),
}

# SS3 final letters (``ESC O x``), used by some terminals for F1-F4 and arrows.
_SS3_LETTER: dict[str, KeyCode] = {
    "P": KeyCode.function(1),
    "Q": KeyCode.function(2),
    "R": KeyCode.function(3),
    "S": KeyCode.function(4),
    "A": KeyCode.UP,
    "B": KeyCode.DOWN,
    "C": KeyCode.RIGHT,
    "D": KeyCode.LEFT,
    "H": KeyCode.HOME,
    "F": KeyCode.END,
}

# Windows extended-key second characters returned after a ``\x00``/``\xe0``.
_WIN_SPECIAL: dict[str, KeyCode] = {
    "H": KeyCode.UP,
    "P": KeyCode.DOWN,
    "K": KeyCode.LEFT,
    "M": KeyCode.RIGHT,
    "G": KeyCode.HOME,
    "O": KeyCode.END,
    "I": KeyCode.PAGE_UP,
    "Q": KeyCode.PAGE_DOWN,
    "S": KeyCode.DELETE,
    ";": KeyCode.function(1),
    "<": KeyCode.function(2),
    "=": KeyCode.function(3),
    ">": KeyCode.function(4),
    "?": KeyCode.function(5),
    "@": KeyCode.function(6),
    "A": KeyCode.function(7),
    "B": KeyCode.function(8),
    "C": KeyCode.function(9),
    "D": KeyCode.function(10),
}


class TerminalSource(EventSource):
    """
    The real event source: reads keystrokes from the terminal.

    Uses ``os.read`` plus ``select`` on POSIX and ``msvcrt`` on Windows. Raw
    mode is expected to be enabled by a
    :class:`~sparcli.input.guard.TerminalGuard` for the source's lifetime.
    """

    __slots__ = ("_fd",)

    def __init__(self) -> None:
        try:
            self._fd = sys.stdin.fileno()
        except (OSError, ValueError):
            self._fd = -1

    def next_event(self) -> InputEvent:
        """Reads and returns the next terminal event."""
        if sys.platform == "win32":
            return self._next_windows()
        return self._next_posix()

    def _next_posix(self) -> InputEvent:
        """Reads the next event from a POSIX terminal."""
        chunk = os.read(self._fd, 1)
        if not chunk:
            return _esc_event()
        byte = chunk[0]
        if byte == 0x1B:
            return self._read_escape()
        return self._decode_byte(byte)

    def _read_escape(self) -> InputEvent:
        """Parses an escape sequence following an initial Esc byte."""
        if not _poll_ready(self._fd, _ESC_TIMEOUT):
            return _esc_event()
        second = os.read(self._fd, 1)
        if not second:
            return _esc_event()
        if second == b"[":
            return self._read_csi()
        if second == b"O":
            return self._read_ss3()
        inner = self._decode_byte(second[0])
        if inner.key is not None:
            return InputEvent.from_key(replace(inner.key, alt=True))
        return inner

    def _read_csi(self) -> InputEvent:
        """Reads a CSI sequence (``ESC [ ...``) up to its final byte."""
        buf = bytearray()
        while _poll_ready(self._fd, _ESC_TIMEOUT):
            byte = os.read(self._fd, 1)
            if not byte:
                break
            buf += byte
            if 0x40 <= byte[0] <= 0x7E:
                break
        if not buf:
            return _esc_event()
        return self._decode_csi(bytes(buf))

    def _decode_csi(self, seq: bytes) -> InputEvent:
        """Maps a CSI sequence body to an input event."""
        text = seq.decode("ascii", "replace")
        final = text[-1]
        params = text[:-1]
        if params == "200" and final == "~":
            return self._read_paste()
        numbers = params.split(";")
        ctrl, alt, shift = _decode_modifier(
            numbers[1] if len(numbers) > 1 else ""
        )
        if final == "~":
            code = _CSI_TILDE.get(_to_int(numbers[0]), KeyCode.UNKNOWN)
        else:
            code = _CSI_LETTER.get(final, KeyCode.UNKNOWN)
        press = KeyPress(code, ctrl=ctrl, alt=alt, shift=shift)
        return InputEvent.from_key(press)

    def _read_ss3(self) -> InputEvent:
        """Reads an SS3 sequence (``ESC O x``)."""
        byte = os.read(self._fd, 1)
        if not byte:
            return _esc_event()
        code = _SS3_LETTER.get(chr(byte[0]), KeyCode.UNKNOWN)
        return InputEvent.from_key(KeyPress.new(code))

    def _read_paste(self) -> InputEvent:
        """Drains a bracketed-paste payload up to its terminator."""
        terminator = b"\x1b[201~"
        data = bytearray()
        while _poll_ready(self._fd, _PASTE_TIMEOUT):
            byte = os.read(self._fd, 1)
            if not byte:
                break
            data += byte
            if data.endswith(terminator):
                del data[-len(terminator) :]
                break
        return InputEvent.paste(data.decode("utf-8", "replace"))

    def _decode_byte(self, byte: int) -> InputEvent:
        """Decodes a single leading byte into a key event."""
        if byte in (0x0D, 0x0A):
            return InputEvent.from_key(KeyPress.new(KeyCode.ENTER))
        if byte == 0x09:
            return InputEvent.from_key(KeyPress.new(KeyCode.TAB))
        if byte in (0x7F, 0x08):
            return InputEvent.from_key(KeyPress.new(KeyCode.BACKSPACE))
        if 0x01 <= byte <= 0x1A:
            letter = chr(byte + _CTRL_LETTER_BASE)
            return InputEvent.from_key(
                KeyPress(KeyCode.char(letter), ctrl=True)
            )
        if byte < 0x20:
            return InputEvent.from_key(KeyPress.new(KeyCode.UNKNOWN))
        text = self._read_utf8(byte)
        if text is None:
            return InputEvent.from_key(KeyPress.new(KeyCode.UNKNOWN))
        return InputEvent.from_key(KeyPress.new(KeyCode.char(text)))

    def _read_utf8(self, lead: int) -> str | None:
        """Completes a UTF-8 character given its leading byte."""
        extra = _utf8_continuation_count(lead)
        buf = bytearray([lead])
        for _ in range(extra):
            byte = os.read(self._fd, 1)
            if not byte:
                break
            buf += byte
        try:
            return buf.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def _next_windows(self) -> InputEvent:
        """Reads the next event from a Windows console."""
        import msvcrt  # noqa: PLC0415

        first = msvcrt.getwch()
        if first in ("\x00", "\xe0"):
            code = _WIN_SPECIAL.get(msvcrt.getwch(), KeyCode.UNKNOWN)
            return InputEvent.from_key(KeyPress.new(code))
        return self._decode_char_windows(first)

    def _decode_char_windows(self, ch: str) -> InputEvent:
        """Decodes a single Windows character into a key event."""
        byte = ord(ch)
        if ch in ("\r", "\n"):
            return InputEvent.from_key(KeyPress.new(KeyCode.ENTER))
        if ch == "\t":
            return InputEvent.from_key(KeyPress.new(KeyCode.TAB))
        if ch in ("\x08", "\x7f"):
            return InputEvent.from_key(KeyPress.new(KeyCode.BACKSPACE))
        if ch == "\x1b":
            return InputEvent.from_key(KeyPress.new(KeyCode.ESC))
        if 0x01 <= byte <= 0x1A:
            letter = chr(byte + _CTRL_LETTER_BASE)
            return InputEvent.from_key(
                KeyPress(KeyCode.char(letter), ctrl=True)
            )
        return InputEvent.from_key(KeyPress.new(KeyCode.char(ch)))


def _to_int(text: str) -> int:
    """Parses an integer, defaulting to ``0`` on failure."""
    try:
        return int(text)
    except ValueError:
        return 0


def _utf8_continuation_count(lead: int) -> int:
    """Returns how many continuation bytes follow a UTF-8 leading byte."""
    if lead >= 0xF0:
        return 3
    if lead >= 0xE0:
        return 2
    if lead >= 0xC0:
        return 1
    return 0
