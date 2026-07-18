"""
sparcli.output.diff
===================

Defines :class:`Diff`, a colored unified diff between two texts.

Lines are matched with a longest-common-subsequence edit script and emitted as
equal (``  ``), deleted (``- ``) or inserted (``+ ``) rows. Unchanged regions
beyond a context window collapse into a ``…`` hunk marker, and a ``--- old`` /
``+++ new`` header precedes the body unless it is disabled. Very large inputs
fall back to a plain delete-then-insert listing.
"""

from __future__ import annotations

import enum

from sparcli.core.color import Color
from sparcli.core.render import Renderable, Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line
from sparcli.core.theme import theme

# Default number of unchanged context lines kept around each change.
DEFAULT_CONTEXT = 3
# Maximum lines per side before falling back to a full listing.
MAX_DIFF_LINES = 5000


class _OpKind(enum.Enum):
    """The kind of a single line operation in the edit script."""

    EQUAL = enum.auto()
    DELETE = enum.auto()
    INSERT = enum.auto()


# The two-character gutter prefix for each operation kind.
_OP_PREFIX: dict[_OpKind, str] = {
    _OpKind.EQUAL: "  ",
    _OpKind.DELETE: "- ",
    _OpKind.INSERT: "+ ",
}


class _Op:
    """A single line operation carrying its kind and text."""

    __slots__ = ("kind", "text")

    def __init__(self, kind: _OpKind, text: str) -> None:
        self.kind = kind
        self.text = text


class Diff(Renderable):
    """A unified, colored diff between an ``old`` and a ``new`` text."""

    __slots__ = (
        "_add_style",
        "_context",
        "_del_style",
        "_hunk_style",
        "_new",
        "_new_label",
        "_no_header",
        "_old",
        "_old_label",
    )

    def __init__(
        self,
        old: str,
        new: str,
        *,
        context: int = DEFAULT_CONTEXT,
        no_header: bool = False,
        old_label: str = "old",
        new_label: str = "new",
        add_style: Style | None = None,
        del_style: Style | None = None,
        hunk_style: Style | None = None,
    ) -> None:
        self._old = old
        self._new = new
        self._context = context
        self._no_header = no_header
        self._old_label = old_label
        self._new_label = new_label
        self._add_style = (
            add_style
            if add_style is not None
            else Style.from_color(Color.GREEN)
        )
        self._del_style = (
            del_style if del_style is not None else Style.from_color(Color.RED)
        )
        self._hunk_style = (
            hunk_style if hunk_style is not None else theme().secondary
        )

    def context(self, lines: int) -> Diff:
        """Sets the number of context lines around changes."""
        self._context = lines
        return self

    def no_header(self) -> Diff:
        """Hides the ``---``/``+++`` header and returns the diff."""
        self._no_header = True
        return self

    def labels(self, old: str, new: str) -> Diff:
        """Sets the old and new side labels and returns the diff."""
        self._old_label = old
        self._new_label = new
        return self

    def render(self, max_width: int) -> Rendered:
        """
        Renders the diff; ``max_width`` is accepted but not constraining.

        Parameters
        ----------
        max_width : int
            The number of columns available for the block.

        Returns
        -------
        Rendered
            The laid-out block of styled lines.
        """
        del max_width
        old = _split_lines(self._old)
        new = _split_lines(self._new)
        ops = _diff_ops(old, new)
        lines: list[Line] = []
        if not self._no_header:
            self._push_header(lines)
        self._push_ops(lines, ops)
        return Rendered(lines)

    def _push_header(self, lines: list[Line]) -> None:
        """Pushes the ``--- old`` / ``+++ new`` header lines."""
        lines.append(Line.styled(f"--- {self._old_label}", self._del_style))
        lines.append(Line.styled(f"+++ {self._new_label}", self._add_style))

    def _push_ops(self, lines: list[Line], ops: list[_Op]) -> None:
        """Pushes the diff body, collapsing unchanged regions to context."""
        visible = _mark_visible(ops, self._context)
        last_visible = False
        for index, op in enumerate(ops):
            if not visible[index]:
                last_visible = False
                continue
            if not last_visible and index > 0:
                lines.append(Line.styled("…", self._hunk_style))
            lines.append(self._format_op(op))
            last_visible = True

    def _format_op(self, op: _Op) -> Line:
        """Formats a single operation as a styled line."""
        text = f"{_OP_PREFIX[op.kind]}{op.text}"
        if op.kind is _OpKind.EQUAL:
            return Line.raw(text)
        style = (
            self._del_style if op.kind is _OpKind.DELETE else self._add_style
        )
        return Line.styled(text, style)


def _split_lines(text: str) -> list[str]:
    """Splits ``text`` into lines the way Rust's ``str::lines`` does."""
    if not text:
        return []
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts.pop()
    return [part.removesuffix("\r") for part in parts]


def _mark_visible(ops: list[_Op], context: int) -> list[bool]:
    """Marks which ops are visible given the surrounding context window."""
    visible = [False] * len(ops)
    for index, op in enumerate(ops):
        if op.kind is _OpKind.EQUAL:
            continue
        start = max(0, index - context)
        end = min(index + context + 1, len(ops))
        for cursor in range(start, end):
            visible[cursor] = True
    return visible


def _diff_ops(old: list[str], new: list[str]) -> list[_Op]:
    """Computes a line-based edit script using an LCS table."""
    if len(old) > MAX_DIFF_LINES or len(new) > MAX_DIFF_LINES:
        return _fallback_ops(old, new)
    table = _lcs_table(old, new)
    return _backtrack(table, old, new)


def _lcs_table(old: list[str], new: list[str]) -> list[list[int]]:
    """Builds the longest-common-subsequence length table."""
    table = [[0] * (len(new) + 1) for _ in range(len(old) + 1)]
    for i in range(len(old) - 1, -1, -1):
        for j in range(len(new) - 1, -1, -1):
            if old[i] == new[j]:
                table[i][j] = table[i + 1][j + 1] + 1
            else:
                table[i][j] = max(table[i + 1][j], table[i][j + 1])
    return table


def _backtrack(
    table: list[list[int]], old: list[str], new: list[str]
) -> list[_Op]:
    """Backtracks the LCS table into an ordered edit script."""
    ops: list[_Op] = []
    i = 0
    j = 0
    while i < len(old) and j < len(new):
        if old[i] == new[j]:
            ops.append(_Op(_OpKind.EQUAL, old[i]))
            i += 1
            j += 1
        elif table[i + 1][j] >= table[i][j + 1]:
            ops.append(_Op(_OpKind.DELETE, old[i]))
            i += 1
        else:
            ops.append(_Op(_OpKind.INSERT, new[j]))
            j += 1
    ops.extend(_Op(_OpKind.DELETE, line) for line in old[i:])
    ops.extend(_Op(_OpKind.INSERT, line) for line in new[j:])
    return ops


def _fallback_ops(old: list[str], new: list[str]) -> list[_Op]:
    """Returns a naive diff for large inputs: delete all, then insert all."""
    ops: list[_Op] = [_Op(_OpKind.DELETE, line) for line in old]
    ops.extend(_Op(_OpKind.INSERT, line) for line in new)
    return ops
