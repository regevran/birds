"""Tests for Latin input normalization."""

from __future__ import annotations

import unittest

from trainer.foundation.normalize import normalize_latin


class NormalizeLatinTests(unittest.TestCase):
    def test_clean_name(self) -> None:
        self.assertEqual(
            normalize_latin("Acrocephalus agricola"),
            "acrocephalus agricola",
        )

    def test_case_and_whitespace(self) -> None:
        self.assertEqual(
            normalize_latin("  ACROCEPHALUS   AGRICOLA  "),
            "acrocephalus agricola",
        )

    def test_tab_newline_and_non_breaking_space(self) -> None:
        for text in (
            "Acrocephalus\tagricola",
            "Acrocephalus\nagricola",
            "Acrocephalus agricola",
        ):
            self.assertEqual(
                normalize_latin(text), "acrocephalus agricola"
            )

    def test_nfc_composes_decomposed_characters(self) -> None:
        self.assertEqual(
            normalize_latin("Acrocephalus ágricola"),
            "acrocephalus ágricola",
        )
        self.assertEqual(
            normalize_latin("Acrocephalus ágricola"),
            normalize_latin("Acrocephalus ágricola"),
        )

    def test_nfc_does_not_remove_accents(self) -> None:
        self.assertNotEqual(
            normalize_latin("Acrocephalus ágricola"),
            normalize_latin("Acrocephalus agricola"),
        )


if __name__ == "__main__":
    unittest.main()
