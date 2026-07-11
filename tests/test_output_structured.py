"""Tests for the structured output widgets: Tree, List and Diff."""

from __future__ import annotations

from sparcli.core.border import BorderType
from sparcli.core.render import Rendered
from sparcli.output.diff import MAX_DIFF_LINES, Diff
from sparcli.output.list import List, Marker, _to_alpha, _to_roman
from sparcli.output.tree import Tree, TreeNode


def lines_of(rendered: Rendered) -> list[str]:
    """Returns the plain text of each rendered line."""
    return [line.plain() for line in rendered.lines]


class TestTree:
    def test_renders_root_and_branches(self) -> None:
        tree = Tree().node(
            TreeNode("root").child(TreeNode("a")).child(TreeNode("b"))
        )
        lines = lines_of(tree.render(40))
        assert lines[0] == "root"
        assert lines[1] == "├─ a"
        assert lines[2] == "└─ b"

    def test_nested_children_show_guides(self) -> None:
        tree = Tree().node(
            TreeNode("root")
            .child(TreeNode("a").child(TreeNode("a1")))
            .child(TreeNode("b"))
        )
        lines = lines_of(tree.render(40))
        assert lines[1] == "├─ a"
        assert lines[2] == "│  └─ a1"
        assert lines[3] == "└─ b"

    def test_no_guides_replaces_verticals_with_spaces(self) -> None:
        tree = (
            Tree()
            .no_guides()
            .node(
                TreeNode("root")
                .child(TreeNode("a").child(TreeNode("a1")))
                .child(TreeNode("b"))
            )
        )
        lines = lines_of(tree.render(40))
        assert lines[2] == "   └─ a1"

    def test_dashes_widen_the_connector(self) -> None:
        tree = Tree().dashes(3).node(TreeNode("root").child(TreeNode("a")))
        lines = lines_of(tree.render(40))
        assert lines[1] == "└─── a"

    def test_border_type_changes_connector_glyphs(self) -> None:
        tree = Tree(border=BorderType.ASCII).node(
            TreeNode("root").child(TreeNode("a")).child(TreeNode("b"))
        )
        lines = lines_of(tree.render(40))
        assert lines[1] == "+- a"
        assert lines[2] == "+- b"

    def test_child_returns_the_same_node(self) -> None:
        node = TreeNode("root")
        assert node.child(TreeNode("leaf")) is node


class TestList:
    def test_bulleted_list_prefixes_each_item(self) -> None:
        lines = lines_of(List().item("a").item("b").render(40))
        assert lines == ["• a", "• b"]

    def test_custom_bullet_glyph(self) -> None:
        lines = lines_of(List().bullet("-").item("a").render(40))
        assert lines == ["- a"]

    def test_numbered_list_counts_items(self) -> None:
        lst = List.ordered(Marker.NUMBER).item("x").item("y")
        assert lines_of(lst.render(40)) == ["1. x", "2. y"]

    def test_alpha_lower_marker(self) -> None:
        lst = List.ordered(Marker.ALPHA_LOWER).item("x").item("y")
        assert lines_of(lst.render(40)) == ["a. x", "b. y"]

    def test_alpha_upper_marker(self) -> None:
        lst = List.ordered(Marker.ALPHA_UPPER).item("x")
        assert lines_of(lst.render(40)) == ["A. x"]

    def test_roman_lower_marker(self) -> None:
        lst = (
            List.ordered(Marker.ROMAN_LOWER)
            .item("a")
            .item("b")
            .item("c")
            .item("d")
        )
        assert lines_of(lst.render(40)) == [
            "i. a",
            "ii. b",
            "iii. c",
            "iv. d",
        ]

    def test_roman_upper_marker(self) -> None:
        lst = List.ordered(Marker.ROMAN_UPPER).item("a")
        assert lines_of(lst.render(40)) == ["I. a"]

    def test_nested_list_is_indented(self) -> None:
        child = List().item("child")
        lst = List().item_with("parent", child)
        lines = lines_of(lst.render(40))
        assert lines[0] == "• parent"
        assert lines[1].startswith("  • child")

    def test_multiline_item_hangs_under_content(self) -> None:
        lines = lines_of(List().item("first\nsecond").render(40))
        assert lines[0] == "• first"
        assert lines[1] == "  second"

    def test_item_gap_inserts_blank_lines(self) -> None:
        lines = lines_of(List().item_gap(1).item("a").item("b").render(40))
        assert lines == ["• a", "", "• b"]

    def test_to_alpha_is_bijective_base_26(self) -> None:
        assert _to_alpha(0, upper=False) == "a"
        assert _to_alpha(25, upper=False) == "z"
        assert _to_alpha(26, upper=False) == "aa"

    def test_to_roman_builds_numerals(self) -> None:
        assert _to_roman(4, upper=False) == "iv"
        assert _to_roman(9, upper=True) == "IX"


class TestDiff:
    def test_shows_added_and_removed_lines(self) -> None:
        diff = Diff("a\nb\nc", "a\nB\nc").no_header().context(1)
        lines = lines_of(diff.render(80))
        assert "- b" in lines
        assert "+ B" in lines
        assert "  a" in lines

    def test_header_shows_labels(self) -> None:
        diff = Diff("a", "b").labels("before", "after")
        lines = lines_of(diff.render(80))
        assert lines[0] == "--- before"
        assert lines[1] == "+++ after"

    def test_identical_input_has_no_changes(self) -> None:
        diff = Diff("x\ny", "x\ny").no_header()
        lines = lines_of(diff.render(80))
        assert all(not line.startswith("-") for line in lines)
        assert all(not line.startswith("+") for line in lines)

    def test_collapses_unchanged_regions_into_hunk_marker(self) -> None:
        old = "a\nb\nc\nd\ne\nf\ng"
        new = "a\nb\nc\nD\ne\nf\ng"
        lines = lines_of(Diff(old, new).no_header().context(1).render(80))
        assert "…" in lines
        assert "  c" in lines
        assert "- d" in lines
        assert "+ D" in lines
        assert "  e" in lines
        assert "  a" not in lines
        assert "  g" not in lines

    def test_large_input_falls_back_to_full_listing(self) -> None:
        big = "\n".join("same" for _ in range(MAX_DIFF_LINES + 1))
        lines = lines_of(Diff(big, "same").no_header().render(80))
        deletions = [line for line in lines if line.startswith("- ")]
        assert len(deletions) == MAX_DIFF_LINES + 1
        assert "+ same" in lines
        assert all(not line.startswith("  ") for line in lines)
