"""Tests for the text client's bird list and lookup."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from trainer.cards.models import CardDescriptor, CardType
from trainer.cards.views import card_view
from trainer.cli import (
    _Up,
    _dispatch,
    _find_bird,
    _interactive,
    _matching_birds,
    _read_line,
)
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


class LineReaderTests(unittest.TestCase):
    def test_exit_and_quit_go_up(self) -> None:
        for text in ("exit", "quit", "EXIT", "  Quit  \n"):
            with patch("builtins.input", return_value=text):
                with self.assertRaises(_Up):
                    _read_line("card> ")

    def test_esc_then_enter_goes_up(self) -> None:
        with patch("builtins.input", return_value="\x1b"):
            with self.assertRaises(_Up):
                _read_line("card> ")

    def test_readline_esc_sentinel_goes_up(self) -> None:
        with patch("builtins.input", return_value="<UP>"):
            with self.assertRaises(_Up):
                _read_line("card> ")

    def test_ctrl_d_goes_up(self) -> None:
        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(_Up):
                _read_line("card> ")

    def test_ordinary_input_is_returned(self) -> None:
        with patch("builtins.input", return_value="esc"):
            self.assertEqual(_read_line("card> "), "esc")


class InteractiveExitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = Config.default()
        cls.catalog = load_catalog(
            config.species_path, config.etymology_path
        )

    def test_ctrl_c_leaves_client(self) -> None:
        output = io.StringIO()
        with patch("trainer.cli._enable_line_editing"):
            with patch("builtins.input", side_effect=KeyboardInterrupt):
                with redirect_stdout(output):
                    self.assertEqual(
                        _interactive(self.catalog, False), 0
                    )

    def test_exit_at_card_prompt_leaves_client(self) -> None:
        output = io.StringIO()
        with patch("trainer.cli._enable_line_editing"):
            with patch("builtins.input", return_value="exit"):
                with redirect_stdout(output):
                    self.assertEqual(
                        _interactive(self.catalog, False), 0
                    )


class InteractiveElementsTests(unittest.TestCase):
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

    def _correct_numbers(self) -> list[str]:
        return [
            str(
                row.options.index(
                    self.catalog.element(row.element_id).he
                )
                + 1
            )
            for row in self.view.rows
        ]

    def _wrong_number(self, index: int = 0) -> str:
        row = self.view.rows[index]
        expected = self.catalog.element(row.element_id).he
        correct = row.options.index(expected)
        return str((correct + 1) % len(row.options) + 1)

    def _run(
        self, args: list[str], responses: list[str]
    ) -> tuple[str, list[str]]:
        prompts: list[str] = []
        iterator = iter(responses)

        def fake_input(prompt: str) -> str:
            prompts.append(prompt)
            return next(iterator)

        output = io.StringIO()
        with patch("builtins.input", side_effect=fake_input):
            with redirect_stdout(output):
                _dispatch(
                    self.catalog, args, False, interactive=True
                )
        return output.getvalue(), prompts

    def test_all_correct(self) -> None:
        text, prompts = self._run(
            ["E", "acrocephalus-agricola", "--seed", "0"],
            self._correct_numbers(),
        )
        self.assertIn("4/4 correct.", text)
        first = self.view.rows[0]
        expected = self.catalog.element(first.element_id).he
        self.assertIn(f"correct: {expected!r}", text)
        self.assertEqual(len(prompts), len(self.view.rows))

    def test_interactive_uses_random_seed(self) -> None:
        with patch("trainer.cli.secrets.randbelow", return_value=0) as rnd:
            text, _ = self._run(
                ["E", "acrocephalus-agricola"], self._correct_numbers()
            )
        rnd.assert_called_once()
        self.assertIn("4/4 correct.", text)

    def test_explicit_seed_beats_random(self) -> None:
        with patch(
            "trainer.cli.secrets.randbelow", return_value=99
        ) as rnd:
            text, _ = self._run(
                ["E", "acrocephalus-agricola", "--seed", "0"],
                self._correct_numbers(),
            )
        rnd.assert_not_called()
        self.assertIn("4/4 correct.", text)

    def test_wrong_answer(self) -> None:
        numbers = self._correct_numbers()
        numbers[0] = self._wrong_number(0)
        text, _ = self._run(
            ["E", "acrocephalus-agricola", "--seed", "0"], numbers
        )
        self.assertIn("wrong:", text)
        self.assertIn("3/4 correct.", text)

    def test_search_returns_to_same_element(self) -> None:
        numbers = self._correct_numbers()
        text, prompts = self._run(
            ["E", "acrocephalus-agricola", "--seed", "0"],
            ["/paddyfield", "exit", *numbers],
        )
        self.assertIn("1 bird matching 'paddyfield'", text)
        self.assertIn("search> ", prompts)
        self.assertIn("4/4 correct.", text)

    def test_bare_slash_and_help_in_search_mode(self) -> None:
        numbers = self._correct_numbers()
        text, prompts = self._run(
            ["E", "acrocephalus-agricola", "--seed", "0"],
            ["/", "?", "acro", "exit", *numbers],
        )
        self.assertIn("Search mode:", text)
        self.assertIn("same as /text", text)
        self.assertIn("matching 'acro'", text)
        self.assertNotIn("565 birds", text)
        self.assertIn("search> ", prompts)

    def test_exit_abandons_card(self) -> None:
        text, _ = self._run(
            ["E", "acrocephalus-agricola"], ["exit"]
        )
        self.assertIn("card cancelled.", text)
        self.assertNotIn("correct.", text)

    def test_esc_then_enter_abandons_card(self) -> None:
        text, _ = self._run(
            ["E", "acrocephalus-agricola"], ["\x1b"]
        )
        self.assertIn("card cancelled.", text)

    def test_search_alias_from_card_prompt(self) -> None:
        text, prompts = self._run(["list", "warbler"], ["exit"])
        self.assertIn("matching 'warbler'", text)
        self.assertIn("search> ", prompts)

    def test_bare_slash_from_card_prompt_does_not_list_all(self) -> None:
        text, prompts = self._run(["/"], ["acro", "exit"])
        self.assertIn("Search mode:", text)
        self.assertIn("matching 'acro'", text)
        self.assertNotIn("565 birds", text)
        self.assertIn("search> ", prompts)


class OneShotElementAnswerTests(unittest.TestCase):
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

    def _numbers(self) -> list[str]:
        return [
            str(
                row.options.index(
                    self.catalog.element(row.element_id).he
                )
                + 1
            )
            for row in self.view.rows
        ]

    def _run(self, answers: list[str]) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            _dispatch(
                self.catalog,
                ["E", "acrocephalus-agricola", "--answer", *answers],
                False,
            )
        return output.getvalue()

    def test_answer_option(self) -> None:
        text = self._run([" ".join(self._numbers())])
        self.assertIn("4/4 correct.", text)

    def test_answer_wrong_count(self) -> None:
        text = self._run(["1 2"])
        self.assertIn("expected 4 answers, got 2", text)

    def test_answer_non_numeric(self) -> None:
        text = self._run(["a b c d"])
        self.assertIn("answer 1 is not a number", text)

    def test_answer_rejects_reveal(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            _dispatch(
                self.catalog,
                [
                    "E",
                    "acrocephalus-agricola",
                    "--answer",
                    "1 2 3 4",
                    "--reveal",
                ],
                False,
            )
        self.assertIn("choose either --answer or --reveal", output.getvalue())

    def test_answer_is_only_for_e(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            _dispatch(
                self.catalog,
                ["L", "acrocephalus-agricola", "--answer", "1"],
                False,
            )
        self.assertIn("--answer is only for E cards", output.getvalue())


if __name__ == "__main__":
    unittest.main()
