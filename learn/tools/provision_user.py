#!/usr/bin/env python3
"""Add or replace a user in the Worker's ``users.json``.

The file is written locally; upload it to the private R2 bucket afterwards.
Passwords are hashed with PBKDF2-HMAC-SHA256 (1,000 iterations by default),
matching the Worker's WebCrypto verification.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

LEARN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LEARN / "src"))

from trainer.foundation.passwords import (  # noqa: E402
    DEFAULT_ITERATIONS,
    add_user,
)

DEFAULT_FILE = LEARN / "cloudflare" / "users.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", help="lowercase account name")
    parser.add_argument(
        "--password",
        help="password (prompted twice when omitted)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"PBKDF2 iterations (default {DEFAULT_ITERATIONS})",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_FILE,
        help=f"users file (default {DEFAULT_FILE})",
    )
    return parser.parse_args(argv)


def read_password(value: str | None) -> str:
    if value is not None:
        if not value:
            raise SystemExit("password must not be empty")
        return value
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Password again: ")
    if first != second:
        raise SystemExit("passwords do not match")
    if not first:
        raise SystemExit("password must not be empty")
    return first


def load_document(path: Path) -> dict:
    if not path.exists():
        return {"users": {}}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read {path}: {exc}")
    if not isinstance(document, dict):
        raise SystemExit(f"{path} does not contain a JSON object")
    users = document.get("users")
    if users is not None and not isinstance(users, dict):
        raise SystemExit(f"{path} has a non-object 'users' field")
    return document


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    password = read_password(args.password)
    document = load_document(args.file)

    try:
        updated = add_user(
            document,
            args.username,
            password,
            iterations=args.iterations,
        )
    except ValueError as exc:
        raise SystemExit(str(exc))

    text = json.dumps(updated, indent=2, ensure_ascii=False) + "\n"
    args.file.parent.mkdir(parents=True, exist_ok=True)
    args.file.write_text(text, encoding="utf-8")
    os.chmod(args.file, 0o600)

    print(f"Added {args.username!r} to {args.file}")
    print("Upload the generated file with one of:")
    print("  cmake --build build --target learn-worker-users-upload")
    print("  cmake --build build --target learn-worker-users-deploy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
