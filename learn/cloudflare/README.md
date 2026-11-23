# Progress Worker

A small Cloudflare Worker that gives the trainer an authenticated, private
store on R2 and owns the trainer session logic. `/fs` is the file API; `/app`
creates sessions, returns card views, grades answers and saves state, so the
Python CLI and browser client stay thin. The full request/response reference is
in [`../WORKER-API.md`](../WORKER-API.md).

## Layout

```text
learn/cloudflare/
  src/core.js        paths, tokens, PBKDF2, CORS (no R2, no routing)
  src/index.js       HTTP routing, /fs and /app dispatch
  src/app.js         /app sessions plus stateless cards/search
  src/trainer/       dataset, search, grading, views, RNG and scheduler
  src/generated/     generated dataset module (not committed)
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

The health check, login/token retrieval and protected request examples live only
in the [Worker API reference](../WORKER-API.md#get-a-token). This README does
not duplicate them.

## API

The endpoint contract, request/response examples, status codes and CORS rules
live only in [`../WORKER-API.md`](../WORKER-API.md).

- [Health](../WORKER-API.md#health)
- [Login and tokens](../WORKER-API.md#get-a-token)
- [File API](../WORKER-API.md#file-api)
- [Profile](../WORKER-API.md#profile)
- [Sessions](../WORKER-API.md#sessions)
- [Stateless cards](../WORKER-API.md#stateless-cards)
- [Errors](../WORKER-API.md#errors)
- [CORS](../WORKER-API.md#cors)

## Local development

Local secrets, local R2 seeding, login/token retrieval and example requests are
in [Run the Worker locally](../WORKER-API.md#run-the-worker-locally) and
[Get a token](../WORKER-API.md#get-a-token).

```sh
cmake --build build --target learn-worker-dev
# or: cd learn/cloudflare && npx wrangler dev
```

Wrangler emulates R2 under `.wrangler/state` (ignored). Commands such as
`r2 object put` default to that local emulation; add `--remote` when you mean
the deployed bucket.

## Accounts

- Accounts are created manually; there is no signup or password-change API.
- The password is hashed with PBKDF2-HMAC-SHA256 at 1,000 iterations. This is
  intentionally a speed bump, not a strong password vault: the bucket is
  private, and passwords should be unique to this tool.
- A normal token maps to `users/<username>/`; a `tests`-scoped token maps to
  `tests/`. The Worker never accepts a username from the request path.
- Login, token expiry and bearer headers are documented in
  [Get a token](../WORKER-API.md#get-a-token).

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
scope, revisions, CORS, the body cap, search, card views, grading and the
session API. The integration tests that exercise a deployed Worker with real
R2 come with the Python client.

## Operational notes

- The bucket must stay private. The Worker is the only reader and writer.
- Set a Cloudflare billing notification even though `workers.dev` and the R2
  free tier are enough for this workload.
- The free plan allows 10 ms of CPU per request. Login does one PBKDF2 at 1,000
  iterations, well below that; file routes only do small JSON and R2 I/O.
- No event log is written. If one is ever added, it needs a separate design
  because R2 objects cannot be appended in place.
