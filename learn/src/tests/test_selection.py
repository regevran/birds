"""Tests for the client-local selected session store."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trainer.foundation import selection

SERVER = "https://worker.example"
USER = "ran"


class SelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        patcher = patch.dict(
            os.environ, {selection.STATE_ENV: str(self.path)}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_save_load_and_clear_are_per_server_and_user(self) -> None:
        self.assertIsNone(selection.load_selected(SERVER, USER))
        selection.save_selected(SERVER, USER, "a1")
        selection.save_selected("https://other.example", USER, "b2")
        selection.save_selected(SERVER, "other", "c3")

        self.assertEqual(selection.load_selected(SERVER, USER), "a1")
        self.assertEqual(
            selection.load_selected("https://other.example", USER), "b2"
        )
        self.assertEqual(selection.load_selected(SERVER, "other"), "c3")

        selection.clear_selected(SERVER, USER)
        self.assertIsNone(selection.load_selected(SERVER, USER))
        self.assertEqual(
            selection.load_selected("https://other.example", USER), "b2"
        )

    def test_file_is_private_and_atomic(self) -> None:
        selection.save_selected(SERVER, USER, "a1")
        self.assertTrue(self.path.exists())
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        document = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(
            document,
            {"selections": {f"{SERVER}|{USER}": "a1"}},
        )

    def test_malformed_state_is_ignored_and_replaced(self) -> None:
        self.path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(selection.load_selected(SERVER, USER))
        selection.save_selected(SERVER, USER, "a1")
        self.assertEqual(selection.load_selected(SERVER, USER), "a1")

    def test_empty_session_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            selection.save_selected(SERVER, USER, "   ")


if __name__ == "__main__":
    unittest.main()
