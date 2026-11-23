# Progress Worker

Status: implemented and deployed at
`https://birds-progress.regevran.workers.dev`; Node tests and live login pass.
The Worker has `/fs` (scoped files) and `/app` (trainer); the Python CLI uses
it fully. Endpoint contract and examples live only in `learn/WORKER-API.md`;
trainer behaviour is in `learn-reference.md`.

## Shape

```text
GitHub Pages (planned)                Cloudflare
  static client                       Worker ── R2 binding ──> private bucket
        │                                │                    birds-progress/
        └──── HTTPS + bearer token ──────┘
```

The Worker owns card chains, grading, scheduling, handle resolution and
card-run eligibility. Clients render JSON views and never duplicate logic.
`/app/cards` is stateless; session routes persist through R2.

## Bucket layout

```text
birds-progress/
  users.json                          provisioned accounts, never served
  users/<username>/profile.json       profile, passed table, global counter
  users/<username>/sessions/<id>.json session state
  tests/...                           test-scoped accounts and fixtures
```

Logical client paths are relative (`profile.json`, `sessions/<id>.json`). A
normal token maps them under `users/<username>/`; a `tests` token under
`tests/`. The client never names a user in a path. The bucket is private, has
no `r2.dev` URL and is read/written only by the Worker.

## Documents

`profile.json`:

- `schema_version`, `app_version`, `profile_id`, `name`, timestamps.
- `settings`: `active_cap` (default 7), `lookahead_target` (50),
  `out_of_scope_reviews`, `show_bridge`.
- `global_counter` — one per consumed card across all sessions.
- `passed` — keyed by species id, then skill (`latin` for v1). Each entry:
  `level` 1–4, `due_at` absolute counter (null when mastered), `mastered`,
  `last_result`, `last_at`, `last_session_id`.

`sessions/<id>.json`:

- Identity: `session_id`, `profile_id`, `name`, timestamps, `data_version`.
- `skill` (`he_to_latin`), `status` (`active` / `completed`).
- `filter`: `families`, `orders`, `genera`, `statuses`, `search`.
- `settings`, `seed`, `initial_pool_size`.
- `pool`: species ids not yet started. `queue`: concrete card descriptors
  (`uid`, `species_id`, `type`, `attempt`, `seed`, `hint_level`, `retry`,
  `revealed`); `queue[0]` is current.
- `session_card_count`, `paused_review` (future V only).

`queue` is the source of truth for order; active chains are derived by grouping
non-V cards by species. Pool and queue are disjoint. `passed` is contained in
the profile, not the session.

## Accounts and tokens

- Accounts are added manually with
  `python3 learn/tools/provision_user.py <username>` (`--scope tests` for the
  test account). No signup, password change or OAuth yet.
- `users.json` stores `algorithm`, `iterations`, `salt`, `hash` and `scope`.
  PBKDF2-HMAC-SHA256 at 1,000 iterations is a speed bump, not a vault; the
  private bucket and unique passwords are the main controls.
- Login and bearer details: `learn/WORKER-API.md#get-a-token`. Tokens are
  HMAC-SHA256 payloads `{u, s, exp}`; rotating `AUTH_SECRET` invalidates all.

## Design constraints

- Card views never contain an explicit correct answer; L intentionally shows
  the full name. Look-ahead exposes only Hebrew, type and review flags.
- Session summaries carry `session_card_count` and `percent_completed`.
- Session selection and naming rules are in `learn-reference.md`.

## Concurrency

The R2 ETag is the revision, sent as `X-Revision` and accepted in `If-Match`;
conditional puts prevent silent overwrites. Two clients on one session see
each other's progress: a consumed card returns `409 stale_card`; a stale write
returns `412`. The client reloads the session and continues.

## Clients

- Python: `learn/src/trainer/foundation/cloud.py` provides `login`,
  `CloudFiles` (read/write/list/delete) and `CloudApp` (`/app` calls);
  `CloudError` carries status and Worker error code. Credentials live in
  `~/.birds_trainer.json` (0600, `BIRDS_TRAINER_CREDENTIALS` overrides). The
  selected session lives in `~/.birds_trainer_state.json` (0600, keyed by
  `server|username`, `BIRDS_TRAINER_STATE` overrides).
- CLI commands and behaviour: `learn/CLI-USAGE.md`.
- Browser client: not written yet; it will use the same `/app` contract and
  keep its selected session in browser storage.

## Testing

- `cmake --build build --target learn-worker-test` runs Node's built-in test
  runner in `learn/cloudflare`, covering core, login/file API, dataset,
  grading, views, scheduler, stateless cards/search and `/app`. Counts are in
  `repository.md`.
- Tests use an in-memory binding implementing only the R2 methods the Worker
  calls. The PBKDF2 vector is shared with the Python tests.
- Live Python tests use a `tests`-scoped account and write only under `tests/`;
  they skip without `BIRDS_TEST_*`.

## Deployment

1. Private bucket `birds-progress`.
2. Provision an account and upload `users.json` with
   `npx wrangler r2 object put ... --remote` (without `--remote` wrangler uses
   local emulation).
3. `npx wrangler secret put AUTH_SECRET` from `learn/cloudflare/`.
4. `cmake --build build --target learn-worker-deploy`.

The static trainer will be linked from the portfolio; no custom domain is
needed.

## Deferred

- Login throttling if the public endpoint is scanned.
- Event log/analytics (R2 cannot append in place; D1 would be a new design).
