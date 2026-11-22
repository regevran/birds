# Progress Worker

A small Cloudflare Worker that gives the trainer an authenticated, private
file store on R2. It is deliberately a file API, not a trainer API: the Python
CLI and the browser client decide what `profile.json` and session files mean.

## Layout

```text
learn/cloudflare/
  src/core.js        paths, tokens, PBKDF2, CORS (no R2, no routing)
  src/index.js       HTTP routing and R2 reads/writes
  tests/             Node's built-in test runner, in-memory R2 binding
  wrangler.toml      bucket binding, allowed origins, token lifetime
  .dev.vars.example  local secret template
```

The private bucket is:

```text
birds-progress/
  users.json                          provisioned accounts
  users/<username>/profile.json       learner state
  users/<username>/sessions/<id>.json session state
  tests/...                           test-scoped fixtures and runs
```

`users.json` is never served to a client. Each token is scoped either to one
user's prefix or to `tests/`; the client never names another user.

## First-time setup

1. Create the private R2 bucket named `birds-progress` in the Cloudflare
   dashboard. Do **not** enable a public `r2.dev` URL for it.

2. Add an account. The script prompts for the password twice, hashes it with
   PBKDF2-HMAC-SHA256 (1,000 iterations), writes `users.json`, and sets its mode
   to `0600`:

   ```sh
   python3 learn/tools/provision_user.py ran
   ```

   Add a test-scoped account for the test harness if needed:

   ```sh
   python3 learn/tools/provision_user.py tester --scope tests
   ```

3. Upload the users file to the real bucket. `--remote` is required:
   without it, wrangler writes to its local emulation under `.wrangler/state`.

   ```sh
   cd learn/cloudflare
   npx wrangler r2 object put birds-progress/users.json \
     --file users.json --content-type application/json --remote
   ```

4. Set the token-signing secret. Use a long random value:

   ```sh
   npx wrangler secret put AUTH_SECRET
   ```

5. Deploy:

   ```sh
   cmake --build build --target learn-worker-deploy
   # or: cd learn/cloudflare && npx wrangler deploy
   ```

The Worker gets a `*.workers.dev` hostname. Put it in the Python client and the
browser client later; the origin does not need a custom domain.

## Smoke test

After deployment, with `WORKER=https://birds-progress.<account>.workers.dev`:

```sh
curl -s "$WORKER/health"
TOKEN=$(curl -s "$WORKER/login" \
  -H 'content-type: application/json' \
  -d '{"username":"ran","password":"..."}' | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["token"])')
curl -s "$WORKER/fs?prefix=" -H "Authorization: Bearer $TOKEN"
```

## API

All responses are JSON except file reads. `POST`, `PUT` and `DELETE` require
`Authorization: Bearer <token>` unless noted.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | public liveness check |
| POST | `/login` | `{username, password}` -> `{token, username, scope, expires_at}` |
| GET | `/fs?prefix=...&limit=...&cursor=...` | list logical paths (flat prefix list) |
| GET | `/fs/<path>` | read bytes; returns `X-Revision` and `ETag` |
| PUT | `/fs/<path>` | write bytes; optional `If-Match: <revision>` |
| DELETE | `/fs/<path>` | delete |

- `PUT` without `If-Match` creates or replaces.
- `PUT` with a stale `If-Match` returns `412 revision_conflict`.
- `GET` and `PUT` return a revision (the R2 ETag without quotes) in
  `X-Revision` and in the response body for `PUT`.
- Listing is recursive: `prefix=` lists every file under the scope;
  `prefix=sessions/` lists only that subtree.
- Paths are relative, use `/`, and may contain letters, digits, `.`, `_`, `-`.
  Empty segments, `.`, `..`, backslashes and control characters are rejected.
- Request bodies are capped at 1 MB.

Errors are `{error, message}`. Codes: `invalid_request`, `invalid_credentials`,
`unauthorized`, `token_expired`, `forbidden_origin`, `invalid_path`,
`not_found`, `method_not_allowed`, `payload_too_large`, `revision_conflict`,
`users_missing`, `users_invalid`, `server_misconfigured`, `internal_error`.

## Authentication

- Accounts are created manually; there is no signup or password-change API.
- The password is hashed with PBKDF2-HMAC-SHA256 at 1,000 iterations. This is
  intentionally a speed bump, not a strong password vault: the bucket is
  private, and passwords should be unique to this tool.
- A successful login returns an HMAC-SHA256 signed token valid for 30 days
  (`TOKEN_TTL_SECONDS` in `wrangler.toml`). Rotating `AUTH_SECRET` invalidates
  every token.
- Login failures are identical for unknown users and wrong passwords.
- A normal token maps to `users/<username>/`; a `tests`-scoped token maps to
  `tests/`. The Worker never accepts a username from the request path.

## CORS

`ALLOWED_ORIGINS` is a comma-separated list. The default is
`https://regevran.github.io`; any `http://localhost:<port>` or
`http://127.0.0.1:<port>` origin is also allowed for local development.
Preflights are cached for a day.

## Local development

Create `.dev.vars` from `.dev.vars.example`, then:

```sh
cmake --build build --target learn-worker-dev
# or: cd learn/cloudflare && npx wrangler dev
```

Wrangler emulates R2 under `.wrangler/state` (ignored). Commands such as
`r2 object put` default to that local emulation; add `--remote` when you mean
the deployed bucket. The `users.json` in the emulated bucket still has to be
created separately for local runs; `wrangler dev` can also use the real bucket
with remote bindings.

## Tests

```sh
cmake --build build --target learn-worker-test
# or: cd learn/cloudflare && node --test
```

Node 22+ is required (for `node --test` and WebCrypto); `wrangler` is run via
`npx`, so it does not need a local install. The tests use Node's built-in
runner and an in-memory binding that implements
the R2 methods the Worker uses (`get`, `put` with `onlyIf`, `delete`, `list`).
They cover path traversal, token signing/expiry, user isolation, the test
scope, revisions, CORS and the body cap. The integration tests that exercise a
deployed Worker with real R2 come with the Python client.

## Operational notes

- The bucket must stay private. The Worker is the only reader and writer.
- Set a Cloudflare billing notification even though `workers.dev` and the R2
  free tier are enough for this workload.
- The free plan allows 10 ms of CPU per request. Login does one PBKDF2 at 1,000
  iterations, well below that; file routes only do small JSON and R2 I/O.
- No event log is written. If one is ever added, it needs a separate design
  because R2 objects cannot be appended in place.
