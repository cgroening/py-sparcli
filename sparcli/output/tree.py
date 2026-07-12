"""
sparcli.output.tree
===================

Defines :class:`Tree` and :class:`TreeNode`, hierarchical views drawn with
box-drawing connectors.

A tree renders each node's content on its own row, prefixed by ``├─``/``└─``
connectors taken from a border glyph set. Vertical ``│`` guides carry the branch
color down through nested descendants; they can be switched off, and the dash
count and connector style are configurable.
"""

from __future__ import annotations

from sparcli.core.border import BorderType
from sparcli.core.render import Renderable, Rendered
from sparcli.core.style import Style
from sparcli.core.text import IntoText, Line, Span, into_text
from sparcli.core.theme import theme

# A connector spans the branch glyph, its dashes and a trailing space.
_CONNECTOR_FIXED_CELLS = 2


class TreeNode:
    """
    A node in a :class:`Tree`.

    Attributes
    ----------
    content : Text
        The node's rich-text content.
    children : list[TreeNode]
        The node's direct children, drawn indented beneath it.
    """

    __slots__ = ("content", "children")

    def __init__(self, content: IntoText) -> None:
        self.content = into_text(content)
        self.children: list[TreeNode] = []

    def child(self, node: TreeNode) -> TreeNode:
        """Adds a child node and returns this node for chaining."""
        self.children.append(node)
        return self


class Tree(Renderable):
    """A tree of :class:`TreeNode` objects drawn with connector glyphs."""

    __slots__ = (
        "_roots",
        "_border",
        "_connector_style",
        "_dashes",
        "_guides",
    )

    def __init__(
        self,
        *,
        border: BorderType = BorderType.SINGLE,
        connector_style: Style | None = None,
        dashes: int = 1,
        guides: bool = True,
    ) -> None:
        self._roots: list[TreeNode] = []
        self._border = border
        self._connector_style = (
            connector_style
            if connector_style is not None
            else theme().secondary
        )
        self._dashes = dashes
        self._guides = guides

    def node(self, node: TreeNode) -> Tree:
        """Adds a top-level (root) node and returns the tree."""
        self._roots.append(node)
        return self

    def border(self, border: BorderType) -> Tree:
        """Sets the connector glyph set and returns the tree."""
        self._border = border
        return self

    def connector_style(self, style: Style) -> Tree:
        """Sets the connector style and returns the tree."""
        self._connector_style = style
        return self

    def dashes(self, dashes: int) -> Tree:
        """Sets the number of horizontal dashes per connector."""
        self._dashes = dashes
        return self

    def no_guides(self) -> Tree:
        """Disables the vertical continuation guides and returns the tree."""
        self._guides = False
        return self

    def render(self, max_width: int) -> Rendered:
        """Renders the tree; ``max_width`` is accepted but not constraining."""
        del max_width
        lines: list[Line] = []
        for root in self._roots:
            for content_line in root.content.lines:
                lines.append(Line(list(content_line.spans)))
            self._render_children(root.children, "", lines)
        return Rendered(lines)

    def _connector_width(self) -> int:
        """Returns the column width of a connector."""
        return _CONNECTOR_FIXED_CELLS + self._dashes

    def _render_children(
        self, children: list[TreeNode], prefix: str, lines: list[Line]
    ) -> None:
        """Renders the children of a node beneath ``prefix``."""
        chars = self._border.chars()
        dash = chars.horizontal * self._dashes
        for index, child in enumerate(children):
            last = index + 1 == len(children)
            branch = chars.bottom_left if last else chars.tee_right
            connector = f"{branch}{dash} "
            continuation = self._continuation(last)
            self._push_node_lines(child, prefix, connector, continuation, lines)
            child_prefix = f"{prefix}{continuation}"
            self._render_children(child.children, child_prefix, lines)

    def _push_node_lines(
        self,
        node: TreeNode,
        prefix: str,
        connector: str,
        continuation: str,
        lines: list[Line],
    ) -> None:
        """Emits the content lines of a single node."""
        for row, content_line in enumerate(node.content.lines):
            lead = connector if row == 0 else continuation
            spans: list[Span] = [
                Span.styled(prefix, self._connector_style),
                Span.styled(lead, self._connector_style),
            ]
            spans.extend(content_line.spans)
            lines.append(Line(spans))

    def _continuation(self, last: bool) -> str:
        """Returns the continuation cell shown under a node's connector."""
        width = self._connector_width()
        if last or not self._guides:
            return " " * width
        guide = self._border.chars().vertical
        return f"{guide}{" " * (width - 1)}"
