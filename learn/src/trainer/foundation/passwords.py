"""Password hashing and account entries for manually provisioned users.

The Cloudflare Worker verifies the same format with WebCrypto.  Only the
provisioning script and its tests use this module; the trainer itself never
handles passwords.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from collections.abc import Mapping
from typing import Any

DEFAULT_ITERATIONS = 1_000
MAX_ITERATIONS = 1_000_000
SCOPES = ("profile", "tests")

_USERNAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def normalize_username(value: str) -> str:
    """Lowercase and trim a username; the Worker uses the same rule."""
    return str(value).strip().lower()


def is_valid_username(name: str) -> bool:
    """Return True for a username the Worker accepts in a token."""
    return bool(_USERNAME.fullmatch(name))


def hash_password(
    password: str,
    *,
    iterations: int = DEFAULT_ITERATIONS,
    salt: bytes | None = None,
) -> dict[str, Any]:
    """Return a ``users.json`` entry for a plaintext password.

    PBKDF2-HMAC-SHA256 matches WebCrypto's PBKDF2 in the Worker.  The salt is
    random per call; pass one only in tests that check a fixed vector.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password must not be empty")
    if not isinstance(iterations, int) or not 1 <= iterations <= MAX_ITERATIONS:
        raise ValueError("iterations out of range")
    if salt is None:
        salt = os.urandom(16)
    if len(salt) < 8:
        raise ValueError("salt must be at least 8 bytes")

    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return {
        "algorithm": "pbkdf2-sha256",
        "iterations": iterations,
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(derived).decode("ascii"),
    }


def verify_password(password: str, entry: Mapping[str, Any]) -> bool:
    """Check a password against an entry; malformed entries are a failure."""
    try:
        iterations = int(entry["iterations"])
        if not 1 <= iterations <= MAX_ITERATIONS:
            return False
        salt = base64.b64decode(str(entry["salt"]), validate=True)
        expected = base64.b64decode(str(entry["hash"]), validate=True)
        if len(salt) < 8 or len(expected) != 32:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
    except (KeyError, TypeError, ValueError):
        return False
    return hmac.compare_digest(actual, expected)


def add_user(
    document: Mapping[str, Any],
    username: str,
    password: str,
    *,
    scope: str = "profile",
    iterations: int = DEFAULT_ITERATIONS,
) -> dict[str, Any]:
    """Return a copy of a users document with one account added or replaced."""
    name = normalize_username(username)
    if not is_valid_username(name):
        raise ValueError(f"invalid username: {username!r}")
    if scope not in SCOPES:
        raise ValueError(f"invalid scope: {scope!r}")

    entry = hash_password(password, iterations=iterations)
    entry["scope"] = scope
    users = document.get("users", {})
    if not isinstance(users, Mapping):
        raise ValueError("users must be an object")
    updated = dict(users)
    updated[name] = entry
    return {**document, "users": updated}


__all__ = [
    "DEFAULT_ITERATIONS",
    "MAX_ITERATIONS",
    "SCOPES",
    "add_user",
    "hash_password",
    "is_valid_username",
    "normalize_username",
    "verify_password",
]
