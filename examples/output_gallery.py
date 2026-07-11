"""A gallery of every static output widget.

Run it with ``python examples/output_gallery.py``. Everything here renders to a
fixed frame, so the output is deterministic and pipe-friendly: piping it
(``| cat``, ``> file``) or setting ``NO_COLOR=1`` yields plain text with no
escape codes. Time-based widgets (spinner animation, progress, multi-progress,
live, pager) live in the ``output_dynamic`` example instead.
"""

from __future__ import annotations

from sparcli import (
    Alert,
    Align,
    Badge,
    BorderType,
    Cell,
    Color,
    Column,
    Columns,
    Diff,
    Edges,
    KeyValue,
    Line,
    List,
    Marker,
    Panel,
    ProgressBar,
    ProgressStyle,
    Renderable,
    Rendered,
    Rule,
    Span,
    Spinner,
    Style,
    Table,
    Thresholds,
    Tree,
    TreeNode,
    align,
    markup,
    pad,
    vstack,
)


class _Block(Renderable):
    """Wraps a pre-rendered block so it can be printed like any widget."""

    def __init__(self, block: Rendered) -> None:
        self._block = block

    def render(self, max_width: int) -> Rendered:
        return self._block


def _print(block: Rendered) -> None:
    """Prints an already rendered block to stdout."""
    _Block(block).print()


def section(title: str) -> None:
    """Prints a left-aligned section header rule."""
    print()
    Rule.with_title(title).align(Align.LEFT).print()
    print()


def styled_text() -> None:
    """Styled spans, attributes, a hyperlink and optional markup."""
    Rule.with_title("sparcli output gallery").print()
    print()
    _print(
        Rendered(
            [
                Line(
                    [
                        Span.styled("bold ", Style.new().bold()),
                        Span.styled("dim ", Style.new().dim()),
                        Span.styled("italic ", Style.new().italic()),
                        Span.styled("red ", Style.new().with_fg(Color.RED)),
                        Span.styled(
                            "on-blue ", Style.new().with_bg(Color.BLUE)
                        ),
                        Span.raw("link: "),
                        Span.raw("sparcli").with_link(
                            "https://example.com/sparcli"
                        ),
                    ]
                )
            ]
        )
    )
    markup.markup_println(
        "[bold green]markup[/]: [#ff8800]orange[/] and `code`"
    )


def sections() -> None:
    """Rules in all three alignments and border styles."""
    section("Rules")
    Rule.with_title("left").align(Align.LEFT).border(BorderType.SINGLE).print()
    Rule.with_title("center").align(Align.CENTER).print()
    Rule.with_title("right").align(Align.RIGHT).border(BorderType.THICK).print()


def alerts() -> None:
    """All five alert kinds."""
    section("Alerts")
    Alert.info("Informational message.").print()
    Alert.debug("Diagnostic detail.").print()
    Alert.success("Everything imported.").print()
    Alert.warning("Low on disk space.").print()
    Alert.error("Connection refused.").print()


def panels() -> None:
    """Panels: borders, title/subtitle, fill and centered content."""
    section("Panels")
    Panel("Rounded border (default).").print()
    Panel("Double border.").border(BorderType.DOUBLE).print()
    Panel("Centered, filled, fixed width.").border(BorderType.THICK).title(
        "Title"
    ).subtitle("subtitle").content_align(Align.CENTER).fill(
        Style.new().with_bg(Color.indexed(236))
    ).width(40).print()


def tables() -> None:
    """Tables: colspan plus striping, and a footer with a wrapping column."""
    section("Tables")
    Table().title("Servers").columns(["Name", "Region", "Status"]).row(
        ["web-1", "eu-west", "online"]
    ).row(["db-1", "eu-west", "online"]).row(
        [Cell.new("maintenance window").colspan(3).align(Align.CENTER)]
    ).striped(True).print()
    print()
    Table().columns(
        [
            Column.new("Item").align(Align.LEFT),
            Column.new("Note").wrap().max_width(24),
        ]
    ).row(["alpha", "a long note that wraps across several lines nicely"]).row(
        ["beta", "short note"]
    ).footer_row([Cell.new("2 items").colspan(2).align(Align.RIGHT)]).border(
        BorderType.ASCII
    ).print()


def lists_and_trees() -> None:
    """Lists in several marker styles, plus a tree."""
    section("Lists & trees")
    List.ordered(Marker.NUMBER).item("First step").item_with(
        "Second step", List().item("detail a").item("detail b")
    ).item("Third step").print()
    print()
    List.ordered(Marker.ALPHA_LOWER).item("alpha").item("beta").print()
    List.ordered(Marker.ROMAN_UPPER).item("one").item("two").print()
    print()
    Tree().node(
        TreeNode("project")
        .child(TreeNode("src").child(TreeNode("main.py")))
        .child(TreeNode("pyproject.toml"))
    ).print()


def key_values_and_badges() -> None:
    """Key-value list and inline badges."""
    section("Key-value & badges")
    KeyValue().add("Version", "0.1.0").add("License", "MIT").print()
    print()
    _print(
        Rendered(
            [
                Line(
                    [
                        Badge("PASS")
                        .style(Style.new().with_fg(Color.GREEN).bold())
                        .span(),
                        Span.raw(" "),
                        Badge("WARN")
                        .style(Style.new().with_fg(Color.YELLOW).bold())
                        .span(),
                        Span.raw(" "),
                        Badge("v0.1").caps("(", ")").span(),
                    ]
                )
            ]
        )
    )


def progress_and_spinner() -> None:
    """Progress bars in every style, a threshold bar and a spinner frame."""
    section("Progress & spinner")
    styles = [
        ("block", ProgressStyle.BLOCK),
        ("ascii", ProgressStyle.ASCII),
        ("line", ProgressStyle.LINE),
        ("shaded", ProgressStyle.SHADED),
    ]
    for label, style in styles:
        _print(ProgressBar().style(style).label(label).width(20).bar(6.0, 10.0))
    thresholds = Thresholds(
        mid=0.5,
        high=0.8,
        low_color=Color.GREEN,
        mid_color=Color.YELLOW,
        high_color=Color.RED,
    )
    _print(
        ProgressBar()
        .thresholds(thresholds)
        .label("load")
        .width(20)
        .bar(9.0, 10.0)
    )
    _print(Spinner("spinner (static frame)").frame())


def diff_and_columns() -> None:
    """A colored diff and a two-column layout."""
    section("Diff & columns")
    Diff(
        "line one\nline two\nline three",
        "line one\nline 2\nline three",
    ).print()
    print()
    left = Panel("left").render(20)
    right = Panel("right").render(20)
    Columns().add_rendered(left).add_rendered(right).gap(3).separator(
        BorderType.SINGLE
    ).print()


def composition() -> None:
    """Composition helpers: align, pad and vstack."""
    section("Composition (align / pad / vstack)")
    block = Rendered([Line.raw("aligned right")])
    _print(align(block, 30, Align.RIGHT))
    print()
    _print(pad(Rendered([Line.raw("padded")]), Edges.all(1)))
    print()
    first = Rendered([Line.raw("first block")])
    second = Rendered([Line.raw("second block")])
    _print(vstack([first, second], 1))


def main() -> None:
    """Prints the full gallery of static output widgets."""
    styled_text()
    sections()
    alerts()
    panels()
    tables()
    lists_and_trees()
    key_values_and_badges()
    progress_and_spinner()
    diff_and_columns()
    composition()


if __name__ == "__main__":
    main()
