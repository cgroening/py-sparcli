"""
sparcli.output.table
=====================

Data tables with headers, footers, borders, alignment and wrapping.

Re-exports the public table types. :class:`Table` composes :class:`Column`
definitions and :class:`Cell` values into a bordered grid that honors
per-column alignment, min/max/fixed widths, word wrap, zebra striping, a title,
footer rows and horizontal or vertical cell spanning.
"""

from __future__ import annotations

from sparcli.output.table.table import Cell, Column, Table

__all__ = ["Cell", "Column", "Table"]
