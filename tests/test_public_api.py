"""Tests guarding the flat public API surface re-exported from ``sparcli``."""

from __future__ import annotations

import sparcli
import sparcli.input


class TestPublicApi:
    def test_all_names_are_importable_attributes(self) -> None:
        # Every name promised by __all__ must resolve to a real attribute, so
        # the flat re-export never drifts from what is actually exported.
        missing = [
            name for name in sparcli.__all__ if not hasattr(sparcli, name)
        ]
        assert missing == []

    def test_all_has_no_duplicates(self) -> None:
        assert len(sparcli.__all__) == len(set(sparcli.__all__))

    def test_outcome_kind_is_re_exported_at_the_root(self) -> None:
        assert "OutcomeKind" in sparcli.__all__
        assert sparcli.OutcomeKind is sparcli.input.OutcomeKind
