"""
Every color comes from the theme.

No color literal may appear in the package outside the files in ``ALLOWED``,
each listed with its reason. Comments and docstrings are not scanned.
"""

from __future__ import annotations

import re
from pathlib import Path

PACKAGE = Path(__file__).parent.parent / "sparcli"

# Files that may hold color values, and why.
ALLOWED: dict[str, str] = {
    "core/color.py": "the color type, its names and the xterm palette",
    "core/theme.py": "the built-in theme",
}

# A named color constant, an RGB literal or a quoted `#rgb`/`#rrggbb` string.
LITERAL = re.compile(
    r"Color\.(BLACK|RED|GREEN|YELLOW|BLUE|MAGENTA|CYAN|GRAY|DARK_GRAY|WHITE"
    r"|LIGHT_[A-Z]+)\b"
    r"|Color\.rgb\(\s*\d"
    r"|[\"']#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})[\"']"
)

TRIPLE_QUOTES = ('"""', "'''")


def test_colors_come_only_from_the_theme() -> None:
    found = [
        f"{path.relative_to(PACKAGE)}:{number}: {line.strip()}"
        for path in sorted(PACKAGE.rglob("*.py"))
        if path.relative_to(PACKAGE).as_posix() not in ALLOWED
        for number, line in code_lines(path)
        if LITERAL.search(line)
    ]
    assert not found, "color literals outside the theme:\n" + "\n".join(found)


def code_lines(path: Path) -> list[tuple[int, str]]:
    """Returns the numbered lines of `path` outside comments and docstrings."""
    lines: list[tuple[int, str]] = []
    in_docstring = False
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        quotes = sum(stripped.count(mark) for mark in TRIPLE_QUOTES)
        if in_docstring or stripped.startswith(TRIPLE_QUOTES):
            # An odd count opens or closes a docstring spanning lines.
            if quotes % 2 == 1:
                in_docstring = not in_docstring
            continue
        if stripped.startswith("#"):
            continue
        lines.append((number, line))
    return lines
