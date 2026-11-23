"""Client-local selected session.

The Worker stores sessions but has no notion of an active session. Each client
remembers which session it is looking at; that choice is local state, keyed by
server and account. It never affects another client or the Worker's data.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

STATE_ENV = "BIRDS_TRAINER_STATE"


def state_path() -> Path:
    """Where this client keeps its selections; tests can override it."""
    override = os.environ.get(STATE_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".birds_trainer_state.json"


def _key(server: str, username: str) -> str:
    return f"{server}|{username}"


def _read(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(document, dict):
        return {}
    selections = document.get("selections")
    if not isinstance(selections, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in selections.items()
        if isinstance(key, str) and isinstance(value, str) and value
    }


def load_selected(server: str, username: str) -> str | None:
    """Return this client's selected session id, if any."""
    return _read(state_path()).get(_key(server, username))


def save_selected(
    server: str, username: str, session_id: str
) -> Path:
    """Remember a session as selected for this server and account."""
    logical = str(session_id or "").strip()
    if not logical:
        raise ValueError("session id is required")
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    selections = _read(path)
    selections[_key(server, username)] = logical
    _write(path, {"selections": selections})
    return path


def clear_selected(server: str, username: str) -> None:
    """Forget this client's selected session."""
    path = state_path()
    selections = _read(path)
    if selections.pop(_key(server, username), None) is None:
        return
    _write(path, {"selections": selections})


def _write(path: Path, document: dict[str, Any]) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=".birds_trainer_state.", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
