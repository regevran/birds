# Birds of Israel — agreed decisions

Date: 2026-11-11

## Working agreement

- Discuss, summarize and agree **before** implementing.
- Work in small slices and let the user review each change; do not start the
  next slice before the previous one is accepted.
- **CMake is the only build interface.** Do not introduce or present a second,
  manual build path. Every build, install and test step goes through CMake, and
  the normal targets produce and install the complete output set.
- Keep durable project context in this `.ai/` directory. Update the relevant
  file when a decision or the structure changes; do not leave the context only
  in a chat session.
- Do not change `data/` or `book/` while working on the trainer unless the user
  asks.
- In chat, print Hebrew reversed because the user's terminal renders RTL
  backwards. Source files keep normal Hebrew. The text trainer reverses Hebrew
  by default and accepts `--no-reverse-hebrew`.
- In data models, every field gets an end-of-line comment with a real example
  from the project data, and each class docstring briefly says what the class
  holds, not who uses it. The dataset is closed, so real examples are cheap and
  remove ambiguity. Apply this to new and edited models everywhere.

## Product decisions

### Book

- The book is a personal memorisation aid for **bird ringing**. The user is
  learning the scientific (Latin) names of birds recorded in Israel; ringers
  write genus + species as the first free letters of each, and the name
  documented at ringing is the genus. Genus is therefore the primary learning
  unit, with family as the grouping level. The layouts are organised by genus
  and family, not as one flat alphabetical list.
- The book teaches the meaning of name parts. Grey marks a part with an entry
  in the word-element index; a raised dot marks the joint; a word with no entry
  stays black. A ringing-shorthand column was considered and deliberately
  dropped because it is derivable from the Latin name.
- The A5 perfect-bound pocket edition is a 96-page third edition (2026):
  K-only interior, full-colour cover, 5.28 mm spine. The combined one-file PDF
  is mandatory. Intermediates go to `build/book/`; installed PDFs go to
  `book/out/`.
- The physical book is RTL: higher folios lie to the left. Latin-script indexes
  must therefore reverse the flowed page assignment so a left-to-right scan
  reads A→Z. Index edge tabs alternate to the outer edge (left on versos,
  right on rectos), using the `pno + FRONT_PAGES` parity.
- The book reads only the installed `data/out` contract and orders families by
  `family_order`. It does not read the merged build intermediate.

### Trainer

- The trainer is a browser trainer for the same dataset: Latin, English and
  Hebrew names plus etymology elements. The primary v1 skill is
  **Hebrew → Latin**; English directions are later. Search, cards and grading
  need the Worker; only login/logout/whoami work without it.
- There is no session timer. The user practises as long as wanted, stops at any
  time, and resumes the saved card queue. Only the current profile/session
  state is stored; there is no event log. Progress is online-only in the
  Cloudflare Worker; each account has one profile, with no second local store.
- Card chain with parts: `L → E → R → C → F`; without parts:
  `L → R → C → F`. `V` appears when due. L is display-only; E is a separate
  element-check card. This superseded the earlier idea of putting the
  parts-matching exercise on L.
- The Worker owns the dataset, L/E/R/C/F views, grading and search. The Python
  text client (`python -m trainer`, CMake `learn-run`) is a thin Worker client:
  command parsing, prompts and text rendering only. Python retains 112 tests
  (three live Worker tests skip unless configured); the Worker has 90 tests.
  E, R, C and F are answerable: E collects one gloss choice per element and is
  graded by the Worker; R grades a Latin-name choice; C and F grade a typed
  Latin name. An E row shows its theme and draws every option from that same
  theme, so the theme is a deliberate hint. R draws distractors by taxonomic
  proximity (genus, family, order, any) and accepts every species that shares
  the prompt's Hebrew name. V, the hint ladder and the web UI remain
  design-only.
- R is a recognition test: Hebrew prompt, Latin options, no English or family.
  A wrong choice gets one retry without revealing the answer; a second wrong
  reveals the correct Latin. Showing the failure is also the intended
  full-training behavior.
- C is a typed production card: Hebrew prompt plus a one-line scaffold with
  the concatenated word shapes and a legend of part lengths and Hebrew
  glosses. The genus is one word even when built from several parts. Typed
  Latin is normalized with NFC, whitespace collapse and casefold. A near miss
  (distance at most 2, matching first letters) shows the exact spelling and
  moves on. A wrong answer gets one retry; the second wrong reveals the answer.
