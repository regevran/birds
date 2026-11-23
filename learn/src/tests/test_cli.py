"""Tests for the Worker-backed text client."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from trainer.cli import (
    _Up,
    _dispatch,
    _interactive,
    _local_time,
    _read_line,
    _practises,
    main,
)
from trainer.foundation.cloud import (
    CloudError,
    Credentials,
    CredentialsError,
    load_credentials,
)

SPECIES = "acrocephalus-agricola"
FIXTURES = Path(__file__).with_name("fixtures") / "worker_cards.json"


def _templates() -> dict[str, dict]:
    cards = json.loads(FIXTURES.read_text(encoding="utf-8"))
    cards["E"] = {
        "card_type": "E",
        "species_id": SPECIES,
        "family": "Acrocephalidae",
        "latin": "Acrocephalus agricola",
        "rows": [
            {
                "element_id": "acro",
                "latin_forms": ["Acro"],
                "theme": "Shape",
                "options": ["פסגה", "ראש"],
            }
        ],
    }
    cards["R"] = {
        "card_type": "R",
        "species_id": SPECIES,
        "family": "Acrocephalidae",
        "hebrew": "קנית אורז",
        "options": [
            {
                "latin": "Acrocephalus agricola",
                "species_id": SPECIES,
            },
            {
                "latin": "Acrocephalus arundinaceus",
                "species_id": "acrocephalus-arundinaceus",
            },
        ],
    }
    return cards


TEMPLATES = _templates()


def _bird(
    species_id: str = SPECIES,
    latin: str = "Acrocephalus agricola",
    english: str = "Paddyfield warbler",
    hebrew: str = "קנית אורז",
    *,
    has_hebrew: bool = True,
    has_parts: bool = True,
) -> dict:
    return {
        "species_id": species_id,
        "latin": latin,
        "english": english,
        "hebrew": hebrew,
        "family": "Acrocephalidae",
        "family_he": "קניתיים",
        "order": "Passeriformes",
        "has_hebrew": has_hebrew,
        "has_parts": has_parts,
        "matched": [],
    }


def _elements_feedback() -> dict:
    return {
        "feedback": {
            "kind": "elements",
            "results": [
                {
                    "element_id": "acro",
                    "chosen": "פסגה",
                    "expected": "פסגה",
                    "correct": True,
                }
            ],
            "correct": 1,
            "total": 1,
        }
    }


def _recognize_retry() -> dict:
    return {
        "feedback": {
            "kind": "retry",
            "chosen": "Acrocephalus arundinaceus",
            "message": "wrong; try again",
        }
    }


def _recognize_result(correct: bool) -> dict:
    return {
        "feedback": {
            "kind": "recognize",
            "result": {
                "chosen": {
                    "latin": "Acrocephalus agricola",
                    "species_id": SPECIES,
                },
                "accepted": ["Acrocephalus agricola"],
                "correct": correct,
            },
        }
    }


def _latin_retry() -> dict:
    return {
        "feedback": {
            "kind": "retry",
            "response": "corvus corax",
            "message": "wrong; try again",
        }
    }


def _latin_result(outcome: str) -> dict:
    if outcome == "correct":
        words = [
            {
                "expected": "acrocephalus",
                "response": "acrocephalus",
                "status": "correct",
                "distance": 0,
            },
            {
                "expected": "agricola",
                "response": "agricola",
                "status": "correct",
                "distance": 0,
            },
        ]
        response = "acrocephalus agricola"
    elif outcome == "near_miss":
        words = [
            {
                "expected": "acrocephalus",
                "response": "acrocephalus",
                "status": "correct",
                "distance": 0,
            },
            {
                "expected": "agricola",
                "response": "agricolo",
                "status": "almost",
                "distance": 1,
            },
        ]
        response = "acrocephalus agricolo"
    else:
        words = [
            {
                "expected": "acrocephalus",
                "response": "corvus",
                "status": "wrong",
                "distance": 8,
            },
            {
                "expected": "agricola",
                "response": "corax",
                "status": "wrong",
                "distance": 6,
            },
        ]
        response = "corvus corax"
    return {
        "feedback": {
            "kind": "latin",
            "result": {
                "response": response,
                "expected": "Acrocephalus agricola",
                "outcome": outcome,
                "genus_ok": outcome == "correct",
                "epithet_ok": outcome == "correct",
                "distance": 0 if outcome == "correct" else 1,
                "words": words,
            },
        }
    }


def _fake_ambiguous(
    subject: str, handle: str, sessions: list[dict]
) -> str:
    lines = [
        f"  {session.get('session_id', '')} '{session.get('name')}'"
        for session in sessions
    ]
    return (
        f"{subject} '{handle}' is ambiguous; use an id:\n"
        + "\n".join(lines)
    )


class FakeCloudApp:
    """Stand-in for the Worker session and card API in CLI tests."""

    def __init__(self, server: str, token: str) -> None:
        self.server = server
        self.username = "ran"
        self.searches: list[str] = []
        self.search_results: list[dict] = []
        self.search_elements: list[dict] = []
        self.search_error: Exception | None = None
        self.card_runs: list[tuple[str, str]] = []
        self.card_run_birds: list[dict] | None = None
        self.card_run_skipped = 0
        self.card_run_reason = ""
        self.card_run_error: Exception | None = None
        self.card_templates: dict[str, dict] = {}
        self.cards: list[tuple[str, str, int]] = []
        self.grades: list[tuple] = []
        self.grade_results: list[dict] = []
        self.pending_errors: list[Exception] = []

        self.created: dict | None = None
        self.current_view: dict | None = None
        self.answer_view: dict | None = None
        self.feedback: dict | None = None
        self.calls: list[tuple] = []
        self.sessions: list[dict] = [
            {
                "session_id": "s1",
                "name": "Test",
                "session_card_count": 0,
                "queue_size": 5,
                "pool_size": 0,
            }
        ]
        self.selected_session_id: str | None = "s1"
        self.selected_saves: list[tuple[str, str]] = []
        self.missing_sessions: set[str] = set()
        self.prepared: list[str] = []
        self.deleted: list[str] = []
        self.renamed: list[tuple[str, str | None]] = []
        self.rename_error: Exception | None = None
        self.resolve_calls: list[tuple[str, bool]] = []
        self.resolve_error: Exception | None = None
        self.delete_error: Exception | None = None

    def search_birds(self, query: str = ""):
        self.searches.append(query)
        if self.search_error is not None:
            raise self.search_error
        return {
            "birds": self.search_results,
            "elements": self.search_elements,
            "count": len(self.search_results),
        }

    def card_view(self, species_id: str, card_type: str, seed: int = 0):
        self.cards.append((species_id, card_type, seed))
        template = self.card_templates.get(card_type.upper())
        if template is None:
            raise CloudError(404, "bird_not_found", "bird not found")
        card = deepcopy(template)
        card["species_id"] = species_id
        return {"card": card}

    def card_run(self, query: str, card_type: str):
        self.card_runs.append((query, card_type))
        if self.card_run_error is not None:
            raise self.card_run_error
        birds = (
            self.search_results
            if self.card_run_birds is None
            else self.card_run_birds
        )
        return {
            "birds": birds,
            "skipped": self.card_run_skipped,
            "skip_reason": self.card_run_reason,
        }

    def grade_card(
        self,
        species_id: str,
        card_type: str,
        seed: int = 0,
        attempt: int = 1,
        *,
        choices=None,
        choice=None,
        response=None,
    ):
        self.grades.append(
            (species_id, card_type, seed, attempt, choices, choice, response)
        )
        if self.pending_errors:
            raise self.pending_errors.pop(0)
        if not self.grade_results:
            raise AssertionError("unexpected grade_card call")
        return self.grade_results.pop(0)

    def create_session(self, **kwargs):
        self.created = kwargs
        if self.current_view is None:
            return None
        view = deepcopy(self.current_view)
        view["session"]["name"] = kwargs.get("name")
        return view

    def list_sessions(self):
        return {"sessions": self.sessions}

    def resolve_session(self, handle: str, *, by_name: bool = False):
        self.resolve_calls.append((handle, by_name))
        if self.resolve_error is not None:
            raise self.resolve_error
        wanted = handle.strip().lower()
        names = [
            session
            for session in self.sessions
            if str(session.get("name") or "").strip().lower() == wanted
        ]
        if by_name:
            if not names:
                raise CloudError(
                    404,
                    "session_not_found",
                    f"no session named '{handle}'",
                )
            if len(names) > 1:
                raise CloudError(
                    409,
                    "session_ambiguous",
                    _fake_ambiguous("session name", handle, names),
                )
            return {"session": self._summary(names[0])}
        if len(names) > 1:
            raise CloudError(
                409,
                "session_ambiguous",
                _fake_ambiguous("session name", handle, names),
            )
        if names:
            return {"session": self._summary(names[0])}
        exact = [
            session
            for session in self.sessions
            if str(session.get("session_id", "")).lower() == wanted
        ]
        if exact:
            return {"session": self._summary(exact[0])}
        prefixed = [
            session
            for session in self.sessions
            if str(session.get("session_id", "")).lower().startswith(wanted)
        ]
        if not prefixed:
            raise CloudError(
                404,
                "session_not_found",
                f"no session matches '{handle}'",
            )
        if len(prefixed) > 1:
            raise CloudError(
                409,
                "session_ambiguous",
                _fake_ambiguous("session id prefix", handle, prefixed),
            )
        return {"session": self._summary(prefixed[0])}

    def _summary(self, session: dict) -> dict:
        return dict(session)

    def load_selected(self, server: str, username: str):
        return self.selected_session_id

    def save_selected(
        self, server: str, username: str, session_id: str
    ) -> None:
        self.selected_session_id = session_id
        self.selected_saves.append((server, session_id))

    def session(self, session_id: str):
        if session_id in self.missing_sessions:
            raise CloudError(
                404, "session_not_found", "session not found"
            )
        return self.current_view

    def prepare_session(self, session_id: str):
        if session_id in self.missing_sessions:
            raise CloudError(
                404, "session_not_found", "session not found"
            )
        self.prepared.append(session_id)
        return self.current_view

    def rename_session(self, session_id: str, name: str | None):
        self.renamed.append((session_id, name))
        if self.rename_error is not None:
            raise self.rename_error
        if self.current_view is None:
            return None
        view = deepcopy(self.current_view)
        view["session"]["name"] = name
        return view

    def delete_session(self, session_id: str) -> None:
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.append(session_id)

    def answer(self, session_id, card_uid, action, **kwargs):
        self.calls.append((session_id, card_uid, action, kwargs))
        if self.pending_errors:
            raise self.pending_errors.pop(0)
        return {
            "feedback": self.feedback,
            "session": self.answer_view,
        }


def _credentials() -> Credentials:
    return Credentials(
        server="https://worker.example",
        username="ran",
        scope="profile",
        token="token-value",
        expires_at="2999-01-01T00:00:00Z",
    )


def _patches(app: FakeCloudApp):
    return (
        patch(
            "trainer.cli.cloud.load_credentials",
            return_value=_credentials(),
        ),
        patch("trainer.cli.cloud.CloudApp", return_value=app),
        patch(
            "trainer.cli.selection.load_selected",
            side_effect=app.load_selected,
        ),
        patch(
            "trainer.cli.selection.save_selected",
            side_effect=app.save_selected,
        ),
    )


def _run(
    app: FakeCloudApp,
    args: list[str],
    *,
    responses: list[str] | None = None,
    interactive: bool = False,
    reverse_hebrew: bool = False,
) -> str:
    output = io.StringIO()
    credentials_patch, app_patch, load_patch, save_patch = _patches(app)
    with credentials_patch, app_patch, load_patch, save_patch, redirect_stdout(output):
        if responses is None:
            _dispatch(args, reverse_hebrew, interactive=interactive)
        else:
            with patch("builtins.input", side_effect=responses):
                _dispatch(args, reverse_hebrew, interactive=interactive)
    return output.getvalue()


def _app() -> FakeCloudApp:
    app = FakeCloudApp("", "")
    app.card_templates = deepcopy(TEMPLATES)
    app.search_results = [_bird()]
    return app


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


class HelpTests(unittest.TestCase):
    def test_long_and_short_help(self) -> None:
        for flag in ("--help", "-h"):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main([flag]), 0)
            text = output.getvalue()
            self.assertIn("Usage: python3 -m trainer", text)
            self.assertIn("session new [X]", text)
            self.assertIn("login --server", text)
            self.assertIn("CLI-USAGE.md", text)

    def test_help_with_no_reverse_flag(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--no-reverse-hebrew", "--help"]), 0)
        self.assertIn("Usage: python3 -m trainer", output.getvalue())

    def _help_text(self, args: list[str]) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 0)
        return output.getvalue()

    def test_card_type_help_splits_seed_usage(self) -> None:
        for card_type in ("E", "R"):
            text = self._help_text(["card", card_type, "--help"])
            self.assertIn(f"Usage: card {card_type}", text)
            self.assertIn("--seed N", text)
        for card_type in ("C", "F"):
            text = self._help_text(["card", card_type, "--help"])
            self.assertIn(f"Usage: card {card_type}", text)
            self.assertNotIn("--seed", text)

    def test_card_alias_help(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["F", "--help"]), 0)
        self.assertIn("Usage: card F", output.getvalue())

    def test_session_action_help(self) -> None:
        text = self._help_text(["session", "new", "--help"])
        self.assertIn("Usage: session new [X | --name X]", text)
        self.assertIn("--active-cap", text)
        self.assertIn("X is the new name", text)
        self.assertIn("default", text)
        self.assertIn("AND between options", text)
        self.assertIn("OR within one option", text)
        text = self._help_text(["session", "run", "--help"])
        self.assertIn("Usage: session run", text)
        self.assertIn("resume", text)
        text = self._help_text(["session", "rename", "--help"])
        self.assertIn("Usage: session rename OLD [NEW]", text)
        self.assertIn("--clear", text)

    def test_session_help_has_no_close(self) -> None:
        text = self._help_text(["session", "--help"])
        self.assertNotIn("close", text)
        self.assertIn("selected", text)
        self.assertIn("default", text)

    def test_help_command_with_target(self) -> None:
        self.assertIn("Usage: card E", self._help_text(["help", "card", "E"]))
        self.assertIn(
            "Usage: session new",
            self._help_text(["help", "session", "new"]),
        )
        self.assertIn("Usage: /<text>", self._help_text(["help", "search"]))

    def test_session_help_documents_counters(self) -> None:
        text = self._help_text(["session", "--help"])
        for term in ("cards", "queue", "pool"):
            self.assertIn(term, text)

    def test_search_help(self) -> None:
        self.assertIn("Usage: /<text>", self._help_text(["search", "--help"]))


class StandaloneCardTests(unittest.TestCase):
    def _run_main(self, args: list[str], responses: list[str] | None = None):
        app = _app()
        app.grade_results = [_latin_result("correct")]
        output = io.StringIO()
        credentials_patch, app_patch, load_patch, save_patch = _patches(app)
        with credentials_patch, app_patch, load_patch, save_patch, redirect_stdout(output):
            if responses is None:
                self.assertEqual(main(args), 0)
            else:
                with patch("builtins.input", side_effect=responses):
                    self.assertEqual(main(args), 0)
        return app, output.getvalue()

    def test_typed_card_prompts_from_a_shell(self) -> None:
        app = _app()
        app.grade_results = [_latin_result("correct")]
        output = io.StringIO()
        credentials_patch, app_patch, load_patch, save_patch = _patches(app)
        with credentials_patch, app_patch, load_patch, save_patch, redirect_stdout(output):
            with patch(
                "builtins.input", side_effect=["Acrocephalus agricola"]
            ) as ask:
                self.assertEqual(main(["card", "C", "acro"]), 0)
        self.assertIn("Latin:", ask.call_args_list[0].args[0])
        self.assertEqual(len(app.grades), 1)
        self.assertEqual(app.grades[0][1], "C")

    def test_card_alias_practises(self) -> None:
        app, _ = self._run_main(["C", "acro"], ["Acrocephalus agricola"])
        self.assertEqual(len(app.grades), 1)

    def test_learn_card_only_prints(self) -> None:
        app, text = self._run_main(["card", "L", "acro"])
        self.assertEqual(app.grades, [])
        self.assertIn("Acrocephalus agricola", text)

    def test_practises_predicate(self) -> None:
        self.assertTrue(_practises(["card", "E", "x"]))
        self.assertTrue(_practises(["R", "x"]))
        self.assertTrue(_practises(["c", "x"]))
        self.assertFalse(_practises(["card", "L", "x"]))
        self.assertFalse(_practises(["card"]))
        self.assertFalse(_practises(["search", "x"]))


class LocalTimeTests(unittest.TestCase):
    def test_utc_timestamp_is_rendered_locally(self) -> None:
        expected = datetime.fromisoformat(
            "2026-12-22T17:16:01+00:00"
        ).astimezone()
        zone = expected.strftime("%Z") or expected.strftime("%z")
        self.assertEqual(
            _local_time("2026-12-22T17:16:01.000Z"),
            f"{expected:%Y-%m-%d %H:%M:%S} {zone}".strip(),
        )

    def test_invalid_timestamp_is_returned_unchanged(self) -> None:
        self.assertEqual(_local_time("not-a-time"), "not-a-time")


class InteractiveExitTests(unittest.TestCase):
    def test_ctrl_c_leaves_client(self) -> None:
        with patch("trainer.cli._enable_line_editing"):
            with patch("builtins.input", side_effect=KeyboardInterrupt):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(_interactive(False), 0)

    def test_exit_at_card_prompt_leaves_client(self) -> None:
        with patch("trainer.cli._enable_line_editing"):
            with patch("builtins.input", return_value="exit"):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(_interactive(False), 0)


class SearchAndCardTests(unittest.TestCase):
    def test_search_lists_worker_results(self) -> None:
        app = _app()
        text = _run(app, ["search", "paddyfield"])
        self.assertIn("1 bird matching 'paddyfield'", text)
        self.assertIn("acrocephalus-agricola", text)
        self.assertIn("Paddyfield warbler", text)
        self.assertEqual(app.searches, ["paddyfield"])

    def _element_app(self, field: str = "en", text: str = "locust"):
        app = _app()
        bird = _bird()
        bird["matched"] = [
            {
                "kind": "element",
                "element_id": "acrido",
                "texts": [{"field": field, "text": text}],
            }
        ]
        app.search_results = [bird]
        app.search_elements = [
            {
                "element_id": "acrido",
                "en": "locust",
                "he": "חגב",
                "theme": "Food",
                "origin": "Greek",
                "bird_count": 2,
                "matched": [{"field": field, "text": text}],
            }
        ]
        return app

    def test_element_match_names_the_gloss(self) -> None:
        app = self._element_app()
        text = _run(app, ["search", "locust"])
        self.assertIn("acrido (=locust)", text)
        self.assertIn("Elements matching 'locust' (1)", text)
        self.assertIn("Food · Greek", text)
        self.assertIn("2 birds", text)

    def test_hebrew_match_is_rendered_reversed(self) -> None:
        app = self._element_app("he", "חגב")
        plain = _run(app, ["search", "חגב"])
        self.assertIn("acrido (=חגב)", plain)
        reversed_text = _run(app, ["search", "חגב"], reverse_hebrew=True)
        self.assertIn("matching 'בגח'", reversed_text)
        self.assertIn("acrido (=בגח)", reversed_text)
        self.assertIn("locust · בגח", reversed_text)

    def test_form_match_shows_the_matched_text(self) -> None:
        app = self._element_app("form", "leucos")
        text = _run(app, ["search", "leucos"])
        self.assertIn("acrido (=leucos)", text)
        self.assertIn("(=leucos)", text)

    def test_name_only_search_keeps_the_old_table(self) -> None:
        app = _app()
        text = _run(app, ["search", "paddyfield"])
        self.assertNotIn("Hebrew family matched", text)
        self.assertNotIn("Elements matching", text)

    def test_order_match_is_annotated(self) -> None:
        app = _app()
        bird = _bird()
        bird["matched"] = [
            {
                "kind": "name",
                "texts": [{"field": "order", "text": "Passeriformes"}],
            }
        ]
        app.search_results = [bird]
        text = _run(app, ["search", "Passeriformes"])
        self.assertIn("name (=Passeriformes)", text)

    def test_name_and_element_matches_are_both_shown(self) -> None:
        app = self._element_app()
        app.search_results[0]["matched"].insert(
            0,
            {
                "kind": "name",
                "texts": [
                    {"field": "english", "text": "Paddyfield warbler"}
                ],
            },
        )
        text = _run(app, ["search", "locust"])
        self.assertIn("name, acrido (=locust)", text)

    def test_unknown_match_kind_is_rejected(self) -> None:
        app = _app()
        bird = _bird()
        bird["matched"] = [{"kind": "theme"}]
        app.search_results = [bird]
        text = _run(app, ["search", "locust"])
        self.assertIn("invalid Worker search response", text)

    def test_response_without_elements_is_rejected(self) -> None:
        app = _app()
        app.search_birds = lambda query: {
            "birds": [_bird()],
            "count": 1,
        }
        text = _run(app, ["search", "paddyfield"])
        self.assertIn("invalid Worker search response", text)

    def test_bird_without_matched_is_rejected(self) -> None:
        app = _app()
        bird = _bird()
        del bird["matched"]
        app.search_results = [bird]
        text = _run(app, ["search", "paddyfield"])
        self.assertIn("invalid Worker search response", text)

    def test_search_failure_names_the_server_and_status(self) -> None:
        app = _app()
        app.server = "https://worker.example"
        app.search_error = CloudError(404, "not_found", "not found")
        text = _run(app, ["search", "paddyfield"])
        self.assertIn("search failed at https://worker.example", text)
        self.assertIn("not_found (HTTP 404)", text)

    def test_search_without_login_explains(self) -> None:
        output = io.StringIO()
        with patch(
            "trainer.cli.cloud.load_credentials",
            side_effect=CredentialsError("not logged in"),
        ), redirect_stdout(output):
            _dispatch(["search", "paddyfield"], False)
        self.assertIn("not logged in", output.getvalue())

    def test_card_accepts_multiword_name_and_renders_worker_view(self) -> None:
        app = _app()
        text = _run(
            app, ["card", "L", "paddyfield", "warbler"]
        )
        self.assertIn("[L] Acrocephalus agricola", text)
        self.assertEqual(app.card_runs, [("paddyfield warbler", "L")])
        self.assertEqual(app.cards, [(SPECIES, "L", 0)])

    def test_unknown_card_options_are_rejected(self) -> None:
        app = _app()
        text = _run(app, ["card", "F", "paddyfield", "--reveal"])
        self.assertIn("unknown option", text)
        self.assertEqual(app.cards, [])

    def test_multi_match_run_skips_ineligible_birds(self) -> None:
        app = _app()
        app.search_results = [
            _bird(),
            _bird(
                "other-bird",
                "Other bird",
                "Other",
                "",
                has_hebrew=False,
            ),
        ]
        app.card_run_birds = [_bird()]
        app.card_run_skipped = 1
        app.card_run_reason = "no Hebrew"
        text = _run(app, ["card", "F", "warbler"])
        self.assertIn("1 bird matching 'warbler' (1 skipped: no Hebrew)", text)
        self.assertEqual(app.card_runs, [("warbler", "F")])
        self.assertEqual(len(app.cards), 1)

    def test_search_mode_searches_through_the_worker(self) -> None:
        app = _app()
        text = _run(
            app,
            ["/"],
            responses=["paddyfield", "exit"],
            interactive=True,
        )
        self.assertIn("Search mode:", text)
        self.assertIn("1 bird matching 'paddyfield'", text)
        self.assertEqual(app.searches, ["paddyfield"])

    def test_interactive_uses_random_seed(self) -> None:
        app = _app()
        app.grade_results = [_elements_feedback()]
        with patch("trainer.cli.secrets.randbelow", return_value=7) as rnd:
            _run(
                app,
                ["card", "E", "paddyfield"],
                responses=["1"],
                interactive=True,
            )
        rnd.assert_called_once()
        self.assertEqual(app.cards, [(SPECIES, "E", 7)])

    def test_explicit_seed_beats_random(self) -> None:
        app = _app()
        app.grade_results = [_elements_feedback()]
        with patch("trainer.cli.secrets.randbelow") as rnd:
            _run(
                app,
                ["card", "E", "paddyfield", "--seed", "3"],
                responses=["1"],
                interactive=True,
            )
        rnd.assert_not_called()
        self.assertEqual(app.cards, [(SPECIES, "E", 3)])


class InteractiveElementTests(unittest.TestCase):
    def test_elements_are_graded_by_the_worker(self) -> None:
        app = _app()
        app.grade_results = [_elements_feedback()]
        text = _run(
            app,
            ["card", "E", "paddyfield", "--seed", "0"],
            responses=["1"],
            interactive=True,
        )
        self.assertIn("(Acrocephalidae)", text)
        self.assertIn("1/1 correct.", text)
        self.assertEqual(
            app.grades,
            [(SPECIES, "E", 0, 1, {"acro": "פסגה"}, None, None)],
        )


class InteractiveRecognizeTests(unittest.TestCase):
    def test_wrong_once_then_correct(self) -> None:
        app = _app()
        app.grade_results = [_recognize_retry(), _recognize_result(True)]
        text = _run(
            app,
            ["card", "R", "paddyfield", "--seed", "0"],
            responses=["2", "1"],
            interactive=True,
        )
        self.assertIn("wrong: chose 'Acrocephalus arundinaceus'", text)
        self.assertIn("correct: 'Acrocephalus agricola'", text)
        self.assertEqual(
            [grade[3] for grade in app.grades],
            [1, 2],
        )

    def test_wrong_twice_returns_the_full_result(self) -> None:
        app = _app()
        app.grade_results = [_recognize_retry(), _recognize_result(False)]
        text = _run(
            app,
            ["card", "R", "paddyfield", "--seed", "0"],
            responses=["2", "2"],
            interactive=True,
        )
        self.assertIn("wrong: chose", text)
        self.assertEqual(len(app.grades), 2)


class InteractiveTypedTests(unittest.TestCase):
    def test_near_miss_on_the_second_attempt(self) -> None:
        app = _app()
        app.grade_results = [_latin_retry(), _latin_result("near_miss")]
        text = _run(
            app,
            ["card", "F", "paddyfield", "--seed", "0"],
            responses=["Corvus corax", "Acrocephalus agricolo"],
            interactive=True,
        )
        self.assertIn("wrong: chose 'corvus corax'", text)
        self.assertIn("almost:", text)
        self.assertEqual([grade[3] for grade in app.grades], [1, 2])

    def test_second_wrong_reveals_the_answer(self) -> None:
        app = _app()
        app.grade_results = [_latin_retry(), _latin_result("wrong")]
        text = _run(
            app,
            ["card", "C", "paddyfield", "--seed", "0"],
            responses=["Corvus corax", "Corvus corax"],
            interactive=True,
        )
        self.assertIn("wrong: chose 'corvus corax'", text)
        self.assertIn("correct 'Acrocephalus agricola'", text)
        self.assertEqual(len(app.grades), 2)

    def test_correct_first_try(self) -> None:
        app = _app()
        app.grade_results = [_latin_result("correct")]
        text = _run(
            app,
            ["card", "F", "paddyfield", "--seed", "0"],
            responses=["Acrocephalus agricola"],
            interactive=True,
        )
        self.assertIn("correct: 'Acrocephalus agricola'", text)

    def test_multi_match_run_covers_both_birds(self) -> None:
        app = _app()
        app.search_results = [
            _bird(),
            _bird("other-bird", "Other bird", "Other"),
        ]
        app.grade_results = [
            _latin_result("correct"),
            _latin_result("correct"),
        ]
        text = _run(
            app,
            ["card", "F", "warbler", "--seed", "0"],
            responses=[
                "Acrocephalus agricola",
                "",
                "Acrocephalus agricola",
            ],
            interactive=True,
        )
        self.assertIn("2 birds matching 'warbler'", text)
        self.assertIn("F run complete: 2 cards", text)
        self.assertEqual(len(app.grades), 2)


class CredentialCommandTests(unittest.TestCase):
    def _run(self, args: list[str]) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            _dispatch(args, False)
        return output.getvalue()

    def test_login_whoami_logout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "credentials.json"
            credentials = _credentials()
            with patch.dict(
                os.environ, {"BIRDS_TRAINER_CREDENTIALS": str(path)}
            ):
                with patch(
                    "trainer.cli.cloud.login", return_value=credentials
                ) as login:
                    with patch(
                        "trainer.cli.getpass.getpass", return_value="pw"
                    ):
                        text = self._run(
                            [
                                "login",
                                "--server",
                                "https://worker.example",
                                "--username",
                                "ran",
                            ]
                        )
                login.assert_called_once_with(
                    "https://worker.example", "ran", "pw"
                )
                self.assertIn("Logged in as ran (profile)", text)
                self.assertEqual(load_credentials(path=path), credentials)

                self.assertIn("ran (profile)", self._run(["whoami"]))
                self.assertIn("Logged out.", self._run(["logout"]))
                with self.assertRaises(CredentialsError):
                    load_credentials(path=path)
                self.assertIn("not logged in", self._run(["whoami"]))

    def test_login_failure_keeps_no_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "credentials.json"
            with patch.dict(
                os.environ, {"BIRDS_TRAINER_CREDENTIALS": str(path)}
            ):
                with patch(
                    "trainer.cli.cloud.login",
                    side_effect=CloudError(
                        401,
                        "invalid_credentials",
                        "invalid username or password",
                    ),
                ):
                    with patch(
                        "trainer.cli.getpass.getpass", return_value="pw"
                    ):
                        text = self._run(
                            [
                                "login",
                                "--server",
                                "https://worker.example",
                                "--username",
                                "ran",
                            ]
                        )
                self.assertIn("login failed:", text)
                self.assertFalse(path.exists())

    def test_login_needs_a_server(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "credentials.json"
            with patch.dict(
                os.environ,
                {
                    "BIRDS_TRAINER_CREDENTIALS": str(path),
                    "BIRDS_TRAINER_SERVER": "",
                },
            ):
                text = self._run(["login", "--username", "ran"])
                self.assertIn("usage: login --server", text)


def _session_view(card=None, *, status="active", count=0, queue=5):
    return {
        "session": {
            "session_id": "s1",
            "name": "Test",
            "status": status,
            "session_card_count": count,
            "global_counter": count,
            "initial_pool_size": 1,
            "pool_size": 0,
            "queue_size": queue,
        },
        "current": (
            None
            if card is None
            else {
                "uid": "c1",
                "type": card["card_type"],
                "attempt": 1,
                "retry": False,
                "revealed": False,
                "card": card,
            }
        ),
        "lookahead": [],
    }


class SessionCommandTests(unittest.TestCase):
    def test_session_new_builds_a_filter_and_prints_a_summary(self) -> None:
        app = FakeCloudApp("", "")
        app.current_view = _session_view(deepcopy(TEMPLATES["L"]))
        text = _run(
            app,
            [
                "session",
                "new",
                "passers",
                "--search",
                "paddyfield warbler",
                "--status",
                "accidental",
                "--active-cap",
                "1",
            ],
        )
        self.assertIn("* passers", text)
        self.assertIn("Practise with: session run", text)
        self.assertNotIn("[L]", text)
        self.assertEqual(
            app.created,
            {
                "name": "passers",
                "filter": {
                    "statuses": ["accidental"],
                    "search": "paddyfield warbler",
                },
                "settings": {"active_cap": 1},
                "seed": None,
            },
        )

    def test_session_new_without_a_name_creates_an_unnamed_session(self) -> None:
        app = FakeCloudApp("", "")
        app.current_view = _session_view(deepcopy(TEMPLATES["L"]))
        text = _run(app, ["session", "new", "--search", "paddyfield"])
        self.assertIn("(unnamed)", text)
        self.assertIsNone(app.created["name"])

    def test_session_new_rejects_a_positional_and_flag_name(self) -> None:
        app = FakeCloudApp("", "")
        text = _run(app, ["session", "new", "one", "--name", "two"])
        self.assertIn("give the session name once", text)
        self.assertIsNone(app.created)

    def test_ambiguous_session_names_list_candidates(self) -> None:
        app = FakeCloudApp("", "")
        for session_id in ("a1", "a2"):
            app.sessions.append(
                {
                    "session_id": session_id,
                    "name": "dup",
                    "session_card_count": 0,
                    "queue_size": 1,
                    "pool_size": 0,
                }
            )
        text = _run(app, ["session", "status", "--name", "dup"])
        self.assertIn("error: session name 'dup' is ambiguous; use an id:", text)
        self.assertIn("a1 'dup'", text)
        self.assertIn("a2 'dup'", text)

    def test_session_list_marks_the_selected_session(self) -> None:
        app = FakeCloudApp("", "")
        app.sessions = [
            {
                "session_id": "default",
                "name": "default",
                "session_card_count": 0,
                "queue_size": 7,
                "pool_size": 500,
            },
            {
                "session_id": "s1",
                "name": "Test",
                "session_card_count": 3,
                "queue_size": 5,
                "pool_size": 10,
            },
        ]
        text = _run(app, ["session", "list"])
        self.assertIn("  default", text)
        self.assertIn("* Test", text)
        self.assertIn("cards 3", text)
        self.assertNotIn("open", text)

    def test_session_run_advances_the_selected_session(self) -> None:
        app = FakeCloudApp("", "")
        app.current_view = _session_view(deepcopy(TEMPLATES["L"]))
        app.answer_view = _session_view(None, status="completed", queue=0)
        text = _run(app, ["session", "run"], responses=[""])
        self.assertIn("* Test", text)
        self.assertIn("[L] Acrocephalus agricola", text)
        self.assertIn("Session complete.", text)
        self.assertEqual(app.prepared, ["s1"])
        self.assertEqual(app.calls, [("s1", "c1", "advance", {})])

    def test_session_run_switches_to_the_named_session(self) -> None:
        app = FakeCloudApp("", "")
        app.sessions.append(
            {
                "session_id": "s2",
                "name": "Other",
                "session_card_count": 0,
                "queue_size": 1,
                "pool_size": 0,
            }
        )
        app.current_view = _session_view(deepcopy(TEMPLATES["L"]))
        app.answer_view = _session_view(None, status="completed", queue=0)
        _run(
            app,
            ["session", "run", "--name", "Other"],
            responses=[""],
        )
        self.assertEqual(app.prepared, ["s2"])
        self.assertEqual(app.selected_session_id, "s2")

    def test_session_status_reads_a_session_without_switching(self) -> None:
        app = FakeCloudApp("", "")
        app.sessions.append(
            {
                "session_id": "s2",
                "name": "Other",
                "session_card_count": 0,
                "queue_size": 1,
                "pool_size": 0,
            }
        )
        view = _session_view(deepcopy(TEMPLATES["L"]))
        view["session"]["session_id"] = "s2"
        view["session"]["name"] = "Other"
        app.current_view = view
        text = _run(app, ["session", "status", "Other"])
        self.assertIn("  Other", text)
        self.assertNotIn("* Other", text)
        self.assertIn("[L] Acrocephalus agricola", text)
        self.assertEqual(app.selected_session_id, "s1")

    def test_session_rename_sets_and_clears_the_name(self) -> None:
        app = FakeCloudApp("", "")
        app.current_view = _session_view(deepcopy(TEMPLATES["L"]))
        text = _run(app, ["session", "rename", "Test", "Evening"])
        self.assertEqual(app.renamed, [("s1", "Evening")])
        self.assertIn("* Evening", text)
        text = _run(app, ["session", "rename", "s1"])
        self.assertEqual(app.renamed[-1], ("s1", None))
        self.assertIn("(unnamed)", text)
        text = _run(app, ["session", "rename", "--name", "Test", "--clear"])
        self.assertEqual(app.renamed[-1], ("s1", None))
        self.assertIn("(unnamed)", text)

    def test_session_rename_rejects_a_name_together_with_clear(self) -> None:
        app = FakeCloudApp("", "")
        text = _run(
            app, ["session", "rename", "s1", "Evening", "--clear"]
        )
        self.assertIn("give a new name or --clear, not both", text)
        self.assertEqual(app.renamed, [])

    def test_session_rename_protects_default(self) -> None:
        app = FakeCloudApp("", "")
        app.sessions.append(
            {
                "session_id": "default",
                "name": "default",
                "session_card_count": 0,
                "queue_size": 7,
                "pool_size": 500,
            }
        )
        app.rename_error = CloudError(
            409,
            "session_default",
            "the default session cannot be renamed: "
            "default 'default' (protected)",
        )
        text = _run(app, ["session", "rename", "default", "Evening"])
        self.assertIn(
            "error: the default session cannot be renamed: "
            "default 'default' (protected)",
            text,
        )

    def test_session_semantic_errors_are_short(self) -> None:
        app = FakeCloudApp("", "")
        app.current_view = _session_view(deepcopy(TEMPLATES["L"]))
        app.rename_error = CloudError(
            409,
            "session_name_taken",
            "session name 'morning' is taken by: "
            "3452-43B 'MoRnInG' (case-insensitive name collision)",
        )
        text = _run(app, ["session", "rename", "s1", "morning"])
        self.assertIn(
            "error: session name 'morning' is taken by: "
            "3452-43B 'MoRnInG' (case-insensitive name collision)",
            text,
        )
        self.assertNotIn("failed at", text)

    def test_session_delete_protects_default_and_falls_back(self) -> None:
        app = FakeCloudApp("", "")
        app.sessions = [
            {
                "session_id": "default",
                "name": "default",
                "session_card_count": 0,
                "queue_size": 7,
                "pool_size": 500,
            },
            {
                "session_id": "s1",
                "name": "Test",
                "session_card_count": 0,
                "queue_size": 5,
                "pool_size": 0,
            },
        ]
        text = _run(app, ["session", "delete", "s1"])
        self.assertIn("Deleted Test.", text)
        self.assertIn("using default.", text)
        self.assertEqual(app.deleted, ["s1"])
        self.assertEqual(app.selected_session_id, "default")
        app.delete_error = CloudError(
            409,
            "session_default",
            "the default session cannot be deleted: "
            "default 'default' (protected)",
        )
        text = _run(app, ["session", "delete", "--name", "default"])
        self.assertIn("default session cannot be deleted", text)
        self.assertEqual(app.deleted, ["s1"])

    def test_session_delete_removes_another_session(self) -> None:
        app = FakeCloudApp("", "")
        app.sessions.append(
            {
                "session_id": "s2",
                "name": "Other",
                "session_card_count": 0,
                "queue_size": 1,
                "pool_size": 0,
            }
        )
        text = _run(app, ["session", "delete", "s2"])
        self.assertEqual(app.deleted, ["s2"])
        self.assertEqual(app.selected_session_id, "s1")
        self.assertIn("Deleted Other.", text)

    def test_session_prefixes_and_names_resolve(self) -> None:
        app = FakeCloudApp("", "")
        app.sessions.append(
            {
                "session_id": "s10",
                "name": "Ten",
                "session_card_count": 0,
                "queue_size": 1,
                "pool_size": 0,
            }
        )
        text = _run(app, ["session", "open", "s1", "s10"])
        self.assertIn("only one session may", text)
        text = _run(app, ["session", "open", "s"])
        self.assertIn("error: session id prefix 's' is ambiguous", text)
        self.assertIn("s1 'Test'", text)
        self.assertIn("s10 'Ten'", text)
        text = _run(app, ["session", "open", "S"])
        self.assertIn("error: session id prefix 'S' is ambiguous", text)
        _run(app, ["session", "open", "S1"])
        _run(app, ["session", "open", "--name", "Ten"])
        self.assertEqual(app.selected_session_id, "s10")
        self.assertEqual(
            app.resolve_calls[-2:], [("S1", False), ("Ten", True)]
        )
        self.assertEqual(
            app.selected_saves[-2:],
            [("", "s1"), ("", "s10")],
        )

    def test_missing_selected_session_falls_back_to_default(self) -> None:
        app = FakeCloudApp("", "")
        app.current_view = _session_view(deepcopy(TEMPLATES["L"]))
        app.selected_session_id = "gone"
        app.missing_sessions = {"gone"}
        text = _run(app, ["session", "status"])
        self.assertIn("selected session 'gone' no longer exists", text)
        self.assertEqual(app.selected_session_id, "default")
        self.assertIn("* Test", text)

    def test_session_run_reloads_after_a_revision_conflict(self) -> None:
        app = FakeCloudApp("", "")
        app.current_view = _session_view(deepcopy(TEMPLATES["L"]))
        app.answer_view = _session_view(None, status="completed", queue=0)
        app.pending_errors = [
            CloudError(412, "revision_conflict", "state changed")
        ]
        text = _run(app, ["session", "run"], responses=["", ""])
        self.assertIn("state changed in another client", text)
        self.assertIn("Session complete.", text)
        self.assertEqual(len(app.calls), 2)


    def test_session_run_reloads_after_a_stale_card(self) -> None:
        app = FakeCloudApp("", "")
        app.current_view = _session_view(deepcopy(TEMPLATES["L"]))
        app.answer_view = _session_view(None, status="completed", queue=0)
        app.pending_errors = [
            CloudError(409, "stale_card", "card is no longer current")
        ]
        text = _run(app, ["session", "run"], responses=["", ""])
        self.assertIn("state changed in another client", text)
        self.assertIn("Session complete.", text)
        self.assertEqual(len(app.calls), 2)


if __name__ == "__main__":
    unittest.main()
