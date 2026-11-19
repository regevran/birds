"""Plain-text rendering of card views for the development client."""

from __future__ import annotations

from .grading import ElementResult, RecognizeResult
from .models import (
    CardView,
    ElementsCardView,
    LearnCardView,
    RecognizeCardView,
)


def render_card(
    view: CardView,
    *,
    reverse_hebrew: bool = True,
    reveal_elements: bool = False,
    element_answers: dict[str, str] | None = None,
    reveal_recognize: bool = False,
    recognize_answers: tuple[str, ...] = (),
    position: tuple[int, int] | None = None,
) -> str:
    label = _card_label(view, position)
    if isinstance(view, LearnCardView):
        return _render_learn(view, reverse_hebrew, label)
    if isinstance(view, ElementsCardView):
        return _render_elements(
            view, reverse_hebrew, reveal_elements, element_answers or {}, label
        )
    if isinstance(view, RecognizeCardView):
        return _render_recognize(
            view,
            reverse_hebrew,
            reveal_recognize,
            recognize_answers,
            label,
        )
    raise TypeError(f"cannot render {type(view).__name__}")


def _card_label(view: CardView, position: tuple[int, int] | None) -> str:
    suffix = f" {position[0]}/{position[1]}" if position else ""
    return f"[{view.card_type.value}{suffix}]"


def _he(text: str, reverse: bool) -> str:
    return text[::-1] if reverse else text


def _render_learn(view: LearnCardView, reverse: bool, label: str) -> str:
    status = view.status or "regular"
    categories = ", ".join(view.status_categories)
    family = view.family_he
    lines = [
        f"{label} {view.latin}",
        f"  Hebrew:  {_he(view.hebrew, reverse) if view.hebrew else '-'}",
        f"  English: {view.english}",
        f"  Family:  {view.family}"
        + (f" ({_he(family, reverse)})" if family else ""),
        f"  Order:   {view.order}",
        f"  Status:  {status} ({categories})",
    ]

    if view.parts:
        lines.append("  Parts:")
        for part in view.parts:
            lines.append(
                f"    {part.latin:<12} {part.element_id:<12} "
                f"{part.english} | {_he(part.hebrew, reverse)} | {part.theme}"
            )
    else:
        lines.append("  Parts:   (no etymology split)")

    if view.bridge:
        lines.append("  Bridge:")
        for match in view.bridge:
            lines.append(
                f"    {_he(match.hebrew, reverse)} <-> "
                f"{match.latin} ({match.english})"
            )

    if view.whole_names:
        lines.append("  Whole names:")
        for note in view.whole_names:
            lines.append(
                f"    {note.word}: {note.english} | "
                f"{_he(note.hebrew, reverse)} | {note.source}"
            )

    return "\n".join(lines)


def _render_elements(
    view: ElementsCardView,
    reverse: bool,
    reveal: bool,
    answers: dict[str, str],
    label: str,
) -> str:
    lines = [
        f"{label} {view.latin}",
        "  Choose the Hebrew meaning for each element.",
    ]
    for index, row in enumerate(view.rows):
        lines.append(render_element_row(view, index, reverse_hebrew=reverse))
        if reveal and row.element_id in answers:
            lines.append(f"     correct: {_he(answers[row.element_id], reverse)}")
    return "\n".join(lines)


def render_element_row(
    view: ElementsCardView, index: int, *, reverse_hebrew: bool = True
) -> str:
    """Render one numbered element row and a vertical numbered option list."""
    row = view.rows[index]
    latin_forms = ", ".join(row.latin_forms)
    options = "\n".join(
        f"       {number}) {_he(option, reverse_hebrew)}"
        for number, option in enumerate(row.options, start=1)
    )
    return (
        f"  {index + 1}. {latin_forms} ({row.element_id}) · theme: {row.theme}\n"
        f"{options}"
    )


def render_element_results(
    view: ElementsCardView,
    results: tuple[ElementResult, ...],
    *,
    reverse_hebrew: bool = True,
) -> str:
    """Render per-element feedback and the correct/total score."""
    labels = {
        row.element_id: ", ".join(row.latin_forms) for row in view.rows
    }
    lines: list[str] = []
    for result in results:
        label = labels.get(result.element_id, result.element_id)
        answer = _he(result.expected, reverse_hebrew)
        if result.correct:
            lines.append(f"  {label:<14} correct: {answer!r}")
        else:
            chosen = _he(result.chosen, reverse_hebrew)
            lines.append(
                f"  {label:<14} wrong: chose {chosen!r}, "
                f"correct {answer!r}"
            )
    correct = sum(result.correct for result in results)
    lines.append(f"  {correct}/{len(results)} correct.")
    return "\n".join(lines)


def _render_recognize(
    view: RecognizeCardView,
    reverse: bool,
    reveal: bool,
    answers: tuple[str, ...],
    label: str,
) -> str:
    lines = [
        f"{label} Which Latin name matches the Hebrew name?",
        f"  Hebrew: {_he(view.hebrew, reverse)}",
        "",
    ]
    for number, option in enumerate(view.options, start=1):
        lines.append(f"  {number}) {option.latin}")
    if reveal and answers:
        lines.append(f"  correct: {_join_latins(answers)}")
    return "\n".join(lines)


def render_recognize_result(result: RecognizeResult) -> str:
    """Render feedback for one R-card choice."""
    answer = _join_latins(result.accepted)
    if result.correct:
        return f"  correct: {answer}"
    return f"  wrong: chose {result.chosen.latin!r}, correct {answer}"


def _join_latins(latins: tuple[str, ...]) -> str:
    return " or ".join(repr(latin) for latin in latins)
