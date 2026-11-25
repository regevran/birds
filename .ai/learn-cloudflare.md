# Progress Worker

Status: implemented and deployed at
`https://birds-progress.regevran.workers.dev`. The deployed Worker predates the
v2 users.json format and the tests-scope removal, so it must not receive the
new `users.json` until it is redeployed. Node tests and local live login pass.
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
  users/<username>/profile.json       profile, settings, global counter
  users/<username>/sessions/<id>.json session state
```

Logical client paths are relative (`profile.json`, `sessions/<id>.json`) and
every token maps them under `users/<username>/`; there is one scope, `profile`.
The client never names a user in a path. The bucket is private, has no
`r2.dev` URL and is read/written only by the Worker.

## Documents

`profile.json`:

- `schema_version`, `app_version`, `profile_id`, `name`, timestamps.
- `settings`: `active_cap` (default 7), `lookahead_target` (50),
  `out_of_scope_reviews`, `show_bridge`.
- `global_counter` — one per consumed card (or wrong redo) across all
  sessions. There is no mastery/passed table and no review levels.

`sessions/<id>.json`:

- Identity: `session_id`, `profile_id`, `name`, timestamps, `data_version`.
- `skill` (`he_to_latin`), `status` (`active` / `completed`).
- `filter`: `families`, `orders`, `genera`, `statuses`, `search`.
- `created_from`: the Worker-formatted search and criteria at creation, e.g.
  `search "acrocephalus-agricola" · status: accidental`; empty for `default`
  (returned as `null`).
- `settings` (including `active_cap`), `seed`, `initial_pool_size` (birds).
- `pending`: ordered per-bird groups `{species_id, cards: [specs]}` for work
  not yet in the queue; a group moves whole into the queue when the bird is
  pulled. `queue`: materialised cards (`uid`, `species_id`, `type`, `attempt`,
  `seed`, `hint_level`, `retry`, `revealed`); `queue[0]` is the frontier.
- `history`: completed cards in timeline order, each
  `{card, result, at}`; `session_card_count` is its length.
- Schema version 2 only. There is no compatibility path for version-1
  documents; they are not supported.

`queue` is the source of truth for the future; pending is disjoint from it.
Card specs are materialised (new uid/seed) when pulled, so cards returned by
invalidation are unseen in the new timeline.

## Accounts and tokens

- Accounts are added with `python3 learn/tools/provision_user.py <username>`.
  No signup, password change or OAuth yet.
- `users.json` is generated (v2):
  `{version: 2, iterations: 1000, users: {name: {salt, hash}}}`. PBKDF2-HMAC-
  SHA256 is implied, `iterations` applies to the document (a per-entry value is
  accepted for imported accounts), and no user carries an `algorithm` or
  `scope` field. 1,000 iterations is a speed bump, not a vault; the private
  bucket and unique passwords are the main controls.
- The file is a staging input only: the Worker reads the R2 copy. The single
  writer is the provisioning script; the bridge to R2 is
  `learn-worker-users-upload` (local emulation) or `learn-worker-users-deploy`
  (remote, after deploying the Worker). Hand-editing either copy caused the
  earlier split brain, so it is not supported.
- Login and bearer details: `learn/WORKER-API.md#get-a-token`. Tokens are
  HMAC-SHA256 payloads `{u, s, exp}`; rotating `AUTH_SECRET` invalidates all.

## Design constraints

- Card views never contain an explicit correct answer; L intentionally shows
  the full name. Look-ahead exposes only Hebrew, type and review flags.
- Session summaries carry `session_card_count`, `percent_completed`,
  `pending_size`, `history_size`, `created_from` and `active_cap`.
- Session selection and naming rules are in `learn-reference.md`.

## Concurrency

The R2 ETag is the revision, sent as `X-Revision` and accepted in `If-Match`;
conditional puts prevent silent overwrites. Two clients on one session see
each other's progress. The answer route classifies the submitted uid: the
frontier is live, a history card is a redo, an unseen non-frontier card is
`409 not_current`, an unknown uid is `409 stale_card`; a stale write returns
`412`. The client reloads and continues.

## Clients

- Python: `learn/src/trainer/foundation/cloud.py` provides `login`,
  `CloudFiles` (read/write/list/delete) and `CloudApp` (`/app` calls);
  `CloudError` carries status and Worker error code. Credentials live in
  `~/.birds_trainer.json` (0600, `BIRDS_TRAINER_CREDENTIALS` overrides). The
  selected session lives in `~/.birds_trainer_state.json` (0600, keyed by
  `server|username`, `BIRDS_TRAINER_STATE` overrides).
- CLI commands and behaviour: `learn/CLI-USAGE.md`.
- Browser client (`learn/web`): static HTML/CSS/JS served on
  `http://localhost:8001` against the local Worker, using the same `/app`
  contract and keeping the selected session and token in browser storage. The
  L face, look-ahead, search and panel are implemented; navigation/redo UI is
  pending.

## Testing

- `cmake --build build --target learn-worker-test` runs Node's built-in test
  runner in `learn/cloudflare`, covering core, login/file API, dataset,
  grading, views, scheduler, stateless cards/search and `/app`. Counts are in
  `repository.md`.
- Tests use an in-memory binding implementing only the R2 methods the Worker
  calls. The PBKDF2 vector is shared with the Python tests.
- Live Python tests run against a local `wrangler dev` with a local account
  and write under a random `probe/` prefix in that account's own space; they
  skip without `BIRDS_TEST_*`.

## Deployment

1. Private bucket `birds-progress`.
2. Provision an account and upload `users.json` with
   `learn-worker-users-deploy` (the upload target without `deploy` writes to
   local emulation). Do this only after deploying a Worker that understands
   the current file format.
3. `npx wrangler secret put AUTH_SECRET` from `learn/cloudflare/`.
4. `cmake --build build --target learn-worker-deploy`.

The static trainer will be linked from the portfolio; no custom domain is
needed.

## Deferred

- Login throttling if the public endpoint is scanned.
- Event log/analytics (R2 cannot append in place; D1 would be a new design).
