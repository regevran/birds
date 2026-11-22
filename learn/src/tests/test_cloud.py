"""Unit tests for the Cloudflare client and stored credentials."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trainer.foundation.cloud import (
    CloudError,
    CloudFiles,
    Credentials,
    CredentialsError,
    credentials_expired,
    credentials_path,
    delete_credentials,
    load_credentials,
    login,
    normalize_server,
    save_credentials,
)


def credentials(expires_at: str = "2999-01-01T00:00:00Z") -> Credentials:
    return Credentials(
        server="https://worker.example",
        username="ran",
        scope="profile",
        token="token-value",
        expires_at=expires_at,
    )


class ServerTests(unittest.TestCase):
    def test_normalizes_and_strips_slash(self) -> None:
        self.assertEqual(
            normalize_server(" https://worker.example/ "),
            "https://worker.example",
        )
        self.assertEqual(
            normalize_server("http://localhost:8787"),
            "http://localhost:8787",
        )

    def test_rejects_missing_or_odd_urls(self) -> None:
        for value in (
            "",
            "worker.example",
            "ftp://worker.example",
            "https://worker.example/api",
            "https://worker.example?x=1",
            "https://worker.example#x",
        ):
            with self.assertRaises(ValueError, msg=value):
                normalize_server(value)


class CredentialStoreTests(unittest.TestCase):
    def test_round_trip_and_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "credentials.json"
            saved = save_credentials(credentials(), path=path)
            self.assertEqual(saved, path)
            loaded = load_credentials(path=path)
            self.assertEqual(loaded, credentials())
            self.assertEqual(
                stat.S_IMODE(path.stat().st_mode) & 0o777, 0o600
            )

    def test_missing_and_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "credentials.json"
            with self.assertRaises(CredentialsError):
                load_credentials(path=path)
            self.assertFalse(delete_credentials(path=path))
            save_credentials(credentials(), path=path)
            self.assertTrue(delete_credentials(path=path))
            with self.assertRaises(CredentialsError):
                load_credentials(path=path)

    def test_expiry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "credentials.json"
            save_credentials(
                credentials("2000-01-01T00:00:00Z"), path=path
            )
            with self.assertRaises(CredentialsError):
                load_credentials(path=path)
            expired = load_credentials(path=path, require_valid=False)
            self.assertTrue(credentials_expired(expired))
            self.assertFalse(credentials_expired(credentials()))

    def test_invalid_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "credentials.json"
            path.write_text("not json", encoding="utf-8")
            with self.assertRaises(CredentialsError):
                load_credentials(path=path)

            path.write_text(
                json.dumps({"server": "https://worker.example"}),
                encoding="utf-8",
            )
            with self.assertRaises(CredentialsError):
                load_credentials(path=path)

    def test_environment_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "custom.json"
            with patch.dict(
                os.environ, {"BIRDS_TRAINER_CREDENTIALS": str(path)}
            ):
                self.assertEqual(credentials_path(), path)

    def test_no_token_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "credentials.json"
            document = {
                "server": "https://worker.example",
                "username": "ran",
                "scope": "profile",
                "token": "",
                "expires_at": "2999-01-01T00:00:00Z",
            }
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(CredentialsError):
                load_credentials(path=path)


class LoginParsingTests(unittest.TestCase):
    def test_login_parses_a_complete_response(self) -> None:
        payload = json.dumps(
            {
                "username": "ran",
                "scope": "profile",
                "token": "token-value",
                "expires_at": "2999-01-01T00:00:00.000Z",
            }
        ).encode("utf-8")
        with patch(
            "trainer.foundation.cloud._open",
            return_value=(200, payload, {}),
        ) as opened:
            credentials = login(
                "https://worker.example", "ran", "secret"
            )
        opened.assert_called_once()
        self.assertEqual(credentials.server, "https://worker.example")
        self.assertEqual(credentials.username, "ran")
        self.assertEqual(credentials.scope, "profile")
        self.assertEqual(credentials.token, "token-value")

    def test_login_rejects_an_incomplete_response(self) -> None:
        with patch(
            "trainer.foundation.cloud._open",
            return_value=(200, b'{"token": "t"}', {}),
        ):
            with self.assertRaises(CloudError):
                login("https://worker.example", "ran", "secret")


class ClientConstructionTests(unittest.TestCase):
    def test_login_validates_before_network(self) -> None:
        for server, username, password in (
            ("", "ran", "pw"),
            ("https://worker.example", "", "pw"),
            ("https://worker.example", "ran", ""),
        ):
            with self.assertRaises(ValueError):
                login(server, username, password)

    def test_client_requires_token_and_normalizes_server(self) -> None:
        with self.assertRaises(ValueError):
            CloudFiles("https://worker.example", "")
        files = CloudFiles("https://worker.example/", "token")
        self.assertEqual(files.server, "https://worker.example")
        with self.assertRaises(ValueError):
            files.read("")
        with self.assertRaises(ValueError):
            files.write("", b"x")


if __name__ == "__main__":
    unittest.main()
