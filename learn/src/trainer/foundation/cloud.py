"""HTTP client for the Cloudflare Worker.

``CloudFiles`` is the raw scoped file API. ``CloudApp`` calls the trainer API
for search, card views, grading and sessions. This module has no trainer rules.
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT = 30.0
USER_AGENT = "BirdsTrainer/0.1"
CREDENTIALS_ENV = "BIRDS_TRAINER_CREDENTIALS"
SERVER_ENV = "BIRDS_TRAINER_SERVER"


class CloudError(Exception):
    """A failed Worker request."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status  # e.g. 401
        self.code = code  # e.g. "invalid_credentials"
        self.message = message  # e.g. "invalid username or password"


class CredentialsError(Exception):
    """No usable stored login."""


@dataclass(frozen=True)
class Credentials:
    """The stored result of one successful login."""

    server: str  # e.g. "https://birds-progress.regevran.workers.dev"
    username: str  # e.g. "ran"
    scope: str  # e.g. "profile"
    token: str  # e.g. "eyJ1IjoicmFuIn0.signature"
    expires_at: str  # e.g. "2026-12-22T14:00:00.000Z"


def normalize_server(value: str) -> str:
    """Return a scheme and host without a trailing slash.

    The Worker lives at the origin; a path, query or fragment is rejected so a
    typo does not silently point the client at a different endpoint.
    """
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("server URL is required")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("server URL must start with http:// or https://")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("server URL must not contain a path, query or fragment")
    return f"{parsed.scheme}://{parsed.netloc}"


def credentials_path() -> Path:
    """Where the login token is stored; tests can override it."""
    override = os.environ.get(CREDENTIALS_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".birds_trainer.json"


def save_credentials(credentials: Credentials, path: Path | None = None) -> Path:
    """Write the credentials atomically with mode 0600."""
    target = path if path is not None else credentials_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        {
            "server": credentials.server,
            "username": credentials.username,
            "scope": credentials.scope,
            "token": credentials.token,
            "expires_at": credentials.expires_at,
        },
        indent=2,
    ) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=".birds_trainer.", dir=target.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target


