"""Tests for the shared dataset loader and its indexes."""

from __future__ import annotations

import unittest
from pathlib import Path

from trainer.foundation.config import Config
from trainer.foundation.dataset import load_catalog
from trainer.foundation.errors import DataError, NotFound


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = Config.default()
        cls.catalog = load_catalog(
            cls.config.species_path, cls.config.etymology_path
        )

    def test_expected_counts(self) -> None:
        catalog = self.catalog
        self.assertEqual(len(catalog.birds), 565)
        self.assertEqual(len(catalog.by_family), 84)
        self.assertEqual(len(catalog.by_order), 26)
        self.assertEqual(len(catalog.by_genus), 249)
        self.assertEqual(len(catalog.elements), 308)
        self.assertEqual(len(catalog.splits), 312)
        self.assertEqual(len(catalog.whole_names), 16)
        self.assertEqual(len(catalog.themes), 13)

    def test_species_ids_and_latin_names(self) -> None:
        seen = set()
        for bird in self.catalog.birds:
            self.assertEqual(bird.latin, f"{bird.genus} {bird.epithet}")
            self.assertEqual(
                bird.species_id,
                f"{bird.genus.lower()}-{bird.epithet.lower()}",
            )
            self.assertNotIn(bird.species_id, seen)
            seen.add(bird.species_id)

    def test_hebrew_coverage(self) -> None:
        with_hebrew = [bird for bird in self.catalog.birds if bird.has_hebrew]
        without_hebrew = [
            bird for bird in self.catalog.birds if not bird.has_hebrew
        ]
        self.assertEqual(len(with_hebrew), 560)
        self.assertEqual(len(without_hebrew), 5)
        self.assertTrue(
            all("no-hebrew" in bird.flags for bird in without_hebrew)
        )

    def test_one_shared_hebrew_name(self) -> None:
        shared = [
            (name, birds)
            for name, birds in self.catalog.by_hebrew.items()
            if len(birds) == 2
        ]
        self.assertEqual(len(shared), 1)
        _, birds = shared[0]
        self.assertEqual(
            {bird.species_id for bird in birds},
            {"oenanthe-lugens", "oenanthe-warriae"},
        )

    def test_family_hebrew_flags(self) -> None:
        missing = [
            bird for bird in self.catalog.birds if not bird.family_he
        ]
        self.assertEqual(len(missing), 29)
        self.assertTrue(
            all("no-family-hebrew" in bird.flags for bird in missing)
        )

    def test_family_order(self) -> None:
        by_family: dict[str, set[int]] = {}
        for bird in self.catalog.birds:
            by_family.setdefault(bird.family, set()).add(bird.family_order)
        self.assertEqual(len(by_family), 84)
        self.assertTrue(all(len(values) == 1 for values in by_family.values()))
        orders = sorted(
            next(iter(values)) for values in by_family.values()
        )
        self.assertEqual(orders, list(range(1, 85)))

    def test_parts_and_lookup(self) -> None:
        with_parts = self.catalog.bird("acrocephalus-agricola")
        without_parts = self.catalog.bird("turdus-merula")
        self.assertTrue(with_parts.has_parts)
        self.assertFalse(without_parts.has_parts)

        genus_parts = with_parts.parts_for("Acrocephalus")
        self.assertEqual(
            [part.surface for part in genus_parts],
            ["Acro", "cephalus"],
        )
        self.assertEqual(
            [part.element_id for part in genus_parts],
            ["acro", "cephalus"],
        )

        epithet_parts = self.catalog.parts_for("melanocephala")
        self.assertEqual(
            [part.surface for part in epithet_parts],
            ["melano", "cephala"],
        )
        self.assertEqual(
            self.catalog.element("cephalus").en,
            "head",
        )
        self.assertTrue(
            any(
                element.element_id == "cephalus"
                for element in self.catalog.elements_for_form("cephalus")
            )
        )

    def test_syriacus_whole_name(self) -> None:
        whole = self.catalog.whole_names["syriacus"]
        self.assertEqual(whole.en, "Syrian")

    def test_status_categories(self) -> None:
        self.assertEqual(
            self.catalog.by_status["regular"][0].status_categories,
            ("regular",),
        )
        self.assertEqual(len(self.catalog.by_status["regular"]), 381)
        self.assertEqual(len(self.catalog.by_status["introduced"]), 11)
        self.assertEqual(len(self.catalog.by_status["accidental"]), 170)
        self.assertEqual(len(self.catalog.by_status["historical"]), 5)
        self.assertEqual(len(self.catalog.by_status["extinct"]), 1)

        historical_accidental = [
            bird
            for bird in self.catalog.birds
            if bird.status == "Ex/A"
        ]
        self.assertEqual(len(historical_accidental), 3)
        for bird in historical_accidental:
            self.assertEqual(
                set(bird.status_categories),
                {"historical", "accidental"},
            )

    def test_data_version(self) -> None:
        version = self.catalog.data_version
        self.assertTrue(version.startswith("sha256:"))
        self.assertEqual(len(version), len("sha256:") + 64)

    def test_ringer_key(self) -> None:
        self.assertEqual(
            self.catalog.bird("passer-moabiticus").ringer_key,
            "PASMOA",
        )

    def test_not_found(self) -> None:
        with self.assertRaises(NotFound):
            self.catalog.bird("no-such-bird")
        with self.assertRaises(NotFound):
            self.catalog.element("no-such-element")

    def test_missing_data_file(self) -> None:
        with self.assertRaises(DataError):
            load_catalog(
                Path("/nonexistent/species.json"),
                self.config.etymology_path,
            )


if __name__ == "__main__":
    unittest.main()
