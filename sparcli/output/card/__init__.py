"""
sparcli.output.card
===================

A filled card: a colored surface with its own title and footer rows.

Re-exports :class:`Card`. Where :class:`~sparcli.output.panel.Panel` draws a
frame and embeds the title in the top border, a card is a surface: the
background carries the shape, an outer border is optional, and every color is
derived from a single accent through HSL.
"""

from __future__ import annotations

from sparcli.output.card.card import Card

__all__ = ["Card"]
