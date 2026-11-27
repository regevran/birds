# Progress Worker

Status: implemented locally; 105 Node tests. The deployed Worker is old: it
predates the v2 `users.json` and the tests-scope removal. Do not upload the new
`users.json` until a v2 Worker is deployed. The Worker provides `/fs` (scoped
files) and `/app` (trainer); the CLI uses it fully. Endpoints:
`learn/WORKER-API.md`; trainer behaviour: `learn-reference.md`.

## Shape

```text
GitHub Pages (planned)              Cloudflare
  static client                     Worker ── R2 binding ──> private bucket
        │                               │                   birds-progress/
        └──── HTTPS + bearer token ─────┘
```

The Worker owns card views, grading, scheduling, handle resolution and card-run
eligibility. Clients render JSON and never duplicate logic.

## Bucket

```text
users.json
users/<username>/profile.json
users/<username>/sessions/<id>.json
media/illustrations/v1/<species>.webp
```

Client paths are relative; every token maps them under `users/<username>/`.
There is one scope, `profile`. The bucket is private. The only public read path
is `GET /media/illustrations/<version>/<species>.webp`, serving generated
images only. Images are not committed; the source is pinned in
`learn/web/illustrations.json`, generated and uploaded by the
`learn-web-illustrations*` targets. Credit: `learn/web/ATTRIBUTION.md`.

## Documents

`profile.json`: schema and app version, id/name, timestamps, `settings`
(`active_cap` default 7, `lookahead_target`, `out_of_scope_reviews`,
`show_bridge`), `global_counter`. No mastery table.

`session.json`: identity, `skill`, `status`, `filter` (families, orders,
genera, statuses, search), `created_from`, settings, seed, initial pool,
`pending` (ordered per-bird groups), `queue` (frontier `queue[0]`) and
`history` (`{card, result, at}`). Schema v2 only; no migration.

## Accounts and tokens

- `python3 learn/tools/provision_user.py <username>`; no signup, password
  change or OAuth.
- `users.json` v2: `{version: 2, iterations: 1000, users: {name: {salt,
  hash}}}`; PBKDF2-HMAC-SHA256 is implied. Generated; the Worker reads R2.
  Upload with `learn-worker-users-upload` (local) or `-deploy` (remote). Never
  hand-edit either copy.
- Tokens are HMAC-SHA256 `{u, s, exp}`; rotating `AUTH_SECRET` invalidates all.
  Login details: `learn/WORKER-API.md#get-a-token`.

## Concurrency

The R2 ETag is the revision (`X-Revision`, `If-Match`). Two clients on one
session see each other's progress. Answer uid classification: frontier live,
history redo, unseen non-frontier `409 not_current`, unknown `409 stale_card`.
A stale write is `412`; the client reloads.

## Clients and tests

- Python: `foundation/cloud.py` (`login`, `CloudFiles`, `CloudApp`);
  credentials `~/.birds_trainer.json`; selected session
  `~/.birds_trainer_state.json`.
- Browser: `learn/web`, same `/app`; L, search, timeline, history/redo and
  thin E/R/C/F forms.
- Node tests: `learn-worker-test` (105) with an in-memory R2 binding. Python:
  117 tests; live Worker tests use local `wrangler dev` and skip without
  `BIRDS_TEST_*`.

## Deployment

1. Private bucket `birds-progress`.
2. Set `AUTH_SECRET` (`npx wrangler secret put AUTH_SECRET` in
   `learn/cloudflare/`).
3. Deploy the Worker (`learn-worker-deploy`).
4. Provision, then upload the v2 `users.json` (`learn-worker-users-deploy`).

The static client will be linked from the portfolio; no custom domain is
needed.

## Deferred

Login throttling; event log/analytics.
