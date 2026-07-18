"""
sparcli.input.keydecode
=======================

Defines the byte-level primitives behind the terminal event source.

Reading keys off a terminal is byte arithmetic before it is anything else:
control-byte boundaries, UTF-8 lead bytes, CSI modifier masks and a readiness
poll with a timeout. None of that knows about logical keys, so it lives here
rather than in :mod:`sparcli.input.event`.

The dependency runs one way only: ``event`` imports these primitives, never the
other way round. The lookup tables that map sequences to :class:`KeyCode` values
stay in ``event`` precisely because they are made of key codes.
"""

from __future__ import annotations

import select

# Timeout (seconds) used to disambiguate a lone Esc from an escape sequence.
ESC_TIMEOUT = 0.05
# Timeout (seconds) used while draining a bracketed-paste payload.
PASTE_TIMEOUT = 0.2

# Byte offset that turns a Ctrl-letter control byte into its ASCII letter.
CTRL_LETTER_BASE = 0x60

# UTF-8 leading bytes, by how many continuation bytes they announce.
UTF8_LEAD_4 = 0xF0
UTF8_LEAD_3 = 0xE0
UTF8_LEAD_2 = 0xC0

# Control-byte boundaries the decoder compares against.
ESC_BYTE = 0x1B
TAB_BYTE = 0x09
CTRL_LETTER_MAX = 0x1A
FIRST_PRINTABLE = 0x20

# A CSI sequence ends at the first byte in this inclusive range.
CSI_FINAL_MIN = 0x40
CSI_FINAL_MAX = 0x7E

# Bits of a CSI modifier parameter, which encodes ``value - 1`` as a mask.
_MODIFIER_CTRL = 4
_MODIFIER_ALT = 2
_MODIFIER_SHIFT = 1


def decode_modifier(text: str) -> tuple[bool, bool, bool]:
    """
    Decodes a CSI modifier parameter into ``(ctrl, alt, shift)``.

    Parameters
    ----------
    text : str
        The raw parameter, which may be empty or malformed.

    Returns
    -------
    tuple[bool, bool, bool]
        The three modifier flags; all ``False`` when nothing parses.
    """
    if not text:
        return (False, False, False)
    try:
        mask = int(text) - 1
    except ValueError:
        return (False, False, False)
    return (
        bool(mask & _MODIFIER_CTRL),
        bool(mask & _MODIFIER_ALT),
        bool(mask & _MODIFIER_SHIFT),
    )


def poll_ready(fd: int, timeout: float) -> bool:
    """
    Returns whether ``fd`` has data ready within ``timeout`` seconds.

    Parameters
    ----------
    fd : int
        The file descriptor to poll.
    timeout : float
        How long to wait, in seconds.

    Returns
    -------
    bool
        ``True`` when data is readable; ``False`` on timeout or a closed fd.
    """
    try:
        ready, _, _ = select.select([fd], [], [], timeout)
    except (OSError, ValueError):
        return False
    return bool(ready)


def to_int(text: str) -> int:
    """
    Parses an integer, defaulting to ``0`` on failure.

    Parameters
    ----------
    text : str
        The digits to parse.

    Returns
    -------
    int
        The parsed value, or ``0`` when ``text`` is not a number.
    """
    try:
        return int(text)
    except ValueError:
        return 0


def utf8_continuation_count(lead: int) -> int:
    """
    Returns how many continuation bytes follow a UTF-8 leading byte.

    Parameters
    ----------
    lead : int
        The leading byte.

    Returns
    -------
    int
        ``0`` to ``3``; ``0`` for a plain ASCII byte.
    """
    if lead >= UTF8_LEAD_4:
        return 3
    if lead >= UTF8_LEAD_3:
        return 2
    if lead >= UTF8_LEAD_2:
        return 1
    return 0
