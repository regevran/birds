"""Tests for the account entries shared with the Cloudflare Worker."""

from __future__ import annotations

import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from trainer.foundation.passwords import (
    add_user,
    hash_password,
    is_valid_username,
    normalize_username,
    verify_password,
)

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "provision_user.py"


class PasswordTests(unittest.TestCase):
    def test_known_pbkdf2_vector(self) -> None:
        entry = hash_password(
            "correct horse battery staple",
            iterations=1_000,
            salt=bytes(range(16)),
        )
        self.assertEqual(entry["salt"], "AAECAwQFBgcICQoLDA0ODw==")
        self.assertEqual(
            entry["hash"], "ppsXnjrdPB4KryJ6DrOqKqhkWrhv7PbKAMF1Eml8cZ4="
        )
        self.assertTrue(
            verify_password("correct horse battery staple", entry)
        )

    def test_wrong_password_fails(self) -> None:
        entry = hash_password("secret", iterations=1_000)
        self.assertFalse(verify_password("Secret", entry))
        self.assertFalse(verify_password("", entry))

    def test_each_hash_uses_a_fresh_salt(self) -> None:
        first = hash_password("secret")
        second = hash_password("secret")
        self.assertNotEqual(first["salt"], second["salt"])
        self.assertNotEqual(first["hash"], second["hash"])

    def test_malformed_entries_fail_closed(self) -> None:
        self.assertFalse(verify_password("secret", {}))
        self.assertFalse(
            verify_password(
                "secret",
                {"iterations": 0, "salt": "AA==", "hash": "AA=="},
            )
        )
        self.assertFalse(
            verify_password(
                "secret",
                {"iterations": "many", "salt": "AA==", "hash": "AA=="},
            )
        )

    def test_username_rules(self) -> None:
        self.assertEqual(normalize_username("  Ran  "), "ran")
        self.assertTrue(is_valid_username("ran"))
        self.assertTrue(is_valid_username("test-user_2"))
        self.assertFalse(is_valid_username("../ran"))
        self.assertFalse(is_valid_username("Ran"))
        self.assertFalse(is_valid_username(""))

    def test_add_user_returns_a_new_document(self) -> None:
        original = {"users": {}}
        updated = add_user(original, "Ran", "secret", scope="profile")
        self.assertEqual(original, {"users": {}})
        self.assertIn("ran", updated["users"])
        self.assertEqual(updated["users"]["ran"]["scope"], "profile")
        self.assertTrue(
            verify_password("secret", updated["users"]["ran"])
        )

        with self.assertRaises(ValueError):
            add_user(updated, "../ran", "secret")
        with self.assertRaises(ValueError):
            add_user(updated, "ran", "secret", scope="admin")


class ProvisionScriptTests(unittest.TestCase):
    def test_script_writes_a_usable_account(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "users.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "tester",
                    "--password",
                    "tester-password",
                    "--scope",
                    "tests",
                    "--file",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("Added 'tester'", result.stdout)
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(
                verify_password(
                    "tester-password", document["users"]["tester"]
                )
            )
            self.assertEqual(document["users"]["tester"]["scope"], "tests")
            self.assertEqual(
                stat.S_IMODE(path.stat().st_mode) & 0o777, 0o600
            )


if __name__ == "__main__":
    unittest.main()
