"""Grade answers against pure card views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..foundation.dataset import Catalog
from ..foundation.errors import InvalidRequest
from ..foundation.normalize import normalize_latin
from .models import ElementsCardView, RecognizeCardView, RecognizeOption


@dataclass(frozen=True)
class ElementResult:
    """The graded outcome of one element choice on an E card."""

    element_id: str  # e.g. "acro"
    chosen: str  # e.g. "פסגה"
    expected: str  # e.g. "פסגה"
    correct: bool  # e.g. True


def grade_elements(
    catalog: Catalog,
    view: ElementsCardView,
    choices: Mapping[str, str],
) -> tuple[ElementResult, ...]:
    """Grade one gloss choice per element; each choice must be an option.

    A gloss is accepted when it equals the element's Hebrew meaning.  Glosses
    are shared between some elements, so the comparison is by gloss, not by
    the element that owns it.
    """
    expected_ids = [row.element_id for row in view.rows]
    missing = set(expected_ids) - set(choices)
    if missing:
        raise InvalidRequest(
            f"missing choices for: {', '.join(sorted(missing))}"
        )
    extra = set(choices) - set(expected_ids)
    if extra:
        raise InvalidRequest(
            f"choices for unknown elements: {', '.join(sorted(extra))}"
        )

    results: list[ElementResult] = []
    for row in view.rows:
        chosen = choices[row.element_id]
        if chosen not in row.options:
            raise InvalidRequest(
                f"{chosen!r} is not an option for element "
                f"{row.element_id!r}"
            )
        expected = catalog.element(row.element_id).he
        results.append(
            ElementResult(
                element_id=row.element_id,
                chosen=chosen,
                expected=expected,
                correct=chosen == expected,
            )
        )
    return tuple(results)


@dataclass(frozen=True)
class RecognizeResult:
    """The graded outcome of one R-card choice."""

    chosen: RecognizeOption  # e.g. RecognizeOption("Acrocephalus arundinaceus", "acrocephalus-arundinaceus")
    accepted: tuple[str, ...]  # e.g. ("Acrocephalus agricola",)
    correct: bool  # e.g. False


def grade_recognize(
    catalog: Catalog,
    view: RecognizeCardView,
    chosen_species_id: str,
) -> RecognizeResult:
    """Grade one Latin-name choice; every species with the prompt is correct."""
    chosen = next(
        (
            option
            for option in view.options
            if option.species_id == chosen_species_id
        ),
        None,
    )
    if chosen is None:
        raise InvalidRequest(
            f"{chosen_species_id!r} is not an option for species "
            f"{view.species_id!r}"
        )

    accepted_birds = catalog.birds_with_hebrew(view.hebrew)
    accepted_ids = {bird.species_id for bird in accepted_birds}
    return RecognizeResult(
        chosen=chosen,
        accepted=tuple(bird.latin for bird in accepted_birds),
        correct=chosen_species_id in accepted_ids,
    )


@dataclass(frozen=True)
class WordResult:
    """The graded outcome of one word in a typed Latin name."""

    expected: str  # e.g. "pygmeus"
    response: str  # e.g. "pygemus"
    status: str  # e.g. "almost"; one of "correct", "almost", "wrong"
    distance: int  # e.g. 1


@dataclass(frozen=True)
class LatinResult:
    """The graded outcome of a typed Latin name."""

    response: str  # e.g. "acrocephalus agrikola"
    expected: str  # e.g. "Acrocephalus agricola"
    outcome: str  # e.g. "near_miss"; one of "correct", "near_miss", "wrong"
    genus_ok: bool  # e.g. True
    epithet_ok: bool  # e.g. False
    distance: int  # e.g. 1
    words: tuple[WordResult, ...]  # e.g. (WordResult("agricola", "agrikola", "almost", 1),)


def grade_latin(expected: str, response: str) -> LatinResult:
    """Grade a typed Latin name after normalization."""
    normalized_expected = normalize_latin(expected)
    normalized_response = normalize_latin(response)
    expected_words = normalized_expected.split()
    response_words = normalized_response.split()

    words: list[WordResult] = []
    if len(expected_words) == len(response_words):
        for expected_word, response_word in zip(
            expected_words, response_words
        ):
            distance = _damerau_levenshtein(
                expected_word, response_word
            )
            words.append(
                WordResult(
                    expected=expected_word,
                    response=response_word,
                    status=_word_status(
                        expected_word, response_word, distance
                    ),
                    distance=distance,
                )
            )
    else:
        for index, expected_word in enumerate(expected_words):
            response_word = (
                response_words[index]
                if index < len(response_words)
                else ""
            )
            if response_word:
                distance = _damerau_levenshtein(
                    expected_word, response_word
                )
                status = _word_status(
                    expected_word, response_word, distance
                )
            else:
                distance = len(expected_word)
                status = "wrong"
            words.append(
                WordResult(
                    expected=expected_word,
                    response=response_word,
                    status=status,
                    distance=distance,
                )
            )

    genus_ok = bool(words) and words[0].status == "correct"
    epithet_ok = len(words) > 1 and words[1].status == "correct"

    if len(expected_words) != len(response_words):
        distance = _damerau_levenshtein(
            normalized_expected, normalized_response
        )
        outcome = "wrong"
    else:
        distance = sum(word.distance for word in words)
        first_letters_match = all(
            word.expected[0] == word.response[0]
            for word in words
            if word.expected and word.response
        )
        if distance == 0:
            outcome = "correct"
        elif distance <= 2 and first_letters_match:
            outcome = "near_miss"
        else:
            outcome = "wrong"

    return LatinResult(
        response=normalized_response,
        expected=expected,
        outcome=outcome,
        genus_ok=genus_ok,
        epithet_ok=epithet_ok,
        distance=distance,
        words=tuple(words),
    )


def _word_status(
    expected: str, response: str, distance: int
) -> str:
    if expected == response:
        return "correct"
    if (
        distance <= 2
        and expected
        and response
        and expected[0] == response[0]
    ):
        return "almost"
    return "wrong"


def _damerau_levenshtein(left: str, right: str) -> int:
    """Optimal-string-alignment distance with adjacent transpositions."""
    if not left:
        return len(right)
    if not right:
        return len(left)

    before_previous = [0] * (len(right) + 1)
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index] + [0] * len(right)
        for right_index, right_char in enumerate(right, start=1):
            cost = 0 if left_char == right_char else 1
            current[right_index] = min(
                current[right_index - 1] + 1,
                previous[right_index] + 1,
                previous[right_index - 1] + cost,
            )
            if (
                left_index > 1
                and right_index > 1
                and left_char == right[right_index - 2]
                and left[left_index - 2] == right_char
            ):
                current[right_index] = min(
                    current[right_index],
                    before_previous[right_index - 2] + 1,
                )
        before_previous, previous = previous, current
    return previous[-1]


__all__ = [
    "ElementResult",
    "LatinResult",
    "RecognizeResult",
    "WordResult",
    "grade_elements",
    "grade_latin",
    "grade_recognize",
]