- F is C without the scaffold: Hebrew prompt, typed Latin, the same `grade_latin`
  grading and feedback. Hints are deferred; the request will be an input at the
  `Latin:` prompt (for example `Latin:?`) when the shared hint ladder is built.
- A card command may take a search query as well as one species. One match is
  the single card; several matches form an ephemeral run in search order, with
  Enter between cards and exit/quit/Ctrl-D/Esc stopping the run. This is a
  learner-driven "search with benefits" tool, not saved progress: one pass, no
  repetition, no logging. The Worker filters the run: R/C/F need Hebrew, E
  needs split elements, and it returns the skipped count and reason.
- `--answer` and `--reveal` were removed. Card views never contain an explicit
  answer; the normal flow reveals it (E immediately, R/C/F on the second wrong
  attempt or a near miss), and `card L` is the reference view.
- Question-card headers include the Latin family name, for example
  `[E 1/15] Gulosus aristotelis (Phalacrocoracidae)`. L already shows the
  family (and Hebrew family) as a field.
- Card views are JSON produced by the Worker; the Python client decodes them
  with `cards/wire.py`. The option seed is supplied by the caller and affects
  E/R option order only. A Latin segment is called `latin` (`latin_forms` for
  several), not `surface`.
- The Worker's card output is deterministic given a seed. E/R cards get a fresh
  random seed unless `--seed N` is given. E, R, C and F practise from a shell as
  well as inside the client: `python3 -m trainer card C acro` prints the card
  and prompts in the terminal. L only prints.
- The text client is a thin adapter over the Worker JSON; the web UI comes
  last. Its commands are `card L|E|R|C|F ...` with `L`/`E`/`R`/`C`/`F` aliases
  and `/<text>` for bird search. Readline history is persisted in
  `~/.birds_trainer_history`.
- Help is split like `gh`: `--help` prints only a terse usage and command list,
  and `<command> --help` / `help <command>` (including `card E` and
  `session new`) prints one command's usage. Prose explanations and examples
  live in `learn/CLI-USAGE.md`, not in `--help`, so the two do not duplicate.
  `session --help` documents the counters: `cards` (cards consumed in the
  session), `queue` (cards waiting in the session queue) and `pool` (eligible
  birds not yet added to the queue); the same meanings are in `CLI-USAGE.md`.
- Sessions follow a git-branch model with a **client-local checkout**. Sessions
  are independent Worker documents with no notion of an active one. Each client
  remembers which session it points at, per server and account, in
  `~/.birds_trainer_state.json` (`BIRDS_TRAINER_STATE` overrides the path);
  different clients may point at different sessions, and two clients may point
  at the same one. The protected `default` session always exists: it has no
  filters (all status categories), so it contains every eligible bird, and it
  cannot be deleted or renamed. It is also the fallback when a client has no
  selection or its selection disappeared. Other names are optional and unique
  (trimmed, case-insensitive). `session new [X | --name X]` creates a session,
  selects it for this client and prints one row with `*`; it does not print a
  card or start practising. `session open|status|run|delete [X | --name X]`
  resolve `X` as exact name, exact id or unambiguous id prefix; `--name` forces
  an exact name. `open X` selects locally; `run X` selects first; `status X` is
  read-only; `delete` removes any non-`default` session, and if it was selected
  the client falls back to `default`. `session rename OLD [NEW]` changes or
  clears a name (`--clear`, or no NEW) without changing the id, queue, progress
  or selection; the `default` session cannot be renamed. Handles (names, ids and
  id prefixes) match case-insensitively; the stored id stays lowercase. Session
  errors are short: semantic errors print `error: <message>` with ids and names,
  not HTTP details. There is no `session close` and no `--start`.
- The Worker owns session handle resolution and card-run eligibility. The CLI
  sends `{handle, by_name}` to `POST /app/sessions/resolve` and
  `{q, card_type}` to `POST /app/cards/run`; it does no name/id/prefix matching
  and no `has_hebrew`/`has_parts` filtering. Session views and summaries carry
  no `active` field, because selection is client state. Before practising, the
  client calls `POST /app/sessions/<id>/prepare`, which drops already-passed
  birds from the queue and pool. Two clients on the same session can race: the
  Worker rejects a consumed card with `409 stale_card` and a stale write with
  `412 revision_conflict`; the client then reports that the state changed in
  another client, reloads the session and continues.
