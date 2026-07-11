"""
sparcli.output.table.table
===========================

Defines the public table classes :class:`Table`, :class:`Column` and
:class:`Cell`.

A :class:`Table` lays out rows of :class:`Cell` values under a set of
:class:`Column` definitions, honoring per-column alignment, width constraints
and word wrap, plus zebra striping, a title, footer rows and horizontal or
vertical cell spanning. Each class offers both a keyword constructor and fluent
builder methods, so ``Column("Name").align(Align.RIGHT)`` reads like the Rust
original. The heavy lifting lives in :mod:`sparcli.output.table.plan` (grid and
width computation) and :mod:`sparcli.output.table.render` (line assembly).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from sparcli.core.border import BorderType
from sparcli.core.geometry import Align
from sparcli.core.render import Renderable, Rendered
from sparcli.core.style import Style
from sparcli.core.text import IntoText, Text, into_text
from sparcli.core.theme import theme


class Column:
    """
    A single table column definition.

    Attributes
    ----------
    header : Text
        The column header text.
    alignment : Align
        Horizontal alignment applied to header and body cells.
    width_min : int
        The minimum column width in columns.
    width_max : int | None
        The maximum column width, or ``None`` for unbounded.
    width_fixed : int | None
        A fixed column width that overrides the natural width.
    wrapping : bool
        Whether overflow reflows onto more lines instead of truncating.
    """

    __slots__ = (
        "header",
        "alignment",
        "width_min",
        "width_max",
        "width_fixed",
        "wrapping",
    )

    def __init__(
        self,
        *,
        header: IntoText = "",
        alignment: Align = Align.LEFT,
        width_min: int = 0,
        width_max: int | None = None,
        width_fixed: int | None = None,
        wrapping: bool = False,
    ) -> None:
        self.header: Text = into_text(header)
        self.alignment: Align = alignment
        self.width_min: int = width_min
        self.width_max: int | None = width_max
        self.width_fixed: int | None = width_fixed
        self.wrapping: bool = wrapping

    @classmethod
    def new(cls, header: IntoText) -> Column:
        """Returns a left-aligned column with the given header."""
        return cls(header=header)

    def align(self, align: Align) -> Column:
        """Sets the column alignment and returns the column."""
        self.alignment = align
        return self

    def min_width(self, width: int) -> Column:
        """Sets the minimum column width and returns the column."""
        self.width_min = width
        return self

    def max_width(self, width: int) -> Column:
        """Sets the maximum column width and returns the column."""
        self.width_max = width
        return self

    def fixed_width(self, width: int) -> Column:
        """Sets a fixed column width and returns the column."""
        self.width_fixed = width
        return self

    def wrap(self) -> Column:
        """Enables word wrapping instead of truncation and returns self."""
        self.wrapping = True
        return self


class Cell:
    """
    A single table cell.

    Attributes
    ----------
    content : Text
        The cell content.
    alignment : Align | None
        An override alignment, or ``None`` to inherit the column alignment.
    span_cols : int
        The number of columns the cell spans (at least ``1``).
    span_rows : int
        The number of rows the cell spans (at least ``1``).
    """

    __slots__ = ("content", "alignment", "span_cols", "span_rows")

    def __init__(
        self,
        *,
        content: IntoText = "",
        alignment: Align | None = None,
        span_cols: int = 1,
        span_rows: int = 1,
    ) -> None:
        self.content: Text = into_text(content)
        self.alignment: Align | None = alignment
        self.span_cols: int = max(span_cols, 1)
        self.span_rows: int = max(span_rows, 1)

    @classmethod
    def new(cls, content: IntoText) -> Cell:
        """Returns a cell holding ``content`` with no span."""
        return cls(content=content)

    def align(self, align: Align) -> Cell:
        """Overrides the cell alignment and returns the cell."""
        self.alignment = align
        return self

    def colspan(self, columns: int) -> Cell:
        """Spans the cell across ``columns`` columns and returns the cell."""
        self.span_cols = max(columns, 1)
        return self

    def rowspan(self, rows: int) -> Cell:
        """Spans the cell across ``rows`` rows and returns the cell."""
        self.span_rows = max(rows, 1)
        return self


IntoColumn = Column | IntoText
IntoCell = Cell | IntoText


def into_column(value: IntoColumn) -> Column:
    """Coerces a string, rich text or column into a :class:`Column`."""
    if isinstance(value, Column):
        return value
    return Column.new(value)


def into_cell(value: IntoCell) -> Cell:
    """Coerces a string, rich text or cell into a :class:`Cell`."""
    if isinstance(value, Cell):
        return value
    return Cell.new(value)


@dataclass(slots=True)
class Row:
    """A table row of cells, flagged as body or footer."""

    cells: list[Cell]
    footer: bool


@dataclass(slots=True)
class TableOpts:
    """The styling and layout options shared with the plan and renderer."""

    border: BorderType = BorderType.ROUNDED
    border_style: Style = field(default_factory=Style)
    header: bool = True
    header_style: Style = field(default_factory=Style)
    striped: bool = False
    stripe_style: Style = field(default_factory=lambda: Style().dim())
    title: Text | None = None
    title_style: Style = field(default_factory=Style)
    pad: int = 1
    row_separators: bool = False


@dataclass(slots=True)
class TableLayout:
    """The column definitions and options handed to plan and render."""

    columns: list[Column]
    opts: TableOpts


class Table(Renderable):
    """
    A data table with headers, footers, borders, alignment and wrapping.

    A table that fits the render width is left untouched; an overflowing one
    shrinks its flexible columns so its borders stay within the terminal.
    ``wrap`` columns reflow first, then the rest truncate; ``fixed_width``
    columns never shrink and no column falls below its ``min_width``.

    Examples
    --------
    >>> from sparcli.output.table import Table
    >>> out = (
    ...     Table()
    ...     .columns(["Name", "Status"])
    ...     .row(["web-1", "online"])
    ...     .render(40)
    ... )
    >>> "web-1" in out.plain()
    True
    """

    __slots__ = ("_columns", "_rows", "_opts")

    def __init__(
        self,
        *,
        border: BorderType | None = None,
        border_style: Style | None = None,
        header: bool = True,
        header_style: Style | None = None,
        striped: bool = False,
        stripe_style: Style | None = None,
        title: IntoText | None = None,
        title_style: Style | None = None,
        pad: int = 1,
        row_separators: bool = False,
    ) -> None:
        active = theme()
        self._columns: list[Column] = []
        self._rows: list[Row] = []
        self._opts = TableOpts(
            border=border if border is not None else active.border,
            border_style=(
                border_style if border_style is not None else active.secondary
            ),
            header=header,
            header_style=(
                header_style if header_style is not None else active.heading
            ),
            striped=striped,
            stripe_style=(
                stripe_style if stripe_style is not None else Style().dim()
            ),
            title=into_text(title) if title is not None else None,
            title_style=(
                title_style if title_style is not None else active.heading
            ),
            pad=pad,
            row_separators=row_separators,
        )

    def column(self, column: IntoColumn) -> Table:
        """Adds a column and returns the table."""
        self._columns.append(into_column(column))
        return self

    def columns(self, columns: Iterable[IntoColumn]) -> Table:
        """Adds several columns from an iterable and returns the table."""
        self._columns.extend(into_column(c) for c in columns)
        return self

    def row(self, cells: Iterable[IntoCell]) -> Table:
        """Adds a data row and returns the table."""
        self._rows.append(Row([into_cell(c) for c in cells], False))
        return self

    def footer_row(self, cells: Iterable[IntoCell]) -> Table:
        """Adds a footer row (drawn after a separator) and returns the table."""
        self._rows.append(Row([into_cell(c) for c in cells], True))
        return self

    def border(self, border: BorderType) -> Table:
        """Sets the border type and returns the table."""
        self._opts.border = border
        return self

    def border_style(self, style: Style) -> Table:
        """Sets the border glyph style and returns the table."""
        self._opts.border_style = style
        return self

    def header(self, show: bool) -> Table:
        """Enables or disables the header row and returns the table."""
        self._opts.header = show
        return self

    def header_style(self, style: Style) -> Table:
        """Sets the header row text style and returns the table."""
        self._opts.header_style = style
        return self

    def striped(self, striped: bool) -> Table:
        """Enables zebra striping of body rows and returns the table."""
        self._opts.striped = striped
        return self

    def stripe_style(self, style: Style) -> Table:
        """Sets the style used for striped rows and returns the table."""
        self._opts.stripe_style = style
        return self

    def title_style(self, style: Style) -> Table:
        """Sets the title text style and returns the table."""
        self._opts.title_style = style
        return self

    def title(self, title: IntoText) -> Table:
        """Sets a table title and returns the table."""
        self._opts.title = into_text(title)
        return self

    def pad(self, pad: int) -> Table:
        """Sets the horizontal cell padding and returns the table."""
        self._opts.pad = pad
        return self

    def row_separators(self, on: bool) -> Table:
        """Draws separators between body rows and returns the table."""
        self._opts.row_separators = on
        return self

    def render(self, max_width: int) -> Rendered:
        """Renders the table into at most ``max_width`` columns."""
        if not self._columns:
            return Rendered.empty()
        from sparcli.output.table.plan import build_plan, column_widths
        from sparcli.output.table.render import Builder

        layout = TableLayout(self._columns, self._opts)
        grid = build_plan(self._rows, len(self._columns))
        widths = column_widths(layout, grid, max_width)
        return Builder(layout, grid, widths).build()
