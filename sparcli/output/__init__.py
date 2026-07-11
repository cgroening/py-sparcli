"""
sparcli.output
=============

Printable widgets that render styled blocks to the terminal.

Every widget implements :class:`~sparcli.core.render.Renderable`. This package
re-exports the full set for flat imports; the composition helpers
:func:`align`, :func:`pad` and :func:`vstack` stack and place rendered blocks.
"""

from sparcli.output.alert import Alert, AlertKind
from sparcli.output.badge import Badge
from sparcli.output.columns import Columns
from sparcli.output.compose import align, pad, vstack
from sparcli.output.diff import Diff
from sparcli.output.kv import KeyValue
from sparcli.output.list import List, Marker
from sparcli.output.live import Live
from sparcli.output.multiprogress import MultiProgress
from sparcli.output.pager import Pager
from sparcli.output.panel import Panel
from sparcli.output.progress import ProgressBar, ProgressStyle, Thresholds
from sparcli.output.rule import Rule
from sparcli.output.spinner import Spinner, SpinnerStyle
from sparcli.output.table import Cell, Column, Table
from sparcli.output.tree import Tree, TreeNode

__all__ = [
    "Alert",
    "AlertKind",
    "Badge",
    "Cell",
    "Column",
    "Columns",
    "Diff",
    "KeyValue",
    "List",
    "Live",
    "Marker",
    "MultiProgress",
    "Pager",
    "Panel",
    "ProgressBar",
    "ProgressStyle",
    "Rule",
    "Spinner",
    "SpinnerStyle",
    "Table",
    "Thresholds",
    "Tree",
    "TreeNode",
    "align",
    "pad",
    "vstack",
]
