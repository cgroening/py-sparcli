"""
The output showcase collage embedded in the README.

Prints a titled hero panel, a three-column dashboard (table | list + tree |
key-value + badges) and a progress bar. Everything is deterministic, so
capturing it with ``SPARCLI_NO_TTY=1 python examples/output_readme.py`` yields
the exact plain-text block the README quotes.
"""

from __future__ import annotations

from sparcli import (
    Align,
    Badge,
    BorderType,
    Cell,
    Color,
    Column,
    Columns,
    KeyValue,
    Line,
    List,
    Marker,
    Panel,
    ProgressBar,
    Renderable,
    Rendered,
    Span,
    Style,
    Table,
    Text,
    Title,
    Tree,
    TreeNode,
    vstack,
)


class _Block(Renderable):
    """Wraps a pre-rendered block so it can be printed like any widget."""

    def __init__(self, block: Rendered) -> None:
        self._block = block

    def render(self, max_width: int) -> Rendered:
        return self._block


def _blank() -> Rendered:
    """Returns a one-line blank spacer for vstacking."""
    return Rendered([Line()])


def hero(width: int) -> None:
    """Prints the top hero panel, sized to match the dashboard width."""
    cyan = Style.new().with_fg(Color.CYAN).bold()
    yellow = Style.new().with_fg(Color.YELLOW).bold()
    body = Text(
        [
            Line(
                [
                    Span.raw("A dependency-free Python library for "),
                    Span.styled("styled output", cyan),
                ]
            ),
            Line(
                [
                    Span.raw("and "),
                    Span.styled("input", yellow),
                    Span.raw(" - panels, tables, trees, lists and more."),
                ]
            ),
        ]
    )
    Panel(body).border(BorderType.ROUNDED).border_style(
        Style.new().with_fg(Color.CYAN)
    ).title(
        Title.new(" sparcli ").with_align(Align.CENTER).with_style(cyan)
    ).content_align(Align.CENTER).width(width).print()


def overview_table() -> Rendered:
    """Builds the striped, row-separated 'Overview' table column."""

    def status(text: str, color: Color) -> Cell:
        return Cell.new(Text.styled(text, Style.new().with_fg(color).bold()))

    return (
        Table()
        .title("Overview")
        .title_style(Style.new().with_fg(Color.MAGENTA).bold())
        .border(BorderType.ROUNDED)
        .border_style(Style.new().with_fg(Color.MAGENTA))
        .header_style(Style.new().with_fg(Color.CYAN).bold())
        .striped(True)
        .row_separators(True)
        .columns(
            [
                Column.new("Service"),
                Column.new("Status").align(Align.CENTER),
                Column.new("Uptime").align(Align.RIGHT),
            ]
        )
        .row([Cell.new("api"), status("OK", Color.GREEN), Cell.new("99.98%")])
        .row([Cell.new("auth"), status("OK", Color.GREEN), Cell.new("99.91%")])
        .row(
            [
                Cell.new("billing"),
                status("WARN", Color.YELLOW),
                Cell.new("97.4%"),
            ]
        )
        .render(34)
    )


def middle_column() -> Rendered:
    """Builds a numbered list stacked above a project tree."""
    steps = (
        List.ordered(Marker.NUMBER)
        .marker_style(Style.new().with_fg(Color.YELLOW).bold())
        .item("Compose widgets side by side")
        .item("Capture, pad and align them")
        .item("Render to any UTF-8 terminal")
        .render(30)
    )
    tree = (
        Tree()
        .dashes(2)
        .connector_style(Style.new().with_fg(Color.CYAN))
        .node(
            TreeNode("project/")
            .child(
                TreeNode("api/")
                .child(TreeNode("routes.py"))
                .child(TreeNode("auth.py"))
            )
            .child(TreeNode("worker.py"))
        )
        .render(24)
    )
    return vstack([steps, _blank(), tree], 0)


def right_column() -> Rendered:
    """Builds a key-value block above a row of colored badges."""
    kv = (
        KeyValue()
        .key_style(Style.new().with_fg(Color.CYAN).bold())
        .add("host", "localhost")
        .add("port", "8080")
        .add("scheme", "https")
        .render(22)
    )

    def badge(text: str, color: Color) -> Span:
        return (
            Badge(text)
            .pad(1)
            .style(Style.new().with_fg(Color.BLACK).with_bg(color).bold())
            .span()
        )

    badges = Rendered(
        [
            Line(
                [
                    badge("DONE", Color.GREEN),
                    Span.raw(" "),
                    badge("INFO", Color.LIGHT_BLUE),
                ]
            ),
            Line(),
            Line(
                [
                    badge("WARN", Color.YELLOW),
                    Span.raw(" "),
                    badge("FAIL", Color.RED),
                ]
            ),
        ]
    )
    return vstack([kv, _blank(), badges], 0)


def dashboard() -> Rendered:
    """Builds the three-column dashboard row."""
    return (
        Columns()
        .add_rendered(overview_table())
        .add_rendered(middle_column())
        .add_rendered(right_column())
        .gap(3)
        .separator(BorderType.SINGLE)
        .render(0)
    )


def progress() -> None:
    """Prints the bottom progress bar."""
    _Block(
        ProgressBar()
        .label("Building")
        .fill_color(Color.GREEN)
        .caps("[", "]")
        .width(29)
        .show_value(True)
        .bar(92.0, 100.0)
    ).print()


def main() -> None:
    """Prints the full output showcase collage."""
    print()
    board = dashboard()
    hero(board.width())
    print()
    _Block(board).print()
    print()
    progress()


if __name__ == "__main__":
    main()
