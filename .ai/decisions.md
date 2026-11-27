# Decisions

Current choices and the reasons that still matter. Mechanics and schemas live
in the canonical files; superseded drafts are in git history.

## Book

- Personal aid for bird ringing. Ringers write genus + species as initials;
  the documented ringing name is the genus. Learn Latin names; genus is the
  learning unit, family the grouping level.
- A5 96-page third edition (2026), perfect bound, K-only interior,
  full-colour cover, 5.28 mm spine, one-file PDF mandatory.
- RTL book: higher folios lie left. Latin-script indexes are assigned pages in
  reverse so a left-to-right scan reads A→Z; edge tabs alternate.
- Reads only the installed `data/out` contract; families follow
  `family_order`. Details: `book-reference.md`.

## Trainer

- Browser trainer over the same dataset; v1 skill is Hebrew → Latin; no timer;
  progress online only in the Worker.
- The Worker owns data, card views, grading, search and scheduling. Python and
  browser clients render JSON and store credentials.
- Card chain with parts L→E→R→C→F; without parts L→R→C→F. L is display-only;
  F is terminal.
- E checks elements; R chooses from taxonomically proximate names; C types
  with a scaffold; F types unaided. A wrong R/C/F gets one retry, then a
  reveal; a near miss reveals and moves on. Shared Hebrew prompts accept every
  species.
- Sessions are independent Worker documents; there is no active session. Each
  client selects one locally. `default` always exists, has no filters and is
  protected.
- A session stores `pending` per-bird card groups, `queue` (frontier
  `queue[0]`) and `history`. Pulling a bird moves its group into the queue;
  invalidation pours cards back.
- History is linear. The answer route classifies a submitted uid: frontier =
  live, history = redo, unseen non-frontier = `409`, unknown = `409`. A
  correct redo records only; a wrong redo truncates the future, pours cards
  back and re-applies the retry.
- No passing/mastery table and no review levels. A correct F completes a
  bird's chain. Progress is the share of the session's birds with no pending
  or queued cards; `global_counter` is the shared scheduling seed.
- A session stores the Worker-formatted `created_from` and `active_cap`; both
  are shown read-only.
- Card commands and card runs are ephemeral study tools; sessions save
  progress. Card runs use the full search; session filters match identity
  only.
- Cards are independent; sessions and card runs are series instances. The
  chain is the session's order; other orderings are future series, not card
  types.
- UI: book-like paper, Hebrew RTL with Latin/English LTR. The look-ahead is a
  fixed-centre timeline: three history, three future. Cards show `(type)
  Hebrew`, never Latin; completed cards dim; text and boxes size 20·15·11·9 px
  toward the centre. The centre slot is a fixed 210 px; step arrows are fixed
  and pinned to the connector line; cards paint above them. Clicking the
  centre collapses to a monocular icon. The main card follows the focus.
- The illustration is always visible, F included, so picture→Latin is
  accepted. A reader speaks visible names (Latin required; English/Hebrew
  later).
- Browser media: no image binaries in git. The set is generated from the
  pinned CC BY 4.0 source, resized to 512 px WebP and served by a public
  Worker route. The footer carries one linked credit line.
- Scope: the CLI covers L/E/R/C/F. The browser has L, search, the timeline,
  history/redo and thin E/R/C/F forms; E/R/C/F face design, the session drawer
  and create flows remain.
- Client and Worker share one version; deploy together.

## Storage and accounts

- Progress lives in private Cloudflare R2 behind the Worker; the static client
  will live on GitHub Pages. The Worker is the single source of truth.
- Accounts are owner-provisioned in a generated `users.json`; no signup or
  OAuth. Passwords are a speed bump over a private bucket.
- Tokens are HMAC-signed; every account has one `profile` scope mapping to
  `users/<username>/`.
- No test scope; local fixtures live in the developer's local R2.
- `users.json` is generated and reaches the Worker only through the upload
  targets; neither copy is hand-edited.
- Details: `learn-cloudflare.md`; endpoints: `learn/WORKER-API.md`.

## Deferred

- V cards, due reviews, hints and the passing/mastery lifecycle.
- Event log/analytics, OAuth/login throttling, global search, English
  directions.
