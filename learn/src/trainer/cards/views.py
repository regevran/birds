"""Build pure, session-independent card views from the catalog."""

from __future__ import annotations

import random

from ..foundation.dataset import Bird, Catalog, Element, SplitPart
from ..foundation.errors import InvalidRequest
from .models import (
    BridgeMatch,
    CardDescriptor,
    CardType,
    CardView,
    ConstructCardView,
    ConstructPart,
    ElementRow,
    ElementsCardView,
    LearnCardView,
    LearnPart,
    RecognizeCardView,
    RecognizeOption,
    WholeNameNote,
)

_OPTION_COUNT = 5


def card_view(
    catalog: Catalog, descriptor: CardDescriptor, *, seed: int = 0
) -> CardView:
    """Build one card view.  No queue or session state is touched.

    The caller supplies ``seed``; it only permutes option order.
    """
    bird = catalog.bird(descriptor.species_id)
    if descriptor.card_type is CardType.L:
        return _learn_view(bird, catalog)
    if descriptor.card_type is CardType.E:
        return _elements_view(bird, catalog, seed)
    if descriptor.card_type is CardType.R:
        return _recognize_view(bird, catalog, seed)
    if descriptor.card_type is CardType.C:
        return _construct_view(bird, catalog)
    raise InvalidRequest(
        f"card type {descriptor.card_type.value} is not implemented yet"
    )


def _learn_view(bird: Bird, catalog: Catalog) -> LearnCardView:
    parts = _learn_parts(bird, catalog)
    return LearnCardView(
        card_type=CardType.L,
        species_id=bird.species_id,
        latin=bird.latin,
        english=bird.english,
        hebrew=bird.hebrew,
        family=bird.family,
        family_he=bird.family_he,
        order=bird.order,
        status=bird.status,
        status_categories=bird.status_categories,
        parts=parts,
        bridge=_bridge(bird, parts),
        whole_names=_whole_names(bird, catalog),
    )


def _elements_view(
    bird: Bird, catalog: Catalog, seed: int
) -> ElementsCardView:
    parts = _learn_parts(bird, catalog)
    if not parts:
        raise InvalidRequest(f"{bird.latin} has no split elements")

    order: list[str] = []
    latin_forms: dict[str, list[str]] = {}
    for part in parts:
        if part.element_id not in latin_forms:
            order.append(part.element_id)
            latin_forms[part.element_id] = []
        latin_forms[part.element_id].append(part.latin)

    rows = tuple(
        ElementRow(
            element_id=element_id,
            latin_forms=tuple(latin_forms[element_id]),
            theme=catalog.element(element_id).theme,
            options=_element_options(catalog, catalog.element(element_id), seed),
        )
        for element_id in order
    )
    return ElementsCardView(
        card_type=CardType.E,
        species_id=bird.species_id,
        latin=bird.latin,
        rows=rows,
    )


def _recognize_view(
    bird: Bird, catalog: Catalog, seed: int
) -> RecognizeCardView:
    if not bird.hebrew:
        raise InvalidRequest(f"{bird.latin} has no Hebrew name")

    accepted = catalog.birds_with_hebrew(bird.hebrew)
    accepted_ids = {other.species_id for other in accepted}
    wanted = max(0, _OPTION_COUNT - len(accepted))
    rng = random.Random(f"{seed}:{bird.species_id}:R")

    distractors: list[RecognizeOption] = []
    seen = set(accepted_ids)
    tiers = (
        catalog.genus(bird.genus),
        catalog.family(bird.family),
        catalog.order(bird.order),
        catalog.birds,
    )
    if wanted:
        for tier in tiers:
            candidates = sorted(tier, key=lambda other: other.species_id)
            rng.shuffle(candidates)
            for other in candidates:
                if other.species_id in seen:
                    continue
                seen.add(other.species_id)
                distractors.append(
                    RecognizeOption(
                        latin=other.latin,
                        species_id=other.species_id,
                    )
                )
                if len(distractors) == wanted:
                    break
            if len(distractors) == wanted:
                break

    options = [
        RecognizeOption(latin=other.latin, species_id=other.species_id)
        for other in accepted
    ]
    options.extend(distractors)
    rng.shuffle(options)
    return RecognizeCardView(
        card_type=CardType.R,
        species_id=bird.species_id,
        hebrew=bird.hebrew,
        options=tuple(options),
    )


