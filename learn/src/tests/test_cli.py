"""Tests for the text client's bird list and lookup."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from trainer.cli import _dispatch, _find_bird, _matching_birds
from trainer.foundation.config import Config
from trainer.foundation.dataset import load_catalog
from trainer.foundation.errors import NotFound


class BirdSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = Config.default()
        cls.catalog = load_catalog(config.species_path, config.etymology_path)

    def test_empty_query_lists_every_bird(self) -> None:
        self.assertEqual(len(_matching_birds(self.catalog, "")), 565)

    def test_searches_english_name(self) -> None:
        birds = _matching_birds(self.catalog, "paddyfield warbler")
        self.assertEqual(
            [bird.species_id for bird in birds],
            ["acrocephalus-agricola"],
        )

    def test_every_word_must_match(self) -> None:
        birds = _matching_birds(self.catalog, "paddyfield goose")
        self.assertEqual(birds, [])

    def test_search_is_case_insensitive(self) -> None:
        birds = _matching_birds(self.catalog, "PADDYFIELD WARBLER")
        self.assertEqual(
            [bird.species_id for bird in birds],
            ["acrocephalus-agricola"],
        )

    def test_find_bird_by_english_name(self) -> None:
        bird = _find_bird(self.catalog, "Paddyfield warbler")
        self.assertEqual(bird.species_id, "acrocephalus-agricola")

    def test_card_accepts_multiword_english_name(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            _dispatch(self.catalog, ["card", "L", "paddyfield", "warbler"], False)
        self.assertIn("[L] Acrocephalus agricola", output.getvalue())

    def test_card_accepts_options_after_multiword_name(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            _dispatch(
                self.catalog,
                ["E", "paddyfield", "warbler", "--seed", "3", "--reveal"],
                False,
            )
        text = output.getvalue()
        self.assertIn("[E] Acrocephalus agricola", text)
        self.assertIn("correct:", text)

    def test_slash_command_searches(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            _dispatch(self.catalog, ["/paddyfield", "warbler"], False)
        text = output.getvalue()
        self.assertIn("1 bird matching 'paddyfield warbler'", text)
        self.assertIn("acrocephalus-agricola", text)
        self.assertIn("Paddyfield warbler", text)
        self.assertIn("Acrocephalidae", text)
        self.assertIn("Hebrew", text)
        self.assertIn("קנית אורז", text)
        self.assertIn("Hebrew family", text)
        self.assertIn("קניתיים", text)

    def test_find_bird_rejects_ambiguous_fragment(self) -> None:
        with self.assertRaises(NotFound) as caught:
            _find_bird(self.catalog, "warbler")
        self.assertIn("ambiguous", str(caught.exception))
        self.assertIn("list warbler", str(caught.exception))

    def test_find_bird_rejects_unknown_name(self) -> None:
        with self.assertRaises(NotFound):
            _find_bird(self.catalog, "no-such-bird")


if __name__ == "__main__":
    unittest.main()
