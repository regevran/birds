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
    _interactive,
    _matching_birds,
    _read_line,
)
from trainer.foundation.config import Config
from trainer.foundation.dataset import load_catalog


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
        self.assertIn(
            "--answer is only for E and R cards", output.getvalue()
        )


class InteractiveRecognizeTests(unittest.TestCase):
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
                card_type=CardType.R,
            ),
            seed=0,
        )
        cls.shared_view = card_view(
            cls.catalog,
            CardDescriptor(
                species_id="oenanthe-lugens",
                card_type=CardType.R,
            ),
            seed=0,
        )

    def _correct_number(self, view=None) -> str:
        view = view or self.view
        for number, option in enumerate(view.options, start=1):
            if option.species_id == view.species_id:
                return str(number)
        raise AssertionError("card species is missing from its options")

    def _wrong_numbers(self, view=None) -> list[str]:
        view = view or self.view
        correct = self._correct_number(view)
        return [
            str(number)
            for number in range(1, len(view.options) + 1)
            if str(number) != correct
        ]

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

    def test_correct_first_try(self) -> None:
        text, _ = self._run(
            ["R", "acrocephalus-agricola", "--seed", "0"],
            [self._correct_number()],
        )
        self.assertIn("correct:", text)
        self.assertNotIn("try again", text)

    def test_wrong_once_then_correct(self) -> None:
        wrong = self._wrong_numbers()[0]
        text, _ = self._run(
            ["R", "acrocephalus-agricola", "--seed", "0"],
            [wrong, self._correct_number()],
        )
        self.assertIn("try again", text)
        self.assertIn("correct:", text)

    def test_wrong_twice_reveals(self) -> None:
        wrong, wrong_again = self._wrong_numbers()[:2]
        text, _ = self._run(
            ["R", "acrocephalus-agricola", "--seed", "0"],
            [wrong, wrong_again],
        )
        self.assertIn("try again", text)
        self.assertIn("wrong: chose", text)
        self.assertIn("correct 'Acrocephalus agricola'", text)

    def test_shared_hebrew_either_is_correct(self) -> None:
        number = next(
            str(index)
            for index, option in enumerate(
                self.shared_view.options, start=1
            )
            if option.species_id == "oenanthe-warriae"
        )
        text, _ = self._run(
            ["R", "oenanthe-lugens", "--seed", "0"], [number]
        )
        self.assertIn(
            "correct: 'Oenanthe lugens' or 'Oenanthe warriae'", text
        )

    def test_search_returns_to_card(self) -> None:
        text, prompts = self._run(
            ["R", "acrocephalus-agricola", "--seed", "0"],
            ["/paddyfield", "exit", self._correct_number()],
        )
        self.assertIn("1 bird matching 'paddyfield'", text)
        self.assertIn("search> ", prompts)
        self.assertIn("correct:", text)

    def test_up_abandons_card(self) -> None:
        text, _ = self._run(
            ["R", "acrocephalus-agricola", "--seed", "0"], ["exit"]
        )
        self.assertIn("card cancelled.", text)
        self.assertNotIn("correct:", text)

    def test_interactive_uses_random_seed(self) -> None:
        with patch("trainer.cli.secrets.randbelow", return_value=0) as rnd:
            text, _ = self._run(
                ["R", "acrocephalus-agricola"],
                [self._correct_number()],
            )
        rnd.assert_called_once()
        self.assertIn("correct:", text)

    def test_explicit_seed_beats_random(self) -> None:
        with patch(
            "trainer.cli.secrets.randbelow", return_value=99
        ) as rnd:
            text, _ = self._run(
                ["R", "acrocephalus-agricola", "--seed", "0"],
                [self._correct_number()],
            )
        rnd.assert_not_called()
        self.assertIn("correct:", text)


