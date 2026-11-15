"""Plain-text rendering of card views for the development client."""

from __future__ import annotations

from .grading import ElementResult
from .models import CardView, ElementsCardView, LearnCardView


def render_card(
    view: CardView,
    *,
    reverse_hebrew: bool = True,
    reveal_elements: bool = False,
    element_answers: dict[str, str] | None = None,
) -> str:
    if isinstance(view, LearnCardView):
        return _render_learn(view, reverse_hebrew)
    if isinstance(view, ElementsCardView):
        return _render_elements(
            view, reverse_hebrew, reveal_elements, element_answers or {}
        )
    raise TypeError(f"cannot render {type(view).__name__}")


def _he(text: str, reverse: bool) -> str:
    return text[::-1] if reverse else text


def _render_learn(view: LearnCardView, reverse: bool) -> str:
    status = view.status or "regular"
    categories = ", ".join(view.status_categories)
    family = view.family_he
    lines = [
        f"[L] {view.latin}",
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
) -> str:
    lines = [
        f"[E] {view.latin}",
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
