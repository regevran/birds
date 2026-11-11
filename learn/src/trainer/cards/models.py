"""Card identities and pure client-facing views.

Only L and E views are implemented so far.  The remaining card types are
listed now so the identity type does not change when they are added.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CardType(str, Enum):
    """The six kinds of card in a learning chain."""

    L = "L"  # learn, e.g. show the full name and its parts
    E = "E"  # elements, e.g. choose the gloss for "Acro"
    R = "R"  # recognize, e.g. Hebrew name -> choose the Latin name
    C = "C"  # construct, e.g. Hebrew name -> type the Latin with scaffolds
    F = "F"  # produce, e.g. Hebrew name -> type the Latin unaided
    V = "V"  # review, e.g. an F card shown again when due


@dataclass(frozen=True)
class CardDescriptor:
    """One requested card: a species and a card type."""

    species_id: str  # e.g. "acrocephalus-agricola"
    card_type: CardType  # e.g. CardType.L


@dataclass(frozen=True)
class LearnPart:
    """One written piece of a Latin name with its meaning and theme."""

    latin: str  # e.g. "Acro"
    element_id: str  # e.g. "acro"
    english: str  # e.g. "summit, peak"
    hebrew: str  # e.g. "פסגה"
    theme: str  # e.g. "Shape"


@dataclass(frozen=True)
class BridgeMatch:
    """One element gloss that also appears in the Hebrew name."""

    hebrew: str  # e.g. "שדה"
    latin: str  # e.g. "arv"
    english: str  # e.g. "field"


@dataclass(frozen=True)
class WholeNameNote:
    """One Latin word with a known meaning that is not split into elements."""

    word: str  # e.g. "syriacus"
    english: str  # e.g. "Syrian"
    hebrew: str  # e.g. "סורי"
    source: str  # e.g. "Jobling 2010"


@dataclass(frozen=True)
class LearnCardView:
    """A complete L-card display: names, classification, parts and notes."""

    card_type: CardType  # e.g. CardType.L
    species_id: str  # e.g. "acrocephalus-agricola"
    latin: str  # e.g. "Acrocephalus agricola"
    english: str  # e.g. "Paddyfield warbler"
    hebrew: str  # e.g. "קנית אורז"
    family: str  # e.g. "Acrocephalidae"
    family_he: str  # e.g. "קניתיים"
    order: str  # e.g. "Passeriformes"
    status: str  # e.g. "A"
    status_categories: tuple[str, ...]  # e.g. ("accidental",)
    parts: tuple[LearnPart, ...]  # e.g. (LearnPart("Acro", "acro", "summit, peak", "פסגה", "Shape"),)
    bridge: tuple[BridgeMatch, ...]  # e.g. (BridgeMatch("שדה", "arv", "field"),)
    whole_names: tuple[WholeNameNote, ...]  # e.g. (WholeNameNote("syriacus", "Syrian", "סורי", "Jobling 2010"),)


@dataclass(frozen=True)
class ElementRow:
    """One element on an E card: its spellings, theme and options."""

    element_id: str  # e.g. "acro"
    latin_forms: tuple[str, ...]  # e.g. ("Acro",)
    theme: str  # e.g. "Shape"
    options: tuple[str, ...]  # e.g. ("פטל", "מעל", "פסגה", "שייך ל", "גדה")


@dataclass(frozen=True)
class ElementsCardView:
    """A complete E-card display: the bird and one row per element."""

    card_type: CardType  # e.g. CardType.E
    species_id: str  # e.g. "acrocephalus-agricola"
    latin: str  # e.g. "Acrocephalus agricola"
    rows: tuple[ElementRow, ...]  # e.g. (ElementRow("acro", ("Acro",), "Shape", ("פטל", ...)),)


CardView = LearnCardView | ElementsCardView  # e.g. LearnCardView(...) or ElementsCardView(...)