class OneShotRecognizeTests(unittest.TestCase):
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
                card_type=CardType.R,
            ),
            seed=0,
        )

    def _correct_number(self) -> str:
        for number, option in enumerate(self.view.options, start=1):
            if option.species_id == self.view.species_id:
                return str(number)
        raise AssertionError("card species is missing from its options")

    def _wrong_number(self) -> str:
        correct = self._correct_number()
        return next(
            str(number)
            for number in range(1, len(self.view.options) + 1)
            if str(number) != correct
        )

    def _run(self, args: list[str]) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            _dispatch(
                self.catalog,
                ["R", "acrocephalus-agricola", *args],
                False,
            )
        return output.getvalue()

    def test_answer_correct(self) -> None:
        text = self._run(["--answer", self._correct_number()])
        self.assertIn("correct:", text)

    def test_answer_wrong(self) -> None:
        text = self._run(["--answer", self._wrong_number()])
        self.assertIn("wrong: chose", text)
        self.assertIn("correct 'Acrocephalus agricola'", text)

    def test_answer_wrong_count(self) -> None:
        text = self._run(["--answer", "1 2"])
        self.assertIn("expected 1 answer, got 2", text)

    def test_answer_non_numeric(self) -> None:
        text = self._run(["--answer", "x"])
        self.assertIn("answer is not a number", text)

    def test_answer_out_of_range(self) -> None:
        text = self._run(["--answer", "99"])
        self.assertIn("answer must be between 1 and 5", text)

    def test_reveal_shows_accepted(self) -> None:
        text = self._run(["--reveal"])
        self.assertIn("correct:", text)
        self.assertIn("Acrocephalus agricola", text)

    def test_shared_hebrew_reveal_shows_both(self) -> None:
        view = card_view(
            self.catalog,
            CardDescriptor(
                species_id="oenanthe-lugens",
                card_type=CardType.R,
            ),
            seed=0,
        )
        output = io.StringIO()
        with redirect_stdout(output):
            _dispatch(
                self.catalog,
                ["R", "oenanthe-lugens", "--reveal"],
                False,
            )
        text = output.getvalue()
        self.assertIn("Oenanthe lugens", text)
        self.assertIn("Oenanthe warriae", text)
        self.assertEqual(len(view.options), 5)


class CardRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = Config.default()
        cls.catalog = load_catalog(
            config.species_path, config.etymology_path
        )
        cls.matches = _matching_birds(cls.catalog, "cormorant")

    def _view(self, bird, card_type: CardType, seed: int = 0):
        return card_view(
            self.catalog,
            CardDescriptor(
                species_id=bird.species_id,
                card_type=card_type,
            ),
            seed=seed,
        )

    def _recognize_numbers(self, seed: int = 0) -> list[str]:
        numbers = []
        for offset, bird in enumerate(self.matches):
            view = self._view(bird, CardType.R, seed + offset)
            for number, option in enumerate(view.options, start=1):
                if option.species_id == bird.species_id:
                    numbers.append(str(number))
                    break
        return numbers

    def _elements_numbers(self, seed: int = 0) -> tuple[list[list[str]], int]:
        cards: list[list[str]] = []
        total = 0
        for offset, bird in enumerate(self.matches):
            view = self._view(bird, CardType.E, seed + offset)
            cards.append(
                [
                    str(
                        row.options.index(
                            self.catalog.element(row.element_id).he
                        )
                        + 1
                    )
                    for row in view.rows
                ]
            )
            total += len(view.rows)
        return cards, total

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

    def _batch(self, args: list[str]) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            _dispatch(self.catalog, args, False)
        return output.getvalue()

    def test_recognize_run(self) -> None:
        numbers = self._recognize_numbers()
        responses = [numbers[0], "", numbers[1]]
        text, _ = self._run(
            ["R", "cormorant", "--seed", "0"], responses
        )
        self.assertIn("R run: 2 birds matching 'cormorant'", text)
        self.assertIn("[R 1/2]", text)
        self.assertIn("[R 2/2]", text)
        self.assertIn(
            "R run complete: 2 cards, first try 2, retry 0, revealed 0.",
            text,
        )

    def test_recognize_run_wrong_then_correct(self) -> None:
        numbers = self._recognize_numbers()
        view = self._view(self.matches[0], CardType.R, 0)
        wrong = next(
            str(number)
            for number, option in enumerate(view.options, start=1)
            if option.species_id != view.species_id
        )
        responses = [wrong, numbers[0], "", numbers[1]]
        text, _ = self._run(
            ["R", "cormorant", "--seed", "0"], responses
        )
        self.assertIn("try again", text)
        self.assertIn(
            "R run complete: 2 cards, first try 1, retry 1, revealed 0.",
            text,
        )

    def test_recognize_run_reveals_after_two_wrongs(self) -> None:
        numbers = self._recognize_numbers()
        view = self._view(self.matches[0], CardType.R, 0)
        wrong_numbers = [
            str(number)
            for number, option in enumerate(view.options, start=1)
            if option.species_id != view.species_id
        ]
        responses = [
            wrong_numbers[0],
            wrong_numbers[1],
            "",
            numbers[1],
        ]
        text, _ = self._run(
            ["R", "cormorant", "--seed", "0"], responses
        )
        self.assertIn(
            "R run complete: 2 cards, first try 1, retry 0, revealed 1.",
            text,
        )

    def test_recognize_run_stops(self) -> None:
        text, _ = self._run(
            ["R", "cormorant", "--seed", "0"], ["exit"]
        )
        self.assertIn("card cancelled.", text)
        self.assertIn("R run stopped after 0 of 2 cards.", text)

    def test_recognize_run_stops_between_cards(self) -> None:
        numbers = self._recognize_numbers()
        text, _ = self._run(
            ["R", "cormorant", "--seed", "0"],
            [numbers[0], "exit"],
        )
        self.assertIn("R run stopped after 1 of 2 cards.", text)

    def test_elements_run(self) -> None:
        cards, total = self._elements_numbers()
        responses: list[str] = []
        for index, numbers in enumerate(cards):
            responses.extend(numbers)
            if index + 1 < len(cards):
                responses.append("")
        text, _ = self._run(
            ["E", "cormorant", "--seed", "0"], responses
        )
        self.assertIn("E run: 2 birds matching 'cormorant'", text)
        self.assertIn("[E 1/2]", text)
        self.assertIn("[E 2/2]", text)
        self.assertIn(
            f"E run complete: 2 cards, {total}/{total} elements correct.",
            text,
        )

    def test_learn_run(self) -> None:
        text, _ = self._run(
            ["L", "cormorant", "--seed", "0"], [""]
        )
        self.assertIn("L run: 2 birds matching 'cormorant'", text)
        self.assertIn("[L 1/2]", text)
        self.assertIn("[L 2/2]", text)
        self.assertIn("L run complete: 2 cards.", text)

    def test_run_skips_ineligible(self) -> None:
        text, _ = self._run(
            ["R", "puffinus", "--seed", "0"], ["exit"]
        )
        self.assertIn(
            "R run: 4 birds matching 'puffinus' "
            "(3 skipped: no Hebrew)",
            text,
        )

        output = io.StringIO()
        with redirect_stdout(output):
            _dispatch(
                self.catalog, ["E", "puffinus"], False, interactive=True
            )
        self.assertIn(
            "no birds matching 'puffinus' can make a card of type E "
            "(7 skipped: no split elements)",
            output.getvalue(),
        )

    def test_batch_prints_all_cards(self) -> None:
        text = self._batch(["R", "cormorant", "--seed", "0"])
        self.assertIn("R run: 2 birds matching 'cormorant'", text)
        self.assertIn("[R 1/2]", text)
        self.assertIn("[R 2/2]", text)
        self.assertIn("Microcarbo pygmeus", text)
        self.assertIn("Phalacrocorax carbo", text)

    def test_batch_reveal_shows_answers(self) -> None:
        text = self._batch(
            ["R", "cormorant", "--seed", "0", "--reveal"]
        )
        self.assertIn("[R 1/2]", text)
        self.assertIn("[R 2/2]", text)
        self.assertIn("correct:", text)
        self.assertIn("R run: 2 cards (answers revealed).", text)

    def test_answer_needs_single_match(self) -> None:
        text = self._batch(["R", "cormorant", "--answer", "1"])
        self.assertIn(
            "--answer needs a single match; 2 birds match 'cormorant'",
            text,
        )

    def test_unknown_card_query(self) -> None:
        text = self._batch(["R", "no-such-bird"])
        self.assertIn("bird 'no-such-bird' not found", text)

    def test_card_query_accepts_leading_slash(self) -> None:
        text = self._batch(["R", "/cormorant", "--seed", "0"])
        self.assertIn("R run: 2 birds matching 'cormorant'", text)

    def test_single_match_has_no_run_header(self) -> None:
        text = self._batch(["R", "paddyfield warbler", "--seed", "0"])
        self.assertTrue(text.startswith("[R]"))
        self.assertNotIn("R run:", text)


if __name__ == "__main__":
    unittest.main()