- Search matches identity fields (species id, Latin, English, Hebrew, family,
  Hebrew family, order) and the etymology elements of each bird's name
  (`element_id`, `display`, `en`, `he`, `forms`). Results carry a `matched`
  explanation — `acrido (=locust)`, with the matched text in the searched
  language — and an `Elements matching ...` section lists the matching
  dictionary entries with glosses, theme, origin and bird count. Name matches
  sort before element-only matches. Whole-name meanings are excluded. Session
  filters stay names-only; card commands use the full search.
- Search is a nested, read-only `search>` mode. It is entered by `/text`, a
  bare `/`, or the `list`/`find`/`birds`/`search` aliases; every input in the
  mode is a query except `?` (help) and the up keys. From an E answer prompt,
  exiting search returns to the same element with earlier answers kept. Search
  never changes the card, the answers or grading.
- `exit`, `quit`, Ctrl-D and Esc (press Esc, then Enter) go one prompt up the
  chain: `search>` -> its caller, an E answer prompt -> `card>` (abandoning the
  card), and `card>` -> out of the CLI. Ctrl-C leaves the CLI. Esc is
  implemented by a readline binding that submits a sentinel and is removed
  from history; without readline, a line containing only ESC is treated as
  up.
- Card commands are ephemeral. Saved progress uses the Worker session commands
  in the next section; a card run does not write progress.

## Progress storage and hosting (2026-11-22)

- Progress lives in Cloudflare R2 behind a Cloudflare Worker that belongs to
  this repository. The static client is published on GitHub Pages
  (`https://regevran.github.io/birds/`); the portfolio links to it as an
  external link.
- Accounts are created manually: the owner adds an entry to a private
  `users.json` in the R2 bucket. The client shows a username+password screen.
  Password changes are not implemented yet. Standard OAuth providers are
  considered only if the user base grows.
- The Worker is the single source of truth for progress. The text client uses
  the same Worker; there is no second local progress store outside tests and
  development.
- The hosted tool is online-only by design. Search, card views, grading and
  sessions all require the Worker; only local credential handling works
  offline.
- The Worker is the only trainer implementation. Python keeps the CLI, text
  rendering, Worker transport and credential store; it has no dataset loader,
  card generator, grader or search matcher. This removes the duplicate
  implementations and makes card inspection online-only.
- Client and Worker are one version: the client requires the current response
  shape (for example `elements` and `matched` on `/app/birds`) and has no
  backward-compatibility path for older deployments. Work happens locally and
  a release deploys both together.
- R2 holds JSON documents: one profile document (settings, passed table,
  global counter) and one document per session. There is no event log for now;
  the earlier event-log idea is deferred and may be dropped.
- The progress bucket is private. Progress is never served through a public
  `r2.dev` base. The Worker authenticates a signed token and scopes every key
  to the logged-in user.
- The Worker exposes two APIs: `/fs` is the scoped raw file API, and `/app`
  is the trainer API. The full contract and examples are in
  `learn/WORKER-API.md`. The R2 ETag is the revision; writes accept `If-Match`
  and reject a stale revision. `/app` owns cards, grading, scheduling and
  session state so the text and browser clients stay thin.
- Sessions are independent Worker documents with no active pointer; `default`
  is always present and cannot be deleted or renamed. A wrong first attempt is
  a retry
  that does not consume the card; a second wrong attempt or a revealed answer
  consumes it and inserts the fallback chain. A near miss consumes the card
  and moves it and its remaining chain ahead. Passing F adds the bird to
  `passed` with a V1 due counter.
- Passwords are owner-set, salted and hashed with PBKDF2-HMAC-SHA256 at 1,000
  iterations. This is a speed bump, not a password vault; the private bucket
  and unique passwords are the main controls. The count is stored per user so
  it can be raised later. This fits easily in the free Worker's 10 ms CPU
  budget.
- A `tests`-scoped account maps its token to `tests/` in the bucket; a normal
  account maps to `users/<name>/`. The client never supplies a username in a
  path. Test fixtures therefore live in the same R2 store, not in a fake.
- Worker tests use Node's built-in runner and a binding stub that implements
  only the R2 methods the Worker calls. This is a binding stub, not a second
  progress store; deployed-worker tests with real R2 come with the client.

## Deferred items

- Trainer V card and the hint ladder.
- The event log and server-side analytics; possibly dropped.
- Standard OAuth login, if the user base grows.
- Global search.

