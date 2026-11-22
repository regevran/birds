"""Tests for the pure L/E card views and their text rendering."""

from __future__ import annotations

import unittest

from trainer.cards.models import (
    CardDescriptor,
    CardType,
    ConstructCardView,
    ConstructPart,
    ElementsCardView,
    LearnCardView,
    ProduceCardView,
    RecognizeCardView,
)
from trainer.cards.grading import grade_latin
from trainer.cards.text import render_card, render_latin_result
from trainer.cards.views import card_view
from trainer.foundation.config import Config
from trainer.foundation.dataset import load_catalog
from trainer.foundation.errors import InvalidRequest, NotFound


class CardViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = Config.default()
        cls.catalog = load_catalog(
            config.species_path, config.etymology_path
        )

    def _view(self, species_id: str, card_type: CardType, seed: int = 0):
        return card_view(
            self.catalog,
            CardDescriptor(species_id=species_id, card_type=card_type),
            seed=seed,
        )

    def test_learn_view_full_parts(self) -> None:
        view = self._view("acrocephalus-agricola", CardType.L)
        self.assertIsInstance(view, LearnCardView)
        self.assertEqual(view.latin, "Acrocephalus agricola")
        self.assertEqual(
            [part.latin for part in view.parts],
            ["Acro", "cephalus", "agri", "cola"],
        )
        self.assertEqual(
            [part.element_id for part in view.parts],
            ["acro", "cephalus", "agri", "cola"],
        )
        self.assertTrue(all(part.english for part in view.parts))

    def test_learn_view_without_parts(self) -> None:
        view = self._view("turdus-merula", CardType.L)
        self.assertIsInstance(view, LearnCardView)
        self.assertEqual(view.parts, ())

    def test_elements_view(self) -> None:
        view = self._view("acrocephalus-agricola", CardType.E)
        self.assertIsInstance(view, ElementsCardView)
        self.assertEqual(
            [row.element_id for row in view.rows],
            ["acro", "cephalus", "agri", "cola"],
        )
        for row in view.rows:
            correct = self.catalog.element(row.element_id).he
            self.assertIn(correct, row.options)
            self.assertEqual(len(row.options), len(set(row.options)))
            self.assertGreaterEqual(len(row.options), 2)
            self.assertLessEqual(len(row.options), 5)
            theme_glosses = {
                element.he
                for element in self.catalog.elements.values()
                if element.theme == row.theme
            }
            self.assertTrue(set(row.options) <= theme_glosses)

    def test_elements_options_are_seeded(self) -> None:
        first = self._view("acrocephalus-agricola", CardType.E, seed=7)
        second = self._view("acrocephalus-agricola", CardType.E, seed=7)
        self.assertEqual(
            [row.options for row in first.rows],
            [row.options for row in second.rows],
        )

    def test_no_elements_for_unsplit_species(self) -> None:
        with self.assertRaises(InvalidRequest):
            self._view("turdus-merula", CardType.E)

    def test_unsupported_card_type(self) -> None:
        with self.assertRaises(InvalidRequest):
            self._view("acrocephalus-agricola", CardType.V)

    def test_text_render_learn(self) -> None:
        view = self._view("acrocephalus-agricola", CardType.L)
        text = render_card(view, reverse_hebrew=False)
        self.assertIn("[L] Acrocephalus agricola", text)
        self.assertIn("Acro", text)
        self.assertIn("English:", text)

    def test_text_render_elements(self) -> None:
        view = self._view("acrocephalus-agricola", CardType.E)
        text = render_card(
            view,
            reverse_hebrew=False,
            reveal_elements=True,
            element_answers={
                row.element_id: self.catalog.element(row.element_id).he
                for row in view.rows
            },
        )
        self.assertIn("[E] Acrocephalus agricola", text)
        self.assertIn("theme:", text)
        self.assertIn("1) ", text)
        self.assertIn("correct:", text)

    def test_unknown_bird(self) -> None:
        with self.assertRaises(NotFound):
            self._view("no-such-bird", CardType.L)


class RecognizeViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = Config.default()
        cls.catalog = load_catalog(
            config.species_path, config.etymology_path
        )

    def _view(self, species_id: str, seed: int = 0):
        return card_view(
            self.catalog,
            CardDescriptor(
                species_id=species_id,
                card_type=CardType.R,
            ),
            seed=seed,
        )

    def test_recognize_view(self) -> None:
        view = self._view("acrocephalus-agricola")
        self.assertIsInstance(view, RecognizeCardView)
        self.assertEqual(view.hebrew, "קנית אורז")
        self.assertEqual(len(view.options), 5)
        latins = [option.latin for option in view.options]
        self.assertEqual(len(latins), len(set(latins)))
        self.assertIn("Acrocephalus agricola", latins)
        for option in view.options:
            bird = self.catalog.bird(option.species_id)
            self.assertEqual(option.latin, bird.latin)
            self.assertEqual(bird.genus, "Acrocephalus")

    def test_options_are_seeded(self) -> None:
        first = self._view("acrocephalus-agricola", seed=7)
        second = self._view("acrocephalus-agricola", seed=7)
        self.assertEqual(first.options, second.options)

    def test_no_hebrew_is_rejected(self) -> None:
        with self.assertRaises(InvalidRequest):
            self._view("butorides-striata")

    def test_shared_hebrew_includes_both_species(self) -> None:
        view = self._view("oenanthe-lugens")
        latins = {option.latin for option in view.options}
        self.assertIn("Oenanthe lugens", latins)
        self.assertIn("Oenanthe warriae", latins)
        self.assertEqual(len(view.options), 5)

    def test_render_hides_latin_header(self) -> None:
        view = self._view("acrocephalus-agricola")
        text = render_card(view, reverse_hebrew=False)
        self.assertTrue(text.startswith("[R] Which Latin name matches"))
        self.assertNotIn("[R] Acrocephalus agricola", text)
        self.assertIn("Hebrew:", text)
        self.assertIn("Acrocephalus agricola", text)

    def test_render_reveal(self) -> None:
        view = self._view("oenanthe-lugens")
        text = render_card(
            view,
            reverse_hebrew=False,
            reveal_recognize=True,
            recognize_answers=("Oenanthe lugens", "Oenanthe warriae"),
        )
        self.assertIn("correct:", text)
        self.assertIn("Oenanthe lugens", text)
        self.assertIn("Oenanthe warriae", text)

    def test_render_position(self) -> None:
        view = self._view("acrocephalus-agricola")
        text = render_card(
            view, reverse_hebrew=False, position=(2, 5)
        )
        self.assertTrue(text.startswith("[R 2/5]"))


class ConstructViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = Config.default()
        cls.catalog = load_catalog(
            config.species_path, config.etymology_path
        )

    def _view(self, species_id: str):
        return card_view(
            self.catalog,
            CardDescriptor(
                species_id=species_id,
                card_type=CardType.C,
            ),
            seed=0,
        )

    def test_construct_view(self) -> None:
        view = self._view("acrocephalus-agricola")
        self.assertIsInstance(view, ConstructCardView)
        self.assertEqual(view.hebrew, "קנית אורז")
        self.assertEqual(
            [
                (part.hebrew, part.first_letter, part.length)
                for part in view.genus_parts
            ],
            [("פסגה", "A", 4), ("ראש", "c", 8)],
        )
        self.assertEqual(
            [
                (part.hebrew, part.first_letter, part.length)
                for part in view.epithet_parts
            ],
            [("שדה", "a", 4), ("שוכן", "c", 4)],
        )

    def test_construct_view_without_parts(self) -> None:
        view = self._view("turdus-merula")
        self.assertIsInstance(view, ConstructCardView)
        self.assertEqual(
            view.genus_parts,
            (ConstructPart(hebrew="", first_letter="T", length=6),),
        )
        self.assertEqual(
            view.epithet_parts,
            (ConstructPart(hebrew="", first_letter="m", length=6),),
        )

    def test_no_hebrew_is_rejected(self) -> None:
        with self.assertRaises(InvalidRequest):
            self._view("butorides-striata")

    def test_render_hides_latin(self) -> None:
        view = self._view("acrocephalus-agricola")
        text = render_card(view, reverse_hebrew=False)
        self.assertTrue(
            text.startswith("[C] Which Latin name matches")
        )
        self.assertNotIn("Acrocephalus", text)
        self.assertNotIn("agricola", text)
        self.assertIn(
            "Scaffold: A···c······· a···c··· "
            "(4 פסגה, 8 ראש, 4 שדה, 4 שוכן)",
            text,
        )

    def test_render_unsplit_scaffold(self) -> None:
        view = self._view("turdus-merula")
        text = render_card(view, reverse_hebrew=False)
        self.assertIn("Scaffold: T····· m····· (6, 6)", text)

    def test_render_reveal(self) -> None:
        view = self._view("acrocephalus-agricola")
        text = render_card(
            view,
            reverse_hebrew=False,
            reveal_construct=True,
            construct_answer="Acrocephalus agricola",
        )
        self.assertIn("correct: 'Acrocephalus agricola'", text)

    def test_render_position(self) -> None:
        view = self._view("acrocephalus-agricola")
        text = render_card(
            view, reverse_hebrew=False, position=(2, 5)
        )
        self.assertTrue(text.startswith("[C 2/5]"))


class ProduceViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = Config.default()
        cls.catalog = load_catalog(
            config.species_path, config.etymology_path
        )

    def _view(self, species_id: str):
        return card_view(
            self.catalog,
            CardDescriptor(
                species_id=species_id,
                card_type=CardType.F,
            ),
            seed=0,
        )

    def test_produce_view(self) -> None:
        view = self._view("acrocephalus-agricola")
        self.assertIsInstance(view, ProduceCardView)
        self.assertEqual(view.hebrew, "קנית אורז")
        self.assertEqual(view.species_id, "acrocephalus-agricola")

    def test_no_hebrew_is_rejected(self) -> None:
        with self.assertRaises(InvalidRequest):
            self._view("butorides-striata")

    def test_render_hides_latin(self) -> None:
        view = self._view("acrocephalus-agricola")
        text = render_card(view, reverse_hebrew=False)
        self.assertTrue(
            text.startswith("[F] Type the Latin name for the Hebrew name.")
        )
        self.assertIn("Hebrew:   קנית אורז", text)
        self.assertNotIn("Acrocephalus", text)
        self.assertNotIn("agricola", text)

    def test_render_reveal(self) -> None:
        view = self._view("acrocephalus-agricola")
        text = render_card(
            view,
            reverse_hebrew=False,
            reveal_produce=True,
            produce_answer="Acrocephalus agricola",
        )
        self.assertIn("correct: 'Acrocephalus agricola'", text)

    def test_render_position(self) -> None:
        view = self._view("acrocephalus-agricola")
        text = render_card(
            view, reverse_hebrew=False, position=(2, 5)
        )
        self.assertTrue(text.startswith("[F 2/5]"))


class ConstructFeedbackTests(unittest.TestCase):
    def _render(self, response: str) -> str:
        return render_latin_result(
            grade_latin("Microcarbo pygmeus", response)
        )

    def test_correct(self) -> None:
        text = self._render("Microcarbo pygmeus")
        self.assertEqual(text, "  correct: 'Microcarbo pygmeus'")

    def test_case_difference_is_correct(self) -> None:
        self.assertIn("correct:", self._render("microcarbo PYGMEUS"))

    def test_transposition_is_marked_as_one_region(self) -> None:
        text = self._render("Microcarbo pygemus")
        self.assertIn("  almost:", text)
        self.assertIn("    chose:    pygemus\n                 ^^", text)
        self.assertIn("  genus:    [correct]  almost  wrong", text)
        self.assertIn("  epithet:  correct  [almost]  wrong", text)

    def test_substitution_is_marked_under_one_character(self) -> None:
        text = self._render("Microcarbo pygmous")
        self.assertIn("    chose:    pygmous\n                  ^", text)

    def test_wrong_marks_its_own_word(self) -> None:
        text = self._render("Microcarbo pygmy")
        self.assertIn("  wrong:", text)
        self.assertIn("  genus:    [correct]  almost  wrong", text)
        self.assertIn("  epithet:  correct  almost  [wrong]", text)

    def test_wrong_words_far_from_expected_have_no_marker(self) -> None:
        text = self._render("Turdus merula")
        self.assertNotIn("^", text)
        self.assertIn("  genus:    correct  almost  [wrong]", text)
        self.assertIn("  epithet:  correct  almost  [wrong]", text)


if __name__ == "__main__":
    unittest.main()