def load_credentials(
    path: Path | None = None, *, require_valid: bool = True
) -> Credentials:
    """Read the stored login; raise ``CredentialsError`` when unusable."""
    target = path if path is not None else credentials_path()
    if not target.exists():
        raise CredentialsError(
            "not logged in; run: python3 -m trainer login --server <url>"
        )
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
        credentials = Credentials(
            server=normalize_server(document["server"]),
            username=str(document["username"]),
            scope=str(document["scope"]),
            token=str(document["token"]),
            expires_at=str(document["expires_at"]),
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise CredentialsError(f"stored login is invalid: {exc}") from exc
    if not credentials.token:
        raise CredentialsError("stored login has no token")
    if require_valid and credentials_expired(credentials):
        raise CredentialsError(
            "login expired; run: python3 -m trainer login --server <url>"
        )
    return credentials


def delete_credentials(path: Path | None = None) -> bool:
    """Remove the stored login; return True when a file was removed."""
    target = path if path is not None else credentials_path()
    try:
        target.unlink()
    except FileNotFoundError:
        return False
    return True


def credentials_expired(credentials: Credentials) -> bool:
    """Return True for an expired or unreadable stored expiry."""
    try:
        expires = datetime.fromisoformat(
            credentials.expires_at.replace("Z", "+00:00")
        )
    except ValueError:
        return True
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires <= datetime.now(timezone.utc)


def login(
    server: str,
    username: str,
    password: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> Credentials:
    """Exchange a username and password for a signed token."""
    base = normalize_server(server)
    name = str(username or "").strip()
    if not name:
        raise ValueError("username is required")
    if not password:
        raise ValueError("password is required")

    body = json.dumps({"username": name, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/login",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    status, payload, _ = _open(request, timeout)
    try:
        document = json.loads(payload.decode("utf-8"))
        return Credentials(
            server=base,
            username=str(document["username"]),
            scope=str(document["scope"]),
            token=str(document["token"]),
            expires_at=str(document["expires_at"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CloudError(
            status, "invalid_response", "login response is incomplete"
        ) from exc


class CloudFiles:
    """Read and write logical files under the token's scope."""

    def __init__(
        self,
        server: str,
        token: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.server = normalize_server(server)
        if not token:
            raise ValueError("token is required")
        self.token = token
        self.timeout = timeout

    def read(self, path: str) -> tuple[bytes, str]:
        """Return the file bytes and its revision."""
        status, payload, headers = self._request(
            "GET", self._file_url(path)
        )
        return payload, _revision(headers)

    def read_json(self, path: str) -> tuple[Any, str]:
        """Return decoded JSON and the revision."""
        payload, revision = self.read(path)
        try:
            return json.loads(payload.decode("utf-8")), revision
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CloudError(
                0, "invalid_json", f"{path} is not valid JSON"
            ) from exc

    def write(
        self,
        path: str,
        data: bytes,
        *,
        revision: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Write bytes; with a revision, fail if the file changed."""
        headers = {"Content-Type": content_type}
        if revision:
            headers["If-Match"] = revision
        status, payload, _ = self._request(
            "PUT", self._file_url(path), data=data, headers=headers
        )
        try:
            return str(json.loads(payload.decode("utf-8"))["revision"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CloudError(
                status, "invalid_response", "write response has no revision"
            ) from exc

    def write_json(
        self,
        path: str,
        value: Any,
        *,
        revision: str | None = None,
    ) -> str:
        """Write indented JSON with a trailing newline."""
        text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        return self.write(
            path,
            text.encode("utf-8"),
            revision=revision,
            content_type="application/json; charset=utf-8",
        )

    def list(self, prefix: str = "") -> list[dict[str, Any]]:
        """Return every object at or below a prefix, following cursors."""
        objects: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params: dict[str, str] = {"prefix": prefix}
            if cursor:
                params["cursor"] = cursor
            url = f"{self.server}/fs?{urllib.parse.urlencode(params)}"
            status, payload, _ = self._request("GET", url)
            try:
                document = json.loads(payload.decode("utf-8"))
                page = document["objects"]
                if not isinstance(page, list):
                    raise TypeError("objects is not a list")
                objects.extend(page)
            except (KeyError, TypeError, ValueError) as exc:
                raise CloudError(
                    status, "invalid_response", "list response is incomplete"
                ) from exc
            if not document.get("truncated"):
                return objects
            cursor = document.get("cursor")
            if not cursor:
                return objects

    def delete(self, path: str) -> None:
        """Delete a file; deleting a missing file still succeeds."""
        self._request("DELETE", self._file_url(path))

    def _file_url(self, path: str) -> str:
        logical = str(path or "").strip()
        if not logical:
            raise ValueError("path is required")
        return f"{self.server}/fs/{urllib.parse.quote(logical, safe='/')}"

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes, Any]:
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
                **(headers or {}),
            },
        )
        return _open(request, self.timeout)


class CloudApp:
    """Call the Worker's trainer session API under the token's scope."""

    def __init__(
        self,
        server: str,
        token: str,
        *,
        username: str = "",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.server = normalize_server(server)
        if not token:
            raise ValueError("token is required")
        self.username = str(username)
        self.token = token
        self.timeout = timeout

    def profile(self) -> dict[str, Any]:
        """Return the profile summary, creating the profile if needed."""
        return self._json("GET", "/app/profile")

    def search_birds(self, query: str = "") -> dict[str, Any]:
        """Search the Worker's bundled catalog."""
        return self._json("POST", "/app/birds", {"q": str(query)})

    def card_view(
        self,
        species_id: str,
        card_type: str,
        seed: int = 0,
    ) -> dict[str, Any]:
        """Build one stateless card view."""
        return self._json(
            "POST",
            "/app/cards",
            {
                "species_id": species_id,
                "card_type": card_type,
                "seed": seed,
            },
        )

    def grade_card(
        self,
        species_id: str,
        card_type: str,
        seed: int = 0,
        attempt: int = 1,
        *,
        choices: dict[str, str] | None = None,
        choice: str | None = None,
        response: str | None = None,
    ) -> dict[str, Any]:
        """Grade one stateless card attempt; return ``{feedback}``."""
        body: dict[str, Any] = {
            "species_id": species_id,
            "card_type": card_type,
            "seed": seed,
            "attempt": attempt,
        }
        if choices is not None:
            body["choices"] = choices
        if choice is not None:
            body["choice"] = choice
        if response is not None:
            body["response"] = response
        return self._json("POST", "/app/cards/answer", body)

    def list_sessions(self) -> dict[str, Any]:
        """Return ``{sessions}``."""
        return self._json("GET", "/app/sessions")

    def resolve_session(
        self, handle: str, *, by_name: bool = False
    ) -> dict[str, Any]:
        """Resolve a session name, id or id prefix in the Worker."""
        return self._json(
            "POST",
            "/app/sessions/resolve",
            {"handle": handle, "by_name": by_name},
        )

    def card_run(
        self, query: str, card_type: str
    ) -> dict[str, Any]:
        """Return Worker-filtered eligible birds for a card run."""
        return self._json(
            "POST",
            "/app/cards/run",
            {"q": str(query), "card_type": str(card_type)},
        )

    def create_session(
        self,
        *,
        name: str | None = None,
        filter: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Create a session and return its first view."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if filter is not None:
            body["filter"] = filter
        if settings is not None:
            body["settings"] = settings
        if seed is not None:
            body["seed"] = seed
        return self._json("POST", "/app/sessions", body)

    def session(self, session_id: str) -> dict[str, Any]:
        """Return one session view."""
        return self._json("GET", self._session_path(session_id))

    def prepare_session(self, session_id: str) -> dict[str, Any]:
        """Refresh and return the session view."""
        return self._json(
            "POST", f"{self._session_path(session_id)}/prepare"
        )

    def rename_session(
        self, session_id: str, name: str | None
    ) -> dict[str, Any]:
        """Set a session name; ``None`` removes it."""
        return self._json(
            "POST",
            f"{self._session_path(session_id)}/rename",
            {"name": name},
        )

    def delete_session(self, session_id: str) -> None:
        """Delete a session; deleting a missing one still succeeds."""
        self._json("DELETE", self._session_path(session_id), allow_empty=True)

    def answer(
        self,
        session_id: str,
        card_uid: str,
        action: str,
        *,
        choices: dict[str, str] | None = None,
        choice: str | None = None,
        response: str | None = None,
    ) -> dict[str, Any]:
        """Submit one answer; return ``{feedback, session}``."""
        body: dict[str, Any] = {"card_uid": card_uid, "action": action}
        if choices is not None:
            body["choices"] = choices
        if choice is not None:
            body["choice"] = choice
        if response is not None:
            body["response"] = response
        return self._json(
            "POST", f"{self._session_path(session_id)}/answer", body
        )

    def _session_path(self, session_id: str) -> str:
        logical = str(session_id or "").strip()
        if not logical:
            raise ValueError("session id is required")
        return f"/app/sessions/{urllib.parse.quote(logical, safe='')}"

    def _json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.server}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": USER_AGENT,
                **headers,
            },
        )
        status, payload, _ = _open(request, self.timeout)
        if not payload:
            if allow_empty:
                return {}
            raise CloudError(
                status, "invalid_response", "response body is empty"
            )
        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CloudError(
                status, "invalid_response", "response is not valid JSON"
            ) from exc
        if not isinstance(document, dict):
            raise CloudError(
                status, "invalid_response", "response is not an object"
            )
        return document


def _open(
    request: urllib.request.Request, timeout: float
) -> tuple[int, bytes, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        code, message = _error_body(payload)
        if not payload:
            message = f"HTTP {exc.code} {exc.reason}".strip()
        raise CloudError(exc.code, code, message) from exc
    except urllib.error.URLError as exc:
        raise CloudError(0, "network_error", str(exc.reason)) from exc
    except (TimeoutError, OSError) as exc:
        raise CloudError(0, "network_error", str(exc)) from exc


def _error_body(payload: bytes) -> tuple[str, str]:
    try:
        document = json.loads(payload.decode("utf-8"))
        code = str(document.get("error", "http_error"))
        message = str(document.get("message", ""))
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        code = "http_error"
        message = payload.decode("utf-8", "replace")[:200]
    return code, message or f"HTTP {code}"


def _revision(headers: Any) -> str:
    value = headers.get("X-Revision")
    if value is None:
        value = headers.get("ETag", "")
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
    return str(value or "")


__all__ = [
    "CREDENTIALS_ENV",
    "CloudApp",
    "CloudError",
    "CloudFiles",
    "Credentials",
    "CredentialsError",
    "SERVER_ENV",
    "credentials_expired",
    "credentials_path",
    "delete_credentials",
    "load_credentials",
    "login",
    "normalize_server",
    "save_credentials",
]
