# Trainer progress on Cloudflare

Status: the Worker file API, login, provisioning script and their tests are
implemented in `learn/cloudflare/` and `learn/tools/provision_user.py`. The
Worker is deployed at `https://birds-progress.regevran.workers.dev`; the live
login smoke test succeeded. The Worker has `/fs`, the `/app` session API and
the stateless card/search API. The Python text client uses all of them; it
keeps no bird data, card views, grading or search logic. The browser client is
next. The stateless endpoints are implemented and tested locally but still
need a deployment to reach the live Worker.

This file is the current storage and session design. The endpoint contract
with request/response examples is in `learn/WORKER-API.md`. The local-file and
local-server sections of `learn-implementation.md` describe the earlier plan
and are superseded where they conflict.

## Shape

```text
GitHub Pages (public)                 Cloudflare
  static client, data/out JSON          Worker ── R2 binding ──> private bucket
        │                                  │                     birds-progress/
        └──── HTTPS + bearer token ────────┘
```

The Worker owns the trainer session logic: `/app` creates sessions, returns
the current card, grades answers and saves profile/session documents. Clients
render the JSON views; they do not duplicate scheduling. `/fs` remains a
scoped raw file API for profile/session documents and test probes.

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

Login, token retrieval, bearer headers and expiry behavior are documented only
in [Get a token](../learn/WORKER-API.md#get-a-token). Internally the token is an
HMAC-SHA256 signed payload `{u: username, s: profile|tests, exp: unix-seconds}`;
`AUTH_SECRET` is a Worker secret and rotating it invalidates every token.

## API

The endpoint contract, request/response examples, status codes and CORS rules
live only in [`learn/WORKER-API.md`](../learn/WORKER-API.md). This file does not
duplicate them. Entry points:

- [Run the Worker locally](../learn/WORKER-API.md#run-the-worker-locally)
- [Get a token](../learn/WORKER-API.md#get-a-token)
- [File API](../learn/WORKER-API.md#file-api)
- [Profile](../learn/WORKER-API.md#profile)
- [Sessions](../learn/WORKER-API.md#sessions)
- [Stateless cards](../learn/WORKER-API.md#stateless-cards)
- [Errors](../learn/WORKER-API.md#errors)
- [CORS](../learn/WORKER-API.md#cors)

Design constraints that stay here:

- The Worker owns the card chain, grading and session scheduler; clients render
  the JSON views and never duplicate scheduling. It also resolves session
  handles and filters card-run eligibility.
- Sessions are independent documents with no active pointer. The protected
  `default` session always exists. Each client locally selects the session it
  works on; different clients may select different sessions, or the same one.
- `/app/cards` is stateless and never touches progress. Session routes persist
  through R2. Both use the same card and grading code.
- Card views never contain an explicit correct-answer field. L is the learning
  card and intentionally shows the full name.
- Session names are optional and unique; `default` is reserved.

## Revision model

The R2 ETag is the revision. The Worker sends it as `X-Revision` and accepts it
back in `If-Match`; the API reference defines the exact requests and
responses. It uses R2's conditional `put` so two writers cannot silently
overwrite each other. Sessions carry no active pointer, so two clients may
practise the same session: a consumed card is rejected with `409 stale_card`
and the client reloads the session, while a stale write reloads on `412`.

## Python client

`learn/src/trainer/foundation/cloud.py` is the Python side of the file API:

- `login(server, username, password)` -> `Credentials`.
- `CloudFiles(server, token)` with `read`, `read_json`, `write`,
  `write_json`, `list` (follows cursors) and `delete`.
- `CloudApp(server, token)` calls `/app`: `search_birds`, `card_view`,
  `card_run`, `grade_card`, `profile`, `list_sessions`, `resolve_session`,
  `create_session`, `session`, `prepare_session`, `rename_session`,
  `delete_session` and `answer`.
- `CloudError` carries the HTTP status and the Worker's error code.
- Credentials are stored in `~/.birds_trainer.json` with mode 0600:
  `{server, username, scope, token, expires_at}`. Override the path with
  `BIRDS_TRAINER_CREDENTIALS`; the server can come from
  `BIRDS_TRAINER_SERVER`.
- The selected session is client state in `~/.birds_trainer_state.json`
  (mode 0600), keyed by `server|username`; override the path with
  `BIRDS_TRAINER_STATE`. It is not stored in the Worker.

CLI commands:

```sh
python3 -m trainer login --server https://birds-progress.regevran.workers.dev
python3 -m trainer whoami
python3 -m trainer logout
python3 -m trainer search paddyfield
python3 -m trainer card L paddyfield
python3 -m trainer card F paddyfield
python3 -m trainer session new --search paddyfield --status accidental
python3 -m trainer session new passers --search passer
python3 -m trainer session list
python3 -m trainer session run
python3 -m trainer session run passers
python3 -m trainer session status
python3 -m trainer session open default
python3 -m trainer session rename passers evening
python3 -m trainer session rename evening --clear
python3 -m trainer session delete <id|name>
```

Search, card views, grading and sessions require a stored login and a reachable
Worker. `card` and `search` are online-only; there is no local dataset or card
generator. `--answer` and `--reveal` are not part of the CLI: the normal flow
reveals the answer, and `card L` is the reference view.

`session new [X | --name X]` creates a session and selects it for this client
without starting it; the name is optional and unique. `session new` accepts
`--search`, `--status`, `--family`, `--order`, `--genus`, `--active-cap` and
`--seed`. `session open|status|run|delete` accept a name, full id or
unambiguous id prefix, or `--name` for an exact name. Handles match
case-insensitively. `session open` and `run X` save the selection locally;
`status X` is read-only. `session rename OLD [NEW]` sets or clears a name; the
id, queue and progress stay unchanged. `session run` calls `/prepare` so passed
birds are dropped, renders the Worker's card views and submits answers; pausing
(`exit`, Esc or Ctrl-D) leaves the session saved, so `session run` resumes it.
Every session except `default` can be deleted; if it was selected, the client
falls back to `default`. `default` cannot be renamed. A completed session is
not deleted automatically.

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

They write only under `tests/`: file probes use `tests/probe/<random>/`, and
the session test creates and deletes one short session. Without the three
environment variables the live module is skipped in the normal suite.

## Testing

- `cmake --build build --target learn-worker-test` runs Node's built-in test
  runner (`node --test`) in `learn/cloudflare`: 90 tests covering core,
  login/file API, dataset, grading, views, scheduler, stateless cards/search
  and the `/app` session API.
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

- Browser client and GitHub Pages deployment.
- Optional login throttling if the public endpoint is scanned.
- Any event log (R2 cannot append in place; D1 would be a separate design).
