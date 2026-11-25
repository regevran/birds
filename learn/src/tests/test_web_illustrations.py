"""Tests for the browser illustration manifest.

The manifest pins one CC BY 4.0 sticker per dataset species; the build tool
downloads and resizes them, and no image is committed. These tests run
offline and keep the manifest aligned with the dataset.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "learn" / "web" / "illustrations.json"
DATA = ROOT / "data" / "out" / "israel_birds_final.json"
COMMIT = re.compile(r"^[0-9a-f]{40}$")
VERSION = re.compile(r"^v[0-9]+$")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class IllustrationManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = load_json(MANIFEST)
        cls.birds = load_json(DATA)

    def test_source_is_pinned_and_credited(self) -> None:
        source = self.document["source"]
        self.assertEqual(
            source["repository"],
            "https://github.com/alchaincyf/huashu-bird-sticker",
        )
        self.assertRegex(source["commit"], COMMIT)
        self.assertTrue(source["data_version"])
        self.assertEqual(source["license"], "CC BY 4.0")
        self.assertIn("creativecommons.org/licenses/by/4.0", source["license_url"])
        self.assertIn("Bird Album", source["credit"])
        self.assertIn("huashu-bird-sticker", source["credit"])

    def test_output_settings(self) -> None:
        self.assertRegex(self.document["asset_version"], VERSION)
        self.assertEqual(self.document["size"], 512)
        self.assertEqual(self.document["quality"], 82)

    def test_every_species_has_one_sticker(self) -> None:
        ids = {
            f"{bird['genus'].lower()}-{bird['epithet'].lower()}"
            for bird in self.birds
        }
        stickers = self.document["stickers"]
        self.assertEqual(set(stickers), ids)
        self.assertEqual(len(stickers), len(self.birds))

    def test_sticker_paths_are_safe(self) -> None:
        for species_id, sticker in self.document["stickers"].items():
            self.assertTrue(sticker.startswith("stickers/"), species_id)
            self.assertTrue(sticker.endswith(".webp"), species_id)
            parts = sticker.split("/")
            self.assertEqual(len(parts), 4, sticker)
            for part in parts:
                self.assertNotIn(part, ("", ".", ".."), sticker)
                self.assertNotIn("\\", part, sticker)


if __name__ == "__main__":
    unittest.main()
