"""Grade answers against pure card views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..foundation.dataset import Catalog
from ..foundation.errors import InvalidRequest
from .models import ElementsCardView


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


__all__ = ["ElementResult", "grade_elements"]
