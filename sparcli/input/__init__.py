"""
sparcli.input
=============

Interactive single-input prompts driven by an :class:`EventSource`.

Every prompt exposes ``run()`` (real terminal), ``run_with(source)`` (the
dependency-injection seam used by tests) and ``frame()`` (a static preview).
Prompts return an :class:`~sparcli.input.outcome.Outcome`. This package
re-exports the prompt classes and the command :class:`History`; the grouped
helpers stay reachable as the ``event``, ``validate`` and ``shortcut``
submodules.
"""

from sparcli.input.confirm import Confirm
from sparcli.input.datepicker import DatePicker
from sparcli.input.editor import edit_file
from sparcli.input.fuzzy import FuzzySelect
from sparcli.input.history import History
from sparcli.input.number import NumberInput
from sparcli.input.outcome import Outcome, OutcomeKind
from sparcli.input.password import PasswordInput
from sparcli.input.select import Select
from sparcli.input.shortcut import Shortcut
from sparcli.input.text import TextInput
from sparcli.input.textarea import Textarea

__all__ = [
    "Confirm",
    "DatePicker",
    "FuzzySelect",
    "History",
    "NumberInput",
    "Outcome",
    "OutcomeKind",
    "PasswordInput",
    "Select",
    "Shortcut",
    "TextInput",
    "Textarea",
    "edit_file",
]
