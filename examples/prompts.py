"""Interactive prompt examples covering every input widget.

Run it in a real terminal: ``python examples/prompts.py``. Each prompt runs in
turn; pressing Esc cancels that prompt and the demo reports it as cancelled
before moving on. The prompts need an interactive TTY, so the example prints a
notice and exits cleanly when standard input or output is redirected.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from sparcli import (
    Confirm,
    DatePicker,
    FuzzySelect,
    NumberInput,
    Outcome,
    PasswordInput,
    Renderable,
    Rendered,
    Select,
    Shortcut,
    Textarea,
    TextInput,
    event,
    is_input_tty,
    shortcut,
    validate,
)


class _Block(Renderable):
    """Wraps a pre-rendered block so the footer hint can be printed."""

    def __init__(self, block: Rendered) -> None:
        self._block = block

    def render(self, max_width: int) -> Rendered:
        return self._block


def report[T](
    label: str, outcome: Outcome[T], render: Callable[[T], str]
) -> None:
    """Prints a prompt's outcome as a submitted value, shortcut or cancel."""
    if outcome.is_submitted:
        print(f"{label}: {render(outcome.value)}")
    elif outcome.is_shortcut:
        print(f"{label}: shortcut #{outcome.shortcut_id}")
    else:
        print(f"{label}: cancelled")


def footer_hint() -> None:
    """Prints a footer-style key hint line above the prompts."""
    hints = [
        Shortcut(event.KeyPress.new(event.KeyCode.ENTER), 1, "submit"),
        Shortcut(event.KeyPress.new(event.KeyCode.ESC), 2, "cancel"),
    ]
    _Block(Rendered([shortcut.hint_line(hints)])).print()


def text_prompts() -> None:
    """A validated name field and a filtered username with history."""
    name = (
        TextInput("Your name?")
        .placeholder("e.g. Alice")
        .validate(validate.non_empty())
        .run()
    )
    report("name", name, lambda value: value)

    username = (
        TextInput("Username?")
        .char_filter(validate.alnum())
        .max_chars(16)
        .suggestions(["alice", "albert", "bob", "carol"])
        .history(["alice", "bob"])
        .run()
    )
    report("username", username, lambda value: value)


def secret_and_number() -> None:
    """A masked password and a number field with a calculator."""
    password = PasswordInput("Password?").mask("•").run()
    report("password", password, lambda value: "*" * len(value))

    age = (
        NumberInput("Age? (try `= 20 + 2`)")
        .range(0.0, 130.0)
        .calculator()
        .run()
    )
    report("age", age, lambda value: f"{value:.0f}")


def selections() -> None:
    """Single select, multi select and an inline fuzzy finder."""
    colors = ["red", "green", "blue"]
    color = Select("Favorite color?", options=colors).run()
    report("color", color, lambda index: colors[index])

    toppings = ["cheese", "mushroom", "olive", "onion"]
    picked = (
        Select("Pick toppings (Space to toggle):", options=toppings)
        .multi()
        .run_multi()
    )
    report(
        "toppings",
        picked,
        lambda indices: ", ".join(toppings[index] for index in indices),
    )

    fruits = ["apple", "apricot", "banana", "cherry", "grape"]
    fruit = FuzzySelect("Find a fruit:", options=fruits).run()
    report("fruit", fruit, lambda index: fruits[index])


def free_text_and_dates() -> None:
    """A multi-line textarea and a calendar date picker."""
    bio = Textarea("Short bio (Ctrl-D to submit):").run()
    report("bio", bio, lambda value: value.replace("\n", " / ") or "(empty)")

    picked = DatePicker("Pick a date:").run()
    report(
        "date",
        picked,
        lambda value: value.isoformat() if value is not None else "(no date)",
    )


def confirmation() -> None:
    """A yes/no confirmation with custom labels."""
    answer = (
        Confirm("Save everything?")
        .default_yes()
        .labels("Save", "Discard")
        .run()
    )
    report("save", answer, lambda value: "yes" if value else "no")


def main() -> None:
    """Runs each interactive prompt, or exits when there is no terminal."""
    if not is_input_tty():
        print("prompts.py needs an interactive terminal (TTY); nothing to do.")
        sys.exit(0)
    footer_hint()
    text_prompts()
    secret_and_number()
    selections()
    free_text_and_dates()
    confirmation()


if __name__ == "__main__":
    main()
