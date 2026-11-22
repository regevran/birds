"""Plain-text rendering of card views for the development client."""

from __future__ import annotations

from .grading import ElementResult, LatinResult, RecognizeResult
from .models import (
    CardView,
    ConstructCardView,
    ConstructPart,
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
    reveal_construct: bool = False,
    construct_answer: str = "",
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
    if isinstance(view, ConstructCardView):
        return _render_construct(
            view,
            reverse_hebrew,
            reveal_construct,
            construct_answer,
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


def _render_construct(
    view: ConstructCardView,
    reverse: bool,
    reveal: bool,
    answer: str,
    label: str,
) -> str:
    lines = [
        f"{label} Which Latin name matches the Hebrew name?",
        f"  Hebrew:   {_he(view.hebrew, reverse)}",
        f"  Scaffold: {_render_scaffold(view, reverse)}",
    ]
    if reveal and answer:
        lines.append(f"  correct: {answer!r}")
    return "\n".join(lines)


def _render_scaffold(view: ConstructCardView, reverse: bool) -> str:
    words = " ".join(
        (
            _scaffold_word(view.genus_parts),
            _scaffold_word(view.epithet_parts),
        )
    )
    legend = ", ".join(
        _scaffold_legend_part(part, reverse)
        for part in (*view.genus_parts, *view.epithet_parts)
    )
    return f"{words} ({legend})"


def _scaffold_word(parts: tuple[ConstructPart, ...]) -> str:
    return "".join(
        f"{part.first_letter}{'·' * max(0, part.length - 1)}"
        for part in parts
    )


def _scaffold_legend_part(part: ConstructPart, reverse: bool) -> str:
    if part.hebrew:
        return f"{part.length} {_he(part.hebrew, reverse)}"
    return str(part.length)


def render_construct_result(result: LatinResult) -> str:
    """Render feedback for a typed Latin answer."""
    if result.outcome == "correct":
        return f"  correct: {result.expected!r}"

    label = "almost" if result.outcome == "near_miss" else "wrong"
    lines = [
        f"  {label}: chose {result.response!r}, "
        f"correct {result.expected!r}"
    ]

    for index, word in enumerate(result.words):
        if word.status == "correct" or word.distance > 3:
            continue
        role = _word_role(index)
        lines.append(f"  {role}:")
        lines.append(f"    expected: {word.expected}")
        if word.response:
            lines.append(f"    chose:    {word.response}")
            lines.append(
                " " * 14
                + _difference_markers(word.expected, word.response)
            )
        else:
            lines.append("    chose:    (missing)")

    for index, word in enumerate(result.words):
        role = f"{_word_role(index)}:"
        statuses = "  ".join(
            f"[{value}]" if value == word.status else value
            for value in ("correct", "almost", "wrong")
        )
        lines.append(f"  {role:<9} {statuses}")

    return "\n".join(lines)


def _word_role(index: int) -> str:
    if index == 0:
        return "genus"
    if index == 1:
        return "epithet"
    return f"word {index + 1}"


def _difference_markers(expected: str, response: str) -> str:
    """Underline the region that differs, compiler-style.

    The shared prefix and suffix are skipped; every response character
    between them gets a caret, so a swap such as ``pygmeus``/``pygemus``
    produces ``^^`` under ``em`` rather than two isolated carets.
    """
    limit = min(len(expected), len(response))
    prefix = 0
    while prefix < limit and expected[prefix] == response[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < limit - prefix
        and expected[-1 - suffix] == response[-1 - suffix]
    ):
        suffix += 1

    markers = [" "] * len(response)
    middle = len(response) - prefix - suffix
    if middle:
        for position in range(prefix, prefix + middle):
            markers[position] = "^"
    elif markers:
        # The response is missing characters: point at where they belong.
        markers[min(prefix, len(markers) - 1)] = "^"
    return "".join(markers).rstrip()
