"""Grading results returned by the Worker and rendered by the text client.

These dataclasses are client-side view models.  The Worker owns grading; it
returns JSON that ``cards.wire`` decodes into these objects.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import RecognizeOption


@dataclass(frozen=True)
class ElementResult:
    """The graded outcome of one element choice on an E card."""

    element_id: str  # e.g. "acro"
    chosen: str  # e.g. "פסגה"
    expected: str  # e.g. "פסגה"
    correct: bool  # e.g. True


@dataclass(frozen=True)
class RecognizeResult:
    """The graded outcome of one R-card choice."""

    chosen: RecognizeOption  # e.g. RecognizeOption("Acrocephalus arundinaceus", "acrocephalus-arundinaceus")
    accepted: tuple[str, ...]  # e.g. ("Acrocephalus agricola",)
    correct: bool  # e.g. False


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
