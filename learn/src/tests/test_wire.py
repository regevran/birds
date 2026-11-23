"""Tests for decoding Worker session JSON into card-layer dataclasses."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from trainer.cards.models import CardType, RecognizeOption
from trainer.cards.results import (
    ElementResult,
    LatinResult,
    RecognizeResult,
    WordResult,
)
from trainer.cards.wire import (
    card_view_from_json,
    element_results_from_json,
    latin_result_from_json,
    recognize_result_from_json,
)
from trainer.foundation.errors import InvalidRequest

FIXTURES = Path(__file__).with_name("fixtures") / "worker_cards.json"


class CardWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cards = json.loads(FIXTURES.read_text(encoding="utf-8"))

    def test_every_card_type_decodes(self) -> None:
        for kind, data in self.cards.items():
            with self.subTest(card_type=kind):
                view = card_view_from_json(data)
                self.assertEqual(view.card_type, CardType(kind))
                self.assertEqual(
                    view.species_id, "acrocephalus-agricola"
                )

    def test_typed_cards_have_no_latin_answer(self) -> None:
        for kind in ("C", "F"):
            view = card_view_from_json(self.cards[kind])
            self.assertFalse(hasattr(view, "latin"))

    def test_learn_card_keeps_the_full_name(self) -> None:
        view = card_view_from_json(self.cards["L"])
        self.assertEqual(view.latin, "Acrocephalus agricola")
        self.assertTrue(view.parts)

    def test_unknown_card_type_is_rejected(self) -> None:
        with self.assertRaises(InvalidRequest):
            card_view_from_json({"card_type": "V"})
        with self.assertRaises(InvalidRequest):
            card_view_from_json([])

    def test_missing_fields_are_rejected(self) -> None:
        with self.assertRaises(InvalidRequest):
            card_view_from_json({"card_type": "F", "species_id": "x"})
        with self.assertRaises(InvalidRequest):
            card_view_from_json(
                {
                    "card_type": "F",
                    "species_id": "x",
                    "hebrew": 3,
                }
            )


class FeedbackWireTests(unittest.TestCase):
    def test_element_results(self) -> None:
        results = element_results_from_json(
            [
                {
                    "element_id": "acro",
                    "chosen": "פסגה",
                    "expected": "פסגה",
                    "correct": True,
                }
            ]
        )
        self.assertEqual(
            results,
            (ElementResult("acro", "פסגה", "פסגה", True),),
        )

    def test_recognize_result(self) -> None:
        result = recognize_result_from_json(
            {
                "chosen": {
                    "latin": "Acrocephalus agricola",
                    "species_id": "acrocephalus-agricola",
                },
                "accepted": ["Acrocephalus agricola"],
                "correct": False,
            }
        )
        self.assertEqual(
            result,
            RecognizeResult(
                chosen=RecognizeOption(
                    "Acrocephalus agricola", "acrocephalus-agricola"
                ),
                accepted=("Acrocephalus agricola",),
                correct=False,
            ),
        )

    def test_latin_result(self) -> None:
        result = latin_result_from_json(
            {
                "response": "acrocephalus agricolo",
                "expected": "Acrocephalus agricola",
                "outcome": "near_miss",
                "genus_ok": True,
                "epithet_ok": False,
                "distance": 1,
                "words": [
                    {
                        "expected": "acrocephalus",
                        "response": "acrocephalus",
                        "status": "correct",
                        "distance": 0,
                    },
                    {
                        "expected": "agricola",
                        "response": "agricolo",
                        "status": "almost",
                        "distance": 1,
                    },
                ],
            }
        )
        self.assertEqual(
            result,
            LatinResult(
                response="acrocephalus agricolo",
                expected="Acrocephalus agricola",
                outcome="near_miss",
                genus_ok=True,
                epithet_ok=False,
                distance=1,
                words=(
                    WordResult("acrocephalus", "acrocephalus", "correct", 0),
                    WordResult("agricola", "agricolo", "almost", 1),
                ),
            ),
        )

    def test_malformed_feedback_is_rejected(self) -> None:
        with self.assertRaises(InvalidRequest):
            element_results_from_json({"nope": "nope"})
        with self.assertRaises(InvalidRequest):
            latin_result_from_json({"response": "x"})


if __name__ == "__main__":
    unittest.main()
