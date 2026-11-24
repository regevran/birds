#!/usr/bin/env python3
"""Mint a local development token for the browser client.

The Worker verifies a token by recomputing an HMAC-SHA256 over the payload
with ``AUTH_SECRET``; it does not store tokens. This tool signs the same
payload locally and writes a small page that stores the token under
``localStorage["birds.token"]`` and opens the app, so no password is needed
for local work. The token is only accepted by a Worker running with the same
``.dev.vars``; it is a development credential and must not be deployed.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path

LEARN = Path(__file__).resolve().parents[1]
DEFAULT_SECRET_FILE = LEARN / "cloudflare" / ".dev.vars"
DEFAULT_USERS_FILE = LEARN / "cloudflare" / "users.json"
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "build" / "web" / "dev-login.html"
DEFAULT_SERVE_URL = "http://localhost:8001"
SCOPES = ("profile", "tests")
USERNAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Birds development token</title>
<body>
<p>Storing the development token and opening the app…</p>
<p><a href="./">Open the app</a> if nothing happens.</p>
<script>
localStorage.setItem("birds.token", "{token}");
location.replace("./");
</script>
</body>
</html>
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user",
        default="ran",
        help="account name carried by the token (default ran)",
    )
    parser.add_argument(
        "--scope",
        choices=SCOPES,
        help="token scope (default: the account's scope in users.json, "
        "else tests)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="token lifetime in days (default 30)",
    )
    parser.add_argument(
        "--secret-file",
        type=Path,
        default=DEFAULT_SECRET_FILE,
        help=f"file holding AUTH_SECRET (default {DEFAULT_SECRET_FILE})",
    )
    parser.add_argument(
        "--users-file",
        type=Path,
        default=DEFAULT_USERS_FILE,
        help=f"accounts file used to pick the scope (default {DEFAULT_USERS_FILE})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"dev-login page to write (default {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--serve-url",
        default=DEFAULT_SERVE_URL,
        help=f"client URL printed by the tool (default {DEFAULT_SERVE_URL})",
    )
    return parser.parse_args(argv)


def read_secret(path: Path) -> str:
    if not path.exists():
        raise SystemExit(
            f"cannot read {path}; create it from .dev.vars.example"
        )
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*AUTH_SECRET\s*=\s*(.*)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value:
            return value
    raise SystemExit(f"{path} has no non-empty AUTH_SECRET")


def read_scope(users_file: Path, user: str) -> str | None:
    if not users_file.exists():
        return None
    try:
        document = json.loads(users_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entry = (document.get("users") or {}).get(user)
    scope = entry.get("scope") if isinstance(entry, dict) else None
    return scope if scope in SCOPES else None


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def mint(secret: str, user: str, scope: str, days: int) -> str:
    if not USERNAME.match(user):
        raise SystemExit(f"invalid account name: {user!r}")
    payload = {
        "u": user,
        "s": scope,
        "exp": int(time.time()) + days * 86400,
    }
    body = b64url(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signature = b64url(
        hmac.new(
            secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
        ).digest()
    )
    return f"{body}.{signature}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    secret = read_secret(args.secret_file)

    scope = args.scope or read_scope(args.users_file, args.user)
    if scope is None:
        scope = "tests"
        print(
            f"note: {args.user!r} is not in {args.users_file}; "
            f"using scope {scope!r}"
        )

    token = mint(secret, args.user, scope, args.days)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(PAGE.format(token=token), encoding="utf-8")
    os.chmod(args.out, 0o600)

    expires = time.strftime(
        "%Y-%m-%d %H:%M", time.localtime(int(time.time()) + args.days * 86400)
    )
    print(
        f"Minted a dev token for {args.user!r} "
        f"(scope {scope!r}, expires {expires})."
    )
    print(f"Wrote {args.out} (development only; never deploy it).")
    print(f"Open: {args.serve_url.rstrip('/')}/dev-login.html")
    print("It stores the token in localStorage['birds.token'] and opens the app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
