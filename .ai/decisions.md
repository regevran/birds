# Agreed decisions

Choices with the reasons behind them. Mechanics and schemas live in the
canonical files linked here; working rules are in `README.md`.

## Book

- **Purpose:** a personal aid for bird ringing. Ringers write genus + species
  as initials, and the documented ringing name is the genus. Learn Latin names;
  genus is the learning unit, family is the grouping level.
- **Name parts:** grey marks an indexed element, a raised dot the joint, black
  means no entry. A ringing-shorthand column was considered and dropped because
  it is derivable from the Latin name.
- **Edition:** A5 96-page third edition (2026), perfect bound, K-only interior,
  full-colour cover, 5.28 mm spine. The combined one-file PDF is mandatory.
- **Direction:** the physical book is RTL, so higher folios lie left.
  Latin-script indexes are assigned pages in reverse so a left-to-right scan
  reads A→Z; edge tabs alternate to the outer edge (`pno + FRONT_PAGES` parity).
- **Input:** the book reads only the installed `data/out` contract and orders
  families by `family_order`.
- Details: `book-reference.md`.

## Trainer

- **Product:** a browser trainer for the same dataset; v1 skill is
  **Hebrew → Latin** (English directions later). There is no session timer; the
  learner stops and resumes the saved queue. Progress is online-only in the
  Worker; one profile per account and no second local progress store.
- **Ownership:** the Worker owns the dataset, card views, grading, search and
  scheduler. Python and browser clients only render JSON, collect answers and
  store credentials; they never duplicate scheduling or grading.
- **Card chain:** with parts `L → E → R → C → F`; without parts
  `L → R → C → F`. L is display-only; E is a separate element check (the
  earlier idea of putting parts on L was dropped). F is terminal. Review
  levels (`V`) are deferred/removed; see Progress.
- **Card choices:** E offers one Hebrew gloss per element within the element's
  theme (the theme is a hint); R chooses a Latin name from taxonomically
  proximate options and accepts every species sharing the Hebrew prompt; C
  types the Latin with a one-line scaffold; F types it unaided. A wrong R/C/F
  gets one retry, then reveals or falls back; a near miss reveals and
  soft-returns. Details: `learn-reference.md`.
- **Sessions:** independent Worker documents with **no active session**. Each
  client selects a session locally, per server and account; different clients
  may select different sessions, or share one. `default` always exists, has no
  filters and cannot be deleted or renamed; it is the fallback. Names are
  optional and unique; handle resolution and card-run eligibility are
  Worker-side. Two clients on one session see each other's progress; conflicts
  reload the session. A session stores a Worker-formatted `created_from` (the
  search and criteria at creation) and its `active_cap`; the summary returns
  both, and the clients show the origin read-only. The string is the base for
  future custom series.
- **Card-level pending pool:** a session keeps `pending` as ordered per-bird
  groups of card specs, `queue` as the materialised unseen cards (frontier at
  `queue[0]`) and `history` as completed cards. Pulling a bird moves its group
  into the queue; invalidation pours cards back. This keeps a partially learned
  bird's remaining cards and makes future series (e.g. every bird's C card) a
  selection over the same inventory.
- **History and redo:** the timeline is linear. The answer route classifies a
  submitted uid by data: frontier = live, history = redo, unseen non-frontier
  = `409 not_current`, unknown = `409 stale_card`. The client holds the
  browsing cursor; the Worker owns history and the frontier. A correct or
  advance redo records only and never mutates the plan; only a `wrong` redo
  invalidates the future — it truncates after the redone card, pours the
  invalidated cards back into pending, re-applies the retry, and makes
  everything after that card unseen. Redo grading is a final attempt (>= 2).
  The client is not asked to declare live vs redo, so CLI and browser share one
  implementation.
- **Progress:** there is no passing or mastery table (removed, along with
  V1–V4 review levels, to simplify history/redo). Correct F completes a bird's
  chain; a bird may be replayed in a new session. `global_counter` is a
  monotonic scheduling/seed counter shared by the profile's sessions.
  `session_card_count` is the history length; percent counts birds with no
  pending or queued cards.
- **Card commands** are ephemeral study tools; saved progress uses sessions.
  Search matches names, taxonomy and element meanings, while saved-session
  filters stay names-only. The CLI's help split, prompts and keys are in
  `learn/CLI-USAGE.md`.
- **Series:** cards are independent; the order they are presented in comes from
  an external series combining membership, ordering, persistence and
  progression. Sessions and card runs are the two instances today; other
  orderings (for example R→C or R→E) are a group-level design question, not
  ad-hoc variants. Card runs stay ephemeral in v1.
- **UI:** book-like paper styling, Hebrew RTL with Latin/English LTR runs. A
  collapsible look-ahead of seven cards shows Hebrew name + card type, never
  Latin.
- **Browser media:** the bird illustration is always visible, F included, so
  picture→Latin is a second accepted route to the name. A reader speaks
  visible names from pre-generated clips (Latin required; English and Hebrew
  later). Card titles and search actions use the full names, not the
  L/E/R/C/F shorthand.
- **Scope:** the text client covers L/E/R/C/F; hints are future. The browser
  L face is in development; E/R/C/F faces and navigation UI follow.
- **Client/Worker versioning:** one version. The client expects the current
  response shape; a release deploys both together.

## Progress storage and hosting

- Progress lives in **private Cloudflare R2** behind this repository's Worker;
  the static client will live on GitHub Pages. The Worker is the single source
  of truth, and the tool is online-only except for local credential handling.
- Accounts are owner-provisioned in a generated `users.json`; no signup or
  OAuth yet. Passwords are a deliberate speed bump over a private bucket, not a
  vault. Tokens are HMAC-signed and every account has the single `profile`
  scope, mapping to `users/<username>/`. Test fixtures live in the developer's
  local R2, not in a shared remote prefix; there is no `tests` scope or account.
- `users.json` is generated by the provisioning tool and is only a staging
  input; the Worker reads R2, so the file reaches it only through the
  `learn-worker-users-upload` / `learn-worker-users-deploy` targets. Never edit
  either copy by hand. `.dev.vars` (signing secret) and `users.json` (account
  verifiers) serve different purposes and neither replaces the other.
- Progress is one profile document plus one document per session, both in
  private R2; there is no event log.
- Storage and concurrency details: `learn-cloudflare.md`; endpoint contract:
  `learn/WORKER-API.md`.

## Deferred

- V cards, due reviews, hints and the passing/mastery lifecycle (removed in
  November 2026; see Progress) — until after the GUI and real practice.
- Event log and analytics; OAuth/login throttling; global search; English
  directions.
