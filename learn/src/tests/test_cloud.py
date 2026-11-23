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
    CloudApp,
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


class CloudAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requests = []
        self.payload = None

    def install(self, payload=None, status=200) -> None:
        self.payload = payload

        def fake_open(request, timeout):
            self.requests.append(request)
            body = (
                b""
                if self.payload is None
                else json.dumps(self.payload).encode("utf-8")
            )
            return status, body, {}

        patcher = patch(
            "trainer.foundation.cloud._open", side_effect=fake_open
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_construction_validates(self) -> None:
        with self.assertRaises(ValueError):
            CloudApp("https://worker.example", "")
        app = CloudApp("https://worker.example/", "token")
        self.assertEqual(app.server, "https://worker.example")
        with self.assertRaises(ValueError):
            app.session("")

    def test_profile_and_session_listing_are_get_requests(self) -> None:
        self.install(
            {"profile_id": "ran", "sessions": []}
        )
        app = CloudApp("https://worker.example", "token")
        self.assertEqual(app.profile()["profile_id"], "ran")
        app.list_sessions()

        self.assertEqual(
            self.requests[0].full_url, "https://worker.example/app/profile"
        )
        self.assertEqual(self.requests[0].get_method(), "GET")
        self.assertEqual(
            self.requests[1].full_url, "https://worker.example/app/sessions"
        )
        self.assertEqual(
            self.requests[1].get_header("Authorization"), "Bearer token"
        )
        self.assertEqual(
            self.requests[1].get_header("User-agent"), "BirdsTrainer/0.1"
        )

    def test_create_session_sends_only_given_fields(self) -> None:
        self.install({"session": {"session_id": "s1"}})
        app = CloudApp("https://worker.example", "token")
        app.create_session(
            name="Morning",
            filter={"search": "paddyfield", "statuses": ["accidental"]},
            settings={"active_cap": 3},
            seed=7,
        )
        body = json.loads(self.requests[0].data.decode("utf-8"))
        self.assertEqual(
            body,
            {
                "name": "Morning",
                "filter": {
                    "search": "paddyfield",
                    "statuses": ["accidental"],
                },
                "settings": {"active_cap": 3},
                "seed": 7,
            },
        )

    def test_answer_builds_the_card_payload(self) -> None:
        self.install({"feedback": None, "session": {}})
        app = CloudApp("https://worker.example", "token")
        app.answer(
            "s1",
            "c1",
            "answer",
            choices={"acro": "פסגה"},
            response="Acrocephalus agricola",
        )
        self.assertEqual(
            self.requests[0].full_url,
            "https://worker.example/app/sessions/s1/answer",
        )
        body = json.loads(self.requests[0].data.decode("utf-8"))
        self.assertEqual(
            body,
            {
                "card_uid": "c1",
                "action": "answer",
                "choices": {"acro": "פסגה"},
                "response": "Acrocephalus agricola",
            },
        )

    def test_session_prepare_and_delete(self) -> None:
        self.install({"session": {"session_id": "s1"}})
        app = CloudApp("https://worker.example", "token")
        app.prepare_session("s1")
        self.install(None)
        app.delete_session("s1")

        self.assertEqual(
            [request.full_url for request in self.requests],
            [
                "https://worker.example/app/sessions/s1/prepare",
                "https://worker.example/app/sessions/s1",
            ],
        )
        self.assertEqual(
            [request.get_method() for request in self.requests],
            ["POST", "DELETE"],
        )

    def test_session_resolve_and_card_run_payloads(self) -> None:
        self.install({"session": {"session_id": "s1"}})
        app = CloudApp("https://worker.example", "token")
        app.resolve_session("Evening", by_name=True)
        self.install({"birds": [], "skipped": 0, "skip_reason": ""})
        app.card_run("paddyfield", "R")

        self.assertEqual(
            [request.full_url for request in self.requests],
            [
                "https://worker.example/app/sessions/resolve",
                "https://worker.example/app/cards/run",
            ],
        )
        self.assertEqual(
            [
                json.loads(request.data.decode("utf-8"))
                for request in self.requests
            ],
            [
                {"handle": "Evening", "by_name": True},
                {"q": "paddyfield", "card_type": "R"},
            ],
        )

    def test_session_rename_sets_and_clears_the_name(self) -> None:
        self.install({"session": {}})
        app = CloudApp("https://worker.example", "token")
        app.rename_session("s1", "Evening")
        app.rename_session("s1", None)

        self.assertEqual(
            [request.full_url for request in self.requests],
            [
                "https://worker.example/app/sessions/s1/rename",
                "https://worker.example/app/sessions/s1/rename",
            ],
        )
        self.assertEqual(
            [
                json.loads(request.data.decode("utf-8"))
                for request in self.requests
            ],
            [{"name": "Evening"}, {"name": None}],
        )

    def test_session_ids_are_quoted(self) -> None:
        self.install({"session": {}})
        app = CloudApp("https://worker.example", "token")
        app.session("a/b")
        self.assertEqual(
            self.requests[0].full_url,
            "https://worker.example/app/sessions/a%2Fb",
        )

    def test_stateless_card_calls(self) -> None:
        self.install({"birds": [], "count": 0})
        app = CloudApp("https://worker.example", "token")
        app.search_birds("paddyfield")
        app.card_view("acrocephalus-agricola", "F", 7)
        self.install({"feedback": {"kind": "retry"}})
        app.grade_card(
            "acrocephalus-agricola",
            "F",
            7,
            1,
            response="Corvus corax",
        )

        self.assertEqual(
            [request.full_url for request in self.requests],
            [
                "https://worker.example/app/birds",
                "https://worker.example/app/cards",
                "https://worker.example/app/cards/answer",
            ],
        )
        self.assertEqual(
            json.loads(self.requests[0].data.decode("utf-8")),
            {"q": "paddyfield"},
        )
        self.assertEqual(
            json.loads(self.requests[1].data.decode("utf-8")),
            {
                "species_id": "acrocephalus-agricola",
                "card_type": "F",
                "seed": 7,
            },
        )
        self.assertEqual(
            json.loads(self.requests[2].data.decode("utf-8")),
            {
                "species_id": "acrocephalus-agricola",
                "card_type": "F",
                "seed": 7,
                "attempt": 1,
                "response": "Corvus corax",
            },
        )


if __name__ == "__main__":
    unittest.main()
