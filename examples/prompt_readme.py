"""The input showcase collage embedded in the README.

Renders the static opening frame of every interactive prompt via its
``frame()`` method – no TTY and no interaction – and arranges them into a
titled panel above a multi-column dashboard. Capturing it with
``SPARCLI_NO_TTY=1 python examples/prompt_readme.py`` yields the exact
plain-text block the README quotes.
"""

from __future__ import annotations

from datetime import date

from sparcli import (
    Align,
    BorderType,
    Color,
    Columns,
    Confirm,
    DatePicker,
    FuzzySelect,
    Line,
    NumberInput,
    Panel,
    PasswordInput,
    Renderable,
    Rendered,
    Select,
    Style,
    Text,
    Textarea,
    TextInput,
    Title,
    vstack,
)


class _Block(Renderable):
    """Wraps a pre-rendered block so it can be printed like any widget."""

    def __init__(self, block: Rendered) -> None:
        self._block = block

    def render(self, max_width: int) -> Rendered:
        return self._block


def _blank() -> Rendered:
    """Returns a one-line blank spacer for vstacking."""
    return Rendered([Line()])


def hero(width: int) -> None:
    """Prints the top hero panel, sized to match the dashboard width."""
    accent = Style.new().with_fg(Color.CYAN).bold()
    body = Text(
        [
            Line.raw("Interactive prompts - confirm, select, text, password,"),
            Line.raw("number, textarea, fuzzy and date."),
        ]
    )
    Panel(body).border(BorderType.ROUNDED).border_style(
        Style.new().with_fg(Color.CYAN)
    ).title(
        Title.new(" sparcli - input widgets ")
        .with_align(Align.CENTER)
        .with_style(accent)
    ).content_align(Align.CENTER).width(width).print()


def left_column() -> Rendered:
    """Builds the confirm, text, password and number frames, stacked."""
    return vstack(
        [
            Confirm("Deploy to production?").default_yes().frame(),
            _blank(),
            TextInput("Service").initial("api-gateway").frame(),
            PasswordInput("Password").initial("hunter2").frame(),
            NumberInput("Replicas").initial(3.0).range(1.0, 10.0).frame(),
            TextInput("Email").placeholder("you@example.com").frame(),
            _blank(),
            Textarea("Notes").initial("first line\nsecond line").frame(),
        ],
        0,
    )


def middle_column() -> Rendered:
    """Builds the single- and multi-select frames, stacked."""
    single = (
        Select("Environment", options=["staging", "production", "local"])
        .cursor(1)
        .frame()
    )
    multi = (
        Select("Targets", options=["web", "api", "worker", "db"])
        .multi()
        .checked([0, 2])
        .frame()
    )
    return vstack([single, _blank(), multi], 0)


def right_column() -> Rendered:
    """Builds the date picker frame above an inline fuzzy finder frame."""
    picker = DatePicker("Release date").initial(date(2026, 5, 15)).frame()
    fuzzy = (
        FuzzySelect("Language", options=["Rust", "Ruby", "Python", "Go"])
        .query("ru")
        .frame()
    )
    return vstack([picker, _blank(), fuzzy], 0)


def dashboard() -> Rendered:
    """Builds the balanced three-column dashboard of prompt frames."""
    return (
        Columns()
        .add_rendered(left_column())
        .add_rendered(middle_column())
        .add_rendered(right_column())
        .gap(3)
        .separator(BorderType.SINGLE)
        .render(0)
    )


def main() -> None:
    """Prints the full input showcase collage."""
    print()
    board = dashboard()
    hero(board.width())
    print()
    _Block(board).print()


if __name__ == "__main__":
    main()
