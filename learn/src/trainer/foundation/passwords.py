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
SCHEMA_VERSION = 2

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
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(derived).decode("ascii"),
    }


def verify_password(
    password: str,
    entry: Mapping[str, Any],
    iterations: int = DEFAULT_ITERATIONS,
) -> bool:
    """Check a password against an entry; malformed entries are a failure."""
    try:
        iterations = int(entry.get("iterations", iterations))
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
    iterations: int = DEFAULT_ITERATIONS,
) -> dict[str, Any]:
    """Return a v2 users document with one account added or replaced.

    The file is generated: usernames and passwords go in, salt and hash come
    out. ``iterations`` is a document-level default; a per-entry override is
    kept only when an imported entry uses a different value.
    """
    name = normalize_username(username)
    if not is_valid_username(name):
        raise ValueError(f"invalid username: {username!r}")

    existing = document.get("users", {})
    if not isinstance(existing, Mapping):
        raise ValueError("users must be an object")

    stored_iterations = document.get("iterations", iterations)
    if not isinstance(stored_iterations, int) or not (
        1 <= stored_iterations <= MAX_ITERATIONS
    ):
        raise ValueError("iterations out of range")
    if existing and iterations != stored_iterations:
        raise ValueError(
            f"existing accounts use {stored_iterations} iterations; "
            f"omit --iterations or match the value"
        )

    users: dict[str, Any] = {}
    for other_name, other in existing.items():
        if not isinstance(other, Mapping):
            raise ValueError("users entries must be objects")
        entry = {
            "salt": other["salt"],
            "hash": other["hash"],
        }
        if "iterations" in other:
            entry["iterations"] = other["iterations"]
        users[other_name] = entry

    users[name] = hash_password(password, iterations=stored_iterations)
    return {
        "version": SCHEMA_VERSION,
        "iterations": stored_iterations,
        "users": users,
    }


__all__ = [
    "DEFAULT_ITERATIONS",
    "MAX_ITERATIONS",
    "SCHEMA_VERSION",
    "add_user",
    "hash_password",
    "is_valid_username",
    "normalize_username",
    "verify_password",
]
