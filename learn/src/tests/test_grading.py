"""Tests for E-card answer grading."""

from __future__ import annotations

import unittest

from trainer.cards.grading import grade_elements
from trainer.cards.models import (
    CardDescriptor,
    CardType,
    ElementRow,
    ElementsCardView,
)
from trainer.cards.views import card_view
from trainer.foundation.config import Config
from trainer.foundation.dataset import load_catalog
from trainer.foundation.errors import InvalidRequest


class ElementGradingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = Config.default()
        cls.catalog = load_catalog(
            config.species_path, config.etymology_path
        )
        cls.view = card_view(
            cls.catalog,
            CardDescriptor(
                species_id="acrocephalus-agricola",
                card_type=CardType.E,
            ),
            seed=0,
        )

    def _correct_choices(self) -> dict[str, str]:
        return {
            row.element_id: self.catalog.element(row.element_id).he
            for row in self.view.rows
        }

    def test_all_correct(self) -> None:
        results = grade_elements(
            self.catalog, self.view, self._correct_choices()
        )
        self.assertEqual(len(results), len(self.view.rows))
        self.assertTrue(all(result.correct for result in results))

    def test_wrong_choice_reports_expected(self) -> None:
        choices = self._correct_choices()
        first = self.view.rows[0]
        expected = self.catalog.element(first.element_id).he
        wrong = next(option for option in first.options if option != expected)
        choices[first.element_id] = wrong

        results = grade_elements(self.catalog, self.view, choices)

        self.assertFalse(results[0].correct)
        self.assertEqual(results[0].chosen, wrong)
        self.assertEqual(results[0].expected, expected)

    def test_missing_choice_is_rejected(self) -> None:
        choices = self._correct_choices()
        choices.pop(self.view.rows[0].element_id)
        with self.assertRaises(InvalidRequest):
            grade_elements(self.catalog, self.view, choices)

    def test_unknown_element_is_rejected(self) -> None:
        choices = self._correct_choices()
        choices["nope"] = "x"
        with self.assertRaises(InvalidRequest):
            grade_elements(self.catalog, self.view, choices)

    def test_choice_must_be_an_option(self) -> None:
        choices = self._correct_choices()
        choices[self.view.rows[0].element_id] = "not an option"
        with self.assertRaises(InvalidRequest):
            grade_elements(self.catalog, self.view, choices)

    def test_shared_gloss_is_accepted(self) -> None:
        by_gloss: dict[str, list] = {}
        for element in self.catalog.elements.values():
            by_gloss.setdefault(element.he, []).append(element)
        pair = next(
            (
                elements
                for elements in by_gloss.values()
                if len(elements) > 1
            ),
            None,
        )
        self.assertIsNotNone(pair)
        element = pair[0]
        row = ElementRow(
            element_id=element.element_id,
            latin_forms=("Test",),
            theme=element.theme,
            options=(element.he, "other"),
        )
        view = ElementsCardView(
            card_type=CardType.E,
            species_id="test-test",
            latin="Test test",
            rows=(row,),
        )

        results = grade_elements(
            self.catalog, view, {element.element_id: element.he}
        )

        self.assertTrue(results[0].correct)


if __name__ == "__main__":
    unittest.main()