def _construct_view(bird: Bird, catalog: Catalog) -> ConstructCardView:
    if not bird.hebrew:
        raise InvalidRequest(f"{bird.latin} has no Hebrew name")
    return ConstructCardView(
        card_type=CardType.C,
        species_id=bird.species_id,
        hebrew=bird.hebrew,
        genus_parts=_construct_parts(bird.genus, bird.genus_parts, catalog),
        epithet_parts=_construct_parts(
            bird.epithet, bird.epithet_parts, catalog
        ),
    )


def _construct_parts(
    word: str, parts: tuple[SplitPart, ...], catalog: Catalog
) -> tuple[ConstructPart, ...]:
    if not parts:
        return (ConstructPart(hebrew="", first_letter=word[0], length=len(word)),)
    return tuple(
        ConstructPart(
            hebrew=catalog.element(part.element_id).he,
            first_letter=part.latin[0],
            length=len(part.latin),
        )
        for part in parts
    )


def _learn_parts(bird: Bird, catalog: Catalog) -> tuple[LearnPart, ...]:
    parts: list[LearnPart] = []
    for part in (*bird.genus_parts, *bird.epithet_parts):
        element = catalog.element(part.element_id)
        parts.append(
            LearnPart(
                latin=part.latin,
                element_id=part.element_id,
                english=element.en,
                hebrew=element.he,
                theme=element.theme,
            )
        )
    return tuple(parts)


def _bridge(bird: Bird, parts: tuple[LearnPart, ...]) -> tuple[BridgeMatch, ...]:
    """Simple display-only bridge: element gloss appears in the Hebrew name."""
    if not bird.hebrew:
        return ()
    matches: list[BridgeMatch] = []
    seen: set[tuple[str, str]] = set()
    for part in parts:
        if not part.hebrew or part.hebrew not in bird.hebrew:
            continue
        key = (part.hebrew, part.latin)
        if key in seen:
            continue
        seen.add(key)
        matches.append(
            BridgeMatch(
                hebrew=part.hebrew,
                latin=part.latin,
                english=part.english,
            )
        )
    return tuple(matches)


def _whole_names(bird: Bird, catalog: Catalog) -> tuple[WholeNameNote, ...]:
    notes: list[WholeNameNote] = []
    for word in (bird.genus, bird.epithet):
        whole = catalog.whole_names.get(word)
        if whole is not None:
            notes.append(
                WholeNameNote(
                    word=word,
                    english=whole.en,
                    hebrew=whole.he,
                    source=whole.source,
                )
            )
    return tuple(notes)


def _element_options(
    catalog: Catalog, element: Element, seed: int
) -> tuple[str, ...]:
    """Correct gloss plus same-theme distractors, unique by gloss.

    The row shows the element's theme, so the options deliberately stay inside
    that theme: the theme is a hint, not decoration.  Small themes simply yield
    fewer than five options.
    """
    correct = element.he
    same_theme = sorted(
        (
            other for other in catalog.elements.values()
            if other.theme == element.theme
            and other.element_id != element.element_id
        ),
        key=lambda other: other.element_id,
    )

    distractors: list[str] = []
    seen = {correct}
    for other in same_theme:
        if other.he in seen:
            continue
        seen.add(other.he)
        distractors.append(other.he)

    # Seeding with a string is deterministic across runs (SHA-512 based).
    rng = random.Random(f"{seed}:{element.element_id}")
    rng.shuffle(distractors)
    chosen = distractors[: _OPTION_COUNT - 1]
    options = [correct, *chosen]
    rng.shuffle(options)
    return tuple(options)
