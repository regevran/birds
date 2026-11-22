"""Live tests against the deployed Worker.

They are skipped unless BIRDS_TEST_SERVER, BIRDS_TEST_USER and
BIRDS_TEST_PASSWORD are set. Use a ``tests``-scoped account: all paths are
written under the Worker's ``tests/`` prefix.
"""

from __future__ import annotations

import os
import unittest
import uuid

from trainer.foundation.cloud import (
    CloudError,
    CloudFiles,
    login,
)

SERVER = os.environ.get("BIRDS_TEST_SERVER", "").strip()
USER = os.environ.get("BIRDS_TEST_USER", "").strip()
PASSWORD = os.environ.get("BIRDS_TEST_PASSWORD", "")

CONFIGURED = bool(SERVER and USER and PASSWORD)


@unittest.skipUnless(
    CONFIGURED,
    "set BIRDS_TEST_SERVER, BIRDS_TEST_USER and BIRDS_TEST_PASSWORD",
)
class LiveWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.credentials = login(SERVER, USER, PASSWORD)
        cls.files = CloudFiles(
            cls.credentials.server, cls.credentials.token
        )
        cls.prefix = f"probe/{uuid.uuid4().hex}/"
        cls.path = f"{cls.prefix}state.json"

    @classmethod
    def tearDownClass(cls) -> None:
        if not hasattr(cls, "files"):
            return
        try:
            cls.files.delete(cls.path)
        except CloudError:
            pass

    def test_file_round_trip_and_revisions(self) -> None:
        first = self.files.write_json(self.path, {"n": 1})
        value, revision = self.files.read_json(self.path)
        self.assertEqual(value, {"n": 1})
        self.assertEqual(revision, first)

        second = self.files.write_json(
            self.path, {"n": 2}, revision=first
        )
        self.assertNotEqual(second, first)

        with self.assertRaises(CloudError) as stale:
            self.files.write_json(self.path, {"n": 3}, revision=first)
        self.assertEqual(stale.exception.status, 412)
        self.assertEqual(stale.exception.code, "revision_conflict")

        listed = self.files.list(self.prefix)
        self.assertIn(self.path, [item["path"] for item in listed])
        self.assertTrue(
            all(item["path"].startswith(self.prefix) for item in listed)
        )

        reader = CloudFiles(
            self.credentials.server, self.credentials.token
        )
        before = reader.read_json(self.path)
        self.assertEqual(before[0], {"n": 2})

        self.files.delete(self.path)
        with self.assertRaises(CloudError) as missing:
            self.files.read(self.path)
        self.assertEqual(missing.exception.status, 404)

    def test_wrong_password_is_rejected(self) -> None:
        with self.assertRaises(CloudError) as failure:
            login(SERVER, USER, f"wrong-{uuid.uuid4().hex}")
        self.assertEqual(failure.exception.status, 401)
        self.assertEqual(failure.exception.code, "invalid_credentials")


if __name__ == "__main__":
    unittest.main()
