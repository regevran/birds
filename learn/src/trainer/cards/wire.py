"""Deserialize Worker ``/app`` JSON into the card-layer dataclasses.

The Worker owns grading and card generation, so the text client receives card
views and feedback as JSON.  This module is the narrow bridge back into the
existing typed renderers; it contains no trainer rules.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..foundation.errors import InvalidRequest
from .results import ElementResult, LatinResult, RecognizeResult, WordResult
from .models import (
    BridgeMatch,
    CardType,
    CardView,
    ConstructCardView,
    ConstructPart,
    ElementRow,
    ElementsCardView,
    LearnCardView,
    LearnPart,
    ProduceCardView,
    RecognizeCardView,
    RecognizeOption,
    WholeNameNote,
)


def _mapping(value: Any, what: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidRequest(f"{what} must be an object")
    return value


def _list(value: Any, what: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise InvalidRequest(f"{what} must be a list")
    return value


def _text(data: Mapping[str, Any], key: str, what: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise InvalidRequest(f"{what}.{key} must be a string")
    return value


def _flag(data: Mapping[str, Any], key: str, what: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise InvalidRequest(f"{what}.{key} must be a boolean")
    return value


def _number(data: Mapping[str, Any], key: str, what: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidRequest(f"{what}.{key} must be an integer")
    return value


def _strings(value: Any, what: str) -> tuple[str, ...]:
    items = _list(value, what)
    if not all(isinstance(item, str) for item in items):
        raise InvalidRequest(f"{what} must contain strings")
    return tuple(items)


def _card_type(data: Mapping[str, Any]) -> CardType:
    raw = data.get("card_type")
    try:
        return CardType(raw)
    except ValueError as exc:
        raise InvalidRequest(f"unknown card type {raw!r}") from exc


def card_view_from_json(data: Any) -> CardView:
    """Build the matching card-view dataclass from a Worker JSON card."""
    card = _mapping(data, "card")
    kind = _card_type(card)
    if kind is CardType.L:
        return LearnCardView(
            card_type=kind,
            species_id=_text(card, "species_id", "L"),
            latin=_text(card, "latin", "L"),
            english=_text(card, "english", "L"),
            hebrew=_text(card, "hebrew", "L"),
            family=_text(card, "family", "L"),
            family_he=_text(card, "family_he", "L"),
            order=_text(card, "order", "L"),
            status=_text(card, "status", "L"),
            status_categories=_strings(
                card.get("status_categories"), "L.status_categories"
            ),
            parts=tuple(
                LearnPart(
                    latin=_text(part, "latin", "L.part"),
                    element_id=_text(part, "element_id", "L.part"),
                    english=_text(part, "english", "L.part"),
                    hebrew=_text(part, "hebrew", "L.part"),
                    theme=_text(part, "theme", "L.part"),
                )
                for part in (
                    _mapping(item, "L.part")
                    for item in _list(card.get("parts"), "L.parts")
                )
            ),
            bridge=tuple(
                BridgeMatch(
                    hebrew=_text(match, "hebrew", "L.bridge"),
                    latin=_text(match, "latin", "L.bridge"),
                    english=_text(match, "english", "L.bridge"),
                )
                for match in (
                    _mapping(item, "L.bridge")
                    for item in _list(card.get("bridge"), "L.bridge")
                )
            ),
            whole_names=tuple(
                WholeNameNote(
                    word=_text(note, "word", "L.whole_names"),
                    english=_text(note, "english", "L.whole_names"),
                    hebrew=_text(note, "hebrew", "L.whole_names"),
                    source=_text(note, "source", "L.whole_names"),
                )
                for note in (
                    _mapping(item, "L.whole_names")
                    for item in _list(
                        card.get("whole_names"), "L.whole_names"
                    )
                )
            ),
        )
    if kind is CardType.E:
        return ElementsCardView(
            card_type=kind,
            species_id=_text(card, "species_id", "E"),
            family=_text(card, "family", "E"),
            latin=_text(card, "latin", "E"),
            rows=tuple(
                ElementRow(
                    element_id=_text(row, "element_id", "E.row"),
                    latin_forms=_strings(
                        row.get("latin_forms"), "E.row.latin_forms"
                    ),
                    theme=_text(row, "theme", "E.row"),
                    options=_strings(row.get("options"), "E.row.options"),
                )
                for row in (
                    _mapping(item, "E.row")
                    for item in _list(card.get("rows"), "E.rows")
                )
            ),
        )
    if kind is CardType.R:
        return RecognizeCardView(
            card_type=kind,
            species_id=_text(card, "species_id", "R"),
            family=_text(card, "family", "R"),
            hebrew=_text(card, "hebrew", "R"),
            options=tuple(
                RecognizeOption(
                    latin=_text(option, "latin", "R.option"),
                    species_id=_text(option, "species_id", "R.option"),
                )
                for option in (
                    _mapping(item, "R.option")
                    for item in _list(card.get("options"), "R.options")
                )
            ),
        )
    if kind is CardType.C:
        return ConstructCardView(
            card_type=kind,
            species_id=_text(card, "species_id", "C"),
            family=_text(card, "family", "C"),
            hebrew=_text(card, "hebrew", "C"),
            genus_parts=_construct_parts(
                card.get("genus_parts"), "C.genus_parts"
            ),
            epithet_parts=_construct_parts(
                card.get("epithet_parts"), "C.epithet_parts"
            ),
        )
    if kind is CardType.F:
        return ProduceCardView(
            card_type=kind,
            species_id=_text(card, "species_id", "F"),
            family=_text(card, "family", "F"),
            hebrew=_text(card, "hebrew", "F"),
        )
    raise InvalidRequest(f"card type {kind.value} is not implemented")


def _construct_parts(value: Any, what: str) -> tuple[ConstructPart, ...]:
    return tuple(
        ConstructPart(
            hebrew=_text(part, "hebrew", what),
            first_letter=_text(part, "first_letter", what),
            length=_number(part, "length", what),
        )
        for part in (
            _mapping(item, what) for item in _list(value, what)
        )
    )


def element_results_from_json(data: Any) -> tuple[ElementResult, ...]:
    """Convert ``feedback.kind == "elements"`` results."""
    return tuple(
        ElementResult(
            element_id=_text(item, "element_id", "elements"),
            chosen=_text(item, "chosen", "elements"),
            expected=_text(item, "expected", "elements"),
            correct=_flag(item, "correct", "elements"),
        )
        for item in (
            _mapping(item, "elements")
            for item in _list(data, "elements")
        )
    )


def recognize_result_from_json(data: Any) -> RecognizeResult:
    """Convert ``feedback.kind == "recognize"``."""
    chosen = _mapping(data.get("chosen"), "recognize.chosen")
    return RecognizeResult(
        chosen=RecognizeOption(
            latin=_text(chosen, "latin", "recognize.chosen"),
            species_id=_text(chosen, "species_id", "recognize.chosen"),
        ),
        accepted=_strings(data.get("accepted"), "recognize.accepted"),
        correct=_flag(data, "correct", "recognize"),
    )


def latin_result_from_json(data: Any) -> LatinResult:
    """Convert ``feedback.kind == "latin"``."""
    return LatinResult(
        response=_text(data, "response", "latin"),
        expected=_text(data, "expected", "latin"),
        outcome=_text(data, "outcome", "latin"),
        genus_ok=_flag(data, "genus_ok", "latin"),
        epithet_ok=_flag(data, "epithet_ok", "latin"),
        distance=_number(data, "distance", "latin"),
        words=tuple(
            WordResult(
                expected=_text(word, "expected", "latin.word"),
                response=_text(word, "response", "latin.word"),
                status=_text(word, "status", "latin.word"),
                distance=_number(word, "distance", "latin.word"),
            )
            for word in (
                _mapping(item, "latin.word")
                for item in _list(data.get("words"), "latin.words")
            )
        ),
    )
