# Trainer progress on Cloudflare

Status: the Worker file API, login, provisioning script and their tests are
implemented in `learn/cloudflare/` and `learn/tools/provision_user.py`. The
Worker is deployed at `https://birds-progress.regevran.workers.dev` and the
live login smoke test succeeded. The Python `CloudFiles` client, credential
storage and CLI `login`/`logout`/`whoami` are implemented. Scheduler wiring
and the browser client are next.

This file is the current storage design. The local-file and local-server
sections of `learn-implementation.md` describe the earlier plan and are
superseded where they conflict.

## Shape

```text
GitHub Pages (public)                 Cloudflare
  static client, data/out JSON          Worker ── R2 binding ──> private bucket
        │                                  │                     birds-progress/
        └──── HTTPS + bearer token ────────┘
```

The Worker is a file store, not a trainer API. It authenticates, scopes paths
and reads/writes R2. The trainer logic (cards, queue, scheduler) lives in the
clients; the files are the contract between them.

## Bucket layout

```text
birds-progress/
  users.json                          provisioned accounts, never served
  users/<username>/profile.json       profile, passed table, global counter
  users/<username>/sessions/<id>.json session state
  tests/...                           test-scoped accounts and fixtures
```

Logical paths used by clients are relative: `profile.json`,
`sessions/<id>.json`. A normal token maps them to
`users/<username>/<path>`; a `tests`-scoped token maps them to `tests/<path>`.
The client never supplies a username in a path.

The bucket is private. It has no public `r2.dev` URL. Only the Worker reads and
writes it.

## Accounts

`users.json`:

```json
{
  "users": {
    "ran": {
      "algorithm": "pbkdf2-sha256",
      "iterations": 1000,
      "salt": "base64…",
      "hash": "base64…",
      "scope": "profile"
    }
  }
}
```

- Accounts are added manually with
  `python3 learn/tools/provision_user.py <username>`. The script prompts for
  the password, hashes it, writes the file with mode 0600, and prints the
  upload command.
- `--scope tests` creates a test account. The test token can only touch
  `tests/`.
- There is no signup, password-change or OAuth endpoint. Standard login is
  deferred until there is a reason.
- Passwords are set by the owner; they are not generated. They should be
  unique to this tool.
- PBKDF2-HMAC-SHA256 is fixed at 1,000 iterations for now. The count is stored
  per user, so it can be raised later. This is a deliberate speed bump, not a
  password vault: the private bucket and unique passwords are the main
  controls. The free Workers plan allows 10 ms CPU per request; 1,000
  iterations fit comfortably.

## Tokens

- `POST /login` returns an HMAC-SHA256 signed token valid for 30 days
  (`TOKEN_TTL_SECONDS`).
- Payload: `{u: username, s: profile|tests, exp: unix-seconds}`.
- `AUTH_SECRET` is a Worker secret; rotating it invalidates every token.
- Login failures are generic: unknown user and wrong password both return
  `invalid_credentials`.
- Missing or malformed tokens return `unauthorized`; expired tokens return
  `token_expired`.

## File API

```text
GET    /health
POST   /login
GET    /fs?prefix=...&limit=...&cursor=...
GET    /fs/<path>
PUT    /fs/<path>          If-Match: <revision> optional
DELETE /fs/<path>
```

- Reads return `X-Revision` (R2 ETag without quotes) and `ETag`.
- Writes return `{path, revision, size}`. Without `If-Match` a write creates or
  replaces; with a stale `If-Match` it returns `412 revision_conflict`.
- Listing is a flat recursive prefix list; `prefix=sessions/` lists the
  subtree, `prefix=` lists the whole scope.
- Bodies are capped at 1 MB.
- Paths are relative and restricted to letters, digits, `.`, `_`, `-` and
  `/`. Empty segments, `.`, `..`, backslashes and control characters are
  rejected.
- Error body: `{error, message}`.

## CORS

`ALLOWED_ORIGINS` is a comma-separated list; the default is
`https://regevran.github.io`. Any localhost or 127.0.0.1 port is allowed for
development. Preflights are cached for a day.

## Revision model

The R2 ETag is the revision. The Worker sends it as `X-Revision` and accepts
it back in `If-Match`. It uses R2's conditional `put` so two writers cannot
silently overwrite each other. The app should keep one open session per
profile and reload on a `412`.

## Python client

`learn/src/trainer/foundation/cloud.py` is the Python side of the file API:

- `login(server, username, password)` -> `Credentials`.
- `CloudFiles(server, token)` with `read`, `read_json`, `write`,
  `write_json`, `list` (follows cursors) and `delete`.
- `CloudError` carries the HTTP status and the Worker's error code.
- Credentials are stored in `~/.birds_trainer.json` with mode 0600:
  `{server, username, scope, token, expires_at}`. Override the path with
  `BIRDS_TRAINER_CREDENTIALS`; the server can come from
  `BIRDS_TRAINER_SERVER`.

CLI commands:

```sh
python3 -m trainer login --server https://birds-progress.regevran.workers.dev
python3 -m trainer whoami
python3 -m trainer logout
```

The token is never printed. An expired stored login tells the user to run
`login` again. The credential file and the login command tests use a temporary
path, not the real home directory.

Live tests use the deployed Worker and a `tests`-scoped account:

```sh
BIRDS_TEST_SERVER=https://birds-progress.regevran.workers.dev \
BIRDS_TEST_USER=tester \
BIRDS_TEST_PASSWORD=... \
cmake --build build --target learn-test-live
```

They write only under `tests/probe/<random>/` and delete the file. Without the
three environment variables the live module is skipped in the normal suite.

## Testing

- `cmake --build build --target learn-worker-test` runs Node's built-in test
  runner (`node --test`) in `learn/cloudflare`.
- The tests use an in-memory binding that implements only the R2 methods the
  Worker calls. This is a binding stub for the Worker, not a parallel progress
  store; deployed-worker tests with real R2 come with the client.
- The PBKDF2 vector is shared with the Python tests, so the provisioner and
  the Worker cannot drift.
- `ctest --test-dir build -R learn-worker` runs the same suite.

## Deployment

1. Create the private bucket `birds-progress`.
2. Provision at least one account and upload `users.json` with
   `npx wrangler r2 object put ... --remote`. Without `--remote` wrangler
   writes to its local emulation, not the deployed bucket.
3. `npx wrangler secret put AUTH_SECRET` from `learn/cloudflare/` (it needs the
   wrangler config).
4. `cmake --build build --target learn-worker-deploy`.

The Worker is deployed at `https://birds-progress.regevran.workers.dev`. The
portfolio links to the static trainer as an external link; no custom domain is
needed.

## Deferred

- Python `RemoteFiles` client and CLI `login`/`logout`.
- Scheduler/profile/session code on top of the file API.
- Browser client and GitHub Pages deployment.
- Optional login throttling if the public endpoint is scanned.
- Any event log (R2 cannot append in place; D1 would be a separate design).
