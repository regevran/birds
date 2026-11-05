# Learning tool — implementation spec (draft)

Status: draft for review. No application code has been written. This file is the
implementation-level companion to `learn/REFERENCE.md`; where the two differ,
this file is the proposal and the difference is listed under **Open decisions**.

## 1. Technology

### Backend

- **Python 3.11+** (the machine has 3.14). Standard library only.
- `http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler` for HTTP.
- `json`, `pathlib`, `dataclasses`, `argparse`, `logging`, `threading`,
  `hashlib`, `random`, `secrets`, `unicodedata`, `unittest`.
- No Flask/FastAPI, no database, no ORM, no pip install, no virtualenv needed.

### Frontend

- **HTML + CSS + vanilla JavaScript**, ES modules, no framework, no bundler,
  no npm, no TypeScript.
- `fetch` for the JSON API; hash-based routing; no service worker.
- Fonts from the system, matching the book: `Noto Sans Mono` for Latin,
  `Droid Sans Hebrew` / `Noto Sans Hebrew` for Hebrew, with sans-serif
  fallbacks. No web-font download.
- Target: current Firefox/Chrome/Safari on the local machine. Linux first.

### Why this stack

- The repository is already Python; the trainer adds no runtime.
- The data is small (565 species, 308 elements), so JSON files and a local
  server are enough.
- File-based progress stays readable and git-diffable. SQLite would be binary
  and would fight the user's git workflow.
- Vanilla JS is sufficient for one screen with six card types; a framework
  would add a build step and dependencies for no benefit.

## 2. Repository tree

```text
birds/
  CMakeLists.txt                top-level build entry point
  CMakePresets.json             Ninja presets
  build/                        disposable build tree (ignored)
    data/
    book/
    learn/
  data/                         shared data project
    CMakeLists.txt              data targets
    README.md
    src/
      pipeline/                 default build steps
      oneoff/                   manual fetch/upgrade/maintenance
    in/                         sources and frozen snapshots
      etymology.md
      raw/
      jobling/
      hebrew_names.json
      hebrew_wikidata.json
      family_hebrew.json
      overrides/
    out/                        installed final data (committed)
      israel_birds_final.json
      etymology.json
  book/                         A5 pocket book
    src/                        book code and render.sh
    data/                       text.md, assets/, reports/
    out/                        installed PDFs (ignored)
    README.md
    REFERENCE.md
    PRINT.md
  learn/                        interactive trainer
    REFERENCE.md                agreed design
    IMPLEMENTATION.md           this file
    TODO.md                     follow-ups
    README.md                   run/test/backup notes
    src/
      birdtrainer/              Python package (stdlib only)
        __init__.py             version
        __main__.py             `python3 -m birdtrainer`
        config.py               paths, CLI defaults, app context
        rules.py                all tunable scheduling constants
        models.py               dataclasses + schema versions
        dataset.py              load/validate data, indexes, data hash
        normalize.py            Hebrew/Latin normalization
        grading.py              answer grading, near-miss, shared Hebrew
        cards.py                card descriptors and card views
        options.py              distractors and option seeding
        bridge.py               heuristic Hebrew <-> Latin element bridge
        queue.py                pure pool/queue operations
        scheduler.py            pure state transitions
        profiles.py             profile lifecycle
        sessions.py             session lifecycle
        store.py                atomic JSON/JSONL I/O, locking, migrations
        events.py               event construction and append
        api.py                  HTTP routing and JSON serialization
        static.py               safe static file serving
        errors.py               domain errors -> HTTP errors
      web/
        index.html
        app.js                  bootstrap and hash router
        api.js                  fetch wrappers and error handling
        state.js                client view state
        strings.js              Hebrew UI labels
        screens/main.js
        screens/new-session.js
        screens/session.js
        cards/learn.js
        cards/elements.js
        cards/recognize.js
        cards/construct.js
        cards/produce.js
        cards/review.js
        components/lookahead.js
        components/feedback.js
        styles/base.css
        styles/book.css
        styles/cards.css
      tests/
        __init__.py
        fixtures/               small synthetic data for edge cases
        test_dataset.py
        test_normalize.py
        test_grading.py
        test_cards.py
        test_queue.py
        test_scheduler.py
        test_store.py
        test_api.py
        test_integration.py
    data/
      README.md                 what the files are
      progress/                 user saved data, git-committable
        <profile-id>/
          profile.json
          events.jsonl
          sessions/
            <session-id>.json
```

Rules:

- `data/` and `book/` are never written by the trainer except for explicit
  user actions; the trainer reads `data/out/`.
- `learn/data/progress/` is user data, not code. The app writes only there.
- `learn/data/progress/**/*.tmp`, `learn/data/progress/**/.lock`,
  `build/`, `book/out/` and `__pycache__/` are ignored. The progress files
  themselves and `data/out/` are **not** ignored; the user commits them.
- There is no `learn/build` and no `learn/out`: all build artifacts go to the
  top-level disposable `build/`, and the trainer runs from `learn/src`.
- The package is named `birdtrainer` and lives under `learn/src/`; `learn/` is
  the trainer project, parallel to `book/`, not a separate `trainer/`
  directory.

## 3. Code shape

The code is split into a pure domain core and thin I/O edges.

```text
dataset ──> models
   │
   ├──> normalize ──> grading
   ├──> options ────> cards
   │
queue ──> scheduler ──> sessions ──> api ──> web
                 │
                 └──> profiles
store <──────────┘
```

- **Pure functions** for queue and scheduler: given a profile, session, card and
  answer, return the next profile/session and the response. No file I/O inside.
- **I/O edges**: `store` reads/writes files; `api` parses HTTP and serializes;
  `static` serves files; `events` appends JSONL.
- **One `AppContext`** holds the config, dataset, profile store, active session
  and locks. It is created at startup and injected into the API handlers.
- **Dataclasses** for `Bird`, `Element`, `CardDescriptor`, `ProfileState`,
  `SessionState`, `PassedEntry`, `Event`. Each has explicit serialization and
  schema validation. No Pydantic.
- **Injected clock and RNG** for tests: the scheduler takes a clock function and
  a `random.Random`; tests seed both.
- **Errors** are domain exceptions (`NotFound`, `Conflict`, `InvalidRequest`,
  `DataError`) mapped to JSON error bodies by `api`.
- **Logging** goes to stderr through `logging`; answers and responses are not
  logged, only IDs, card types and errors.

## 4. Data model

### 4.1 Catalog (in memory, built at startup)

From `data/out/israel_birds_final.json`:

- `species_id` — lowercase ASCII slug `genus-epithet`
  (`acrocephalus-agricola`). Stable for v1; human-readable in progress files.
- `genus`, `epithet`, `latin`, `english`, `hebrew`, `family`, `family_he`,
  `order`, `status`, `flags`, `family_order` (integer family rank for the
  book; ignored by the trainer).
- `status_category` — derived: `regular`, `introduced`, `accidental`,
  `historical`, `extinct` (a status may map to more than one, e.g. `Ex/A`).
- `has_hebrew` — false for the five species with no Hebrew; they are excluded
  from H→L.
- `ringer_key` — computed label `first 3 genus + first 3 epithet` (`PASMOA`).
  Display/export only; collision rule is still `learn/TODO.md`.

From `data/out/etymology.json`:

- `elements`: element ID -> `{en, he, theme, origin, display, forms}`.
- `splits`: Latin word -> ordered `[(surface, element_id)]`.
- `whole_names`, `themes`.
- Per species: `genus_parts`, `epithet_parts`, `has_parts`, `whole_name`.
  A card chain gets an **E** card only if `has_parts`.

Derived indexes: by family, order, genus, status, Hebrew, English, Latin;
element -> example species; element gloss sets for E options.

**Data version** is the SHA-256 of the canonicalized JSON (sorted keys,
UTF-8, no insignificant whitespace) of both files. It is stored in every
session and event. A mismatch triggers a warning, never a silent rewrite.

### 4.2 Identifiers

- `profile_id`: slug of the display name (`ran`), with a numeric suffix on
  collision, or `profile-<hex>` if the name has no slug. Display name can be
  changed; ID does not change.
- `session_id`: UTC timestamp plus short random suffix
  (`20261105-1432-a1b2`).
- `card_uid`: opaque `c_<12 hex>`. Public; the client uses it for answers.
- `event_id`: opaque `e_<12 hex>`.
- `species_id`: internal only. **It is never included in quiz payloads**
  (current card, lookahead, session summaries). Tests assert this. The event
  log may include it, plus Latin, for analysis.

### 4.3 Profile file: `learn/data/progress/<profile-id>/profile.json`

```json
{
  "schema_version": 1,
  "app_version": "0.1.0",
  "profile_id": "ran",
  "name": "Ran",
  "created_at": "2026-11-05T12:00:00.000Z",
  "updated_at": "2026-11-05T12:34:56.000Z",
  "settings": {
    "active_cap": 7,
    "lookahead_target": 50,
    "out_of_scope_reviews": true,
    "show_bridge": true
  },
  "global_counter": 1234,
  "passed": {
    "acrocephalus-agricola": {
      "latin": {
        "level": 1,
        "due_at": 1254,
        "mastered": false,
        "last_result": "correct",
        "last_at": "2026-11-05T12:30:00.000Z",
        "last_session_id": "20261105-1200-7f3a"
      }
    }
  }
}
```

- `passed` is keyed by `species_id` and then by skill. v1 only uses `latin`.
  The nesting leaves room for English directions later without a migration.
- `level` is 1..4; `due_at` is an absolute global counter; `mastered` means
  V4 passed and `due_at` is null.
- `global_counter` is profile-global and advances on every consumed card in any
  session, including L, E, skips and reviews.

### 4.4 Session file: `learn/data/progress/<profile-id>/sessions/<session-id>.json`

```json
{
  "schema_version": 1,
  "app_version": "0.1.0",
  "session_id": "20261105-1432-a1b2",
  "profile_id": "ran",
  "name": "Passerines — evening",
  "created_at": "2026-11-05T14:32:00.000Z",
  "updated_at": "2026-11-05T14:40:00.000Z",
  "data_version": "sha256:...",
  "skill": "he_to_latin",
  "status": "active",
  "filter": {
    "families": [],
    "orders": ["Passeriformes"],
    "genera": [],
    "statuses": ["regular", "introduced"],
    "search": ""
  },
  "settings": {
    "active_cap": 7,
    "lookahead_target": 50,
    "out_of_scope_reviews": true
  },
  "seed": 123456789,
  "initial_pool_size": 120,
  "pool": ["turdus-merula", "..."],
  "queue": [
    {
      "uid": "c_ab12cd34ef56",
      "species_id": "acrocephalus-agricola",
      "type": "L",
      "attempt": 1,
      "seed": 987654,
      "hint_level": 0,
      "retry": false,
      "revealed": false
    }
  ],
  "session_card_count": 12,
  "paused_review": null
}
```

- **`queue` is the single source of truth for order.** The active chains are a
  derived view: group the non-V cards by `species_id` and read them in queue
  order. No separate per-bird list is stored.
- `pool` is disjoint from `queue`: a bird is in exactly one of them (or in
  `passed`). Pulling a bird removes it from `pool` and inserts its chain into
  `queue`.
- `queue[0]` is the current card. Saving mid-card keeps it; reopening re-shows
  it. There is no separate `current_card` field.
- `session_card_count` counts consumed cards in this session only; it is not
  the scheduling clock.
- `paused_review` is the one exception to "V cards are not persisted": if the
  session was closed with a V card at the front, store
  `{uid, species_id, seed, level, retry}` here so reopening can re-show the
  same review. On open it is re-validated against the due pool; if no longer
  due or already claimed elsewhere, it is dropped. Other V cards in the queue
  are not persisted; they are re-derived from the shared due pool.
- `status`: `active` while learning cards remain or pool is non-empty;
  `completed` when both are empty. A completed session can be opened again for
  due V reviews.
- `initial_pool_size` is for progress display only (`passed / initial`).

### 4.5 Event log: `learn/data/progress/<profile-id>/events.jsonl`

Append-only, one JSON object per line, UTF-8. Every line is self-contained.

```json
{
  "event_id": "e_12ab34cd56ef",
  "schema_version": 1,
  "ts": "2026-11-05T14:40:00.123Z",
  "profile_id": "ran",
  "session_id": "20261105-1432-a1b2",
  "event": "answer_submitted",
  "data_version": "sha256:...",
  "card": {
    "uid": "c_ab12cd34ef56",
    "type": "F",
    "species_id": "acrocephalus-agricola",
    "attempt": 1,
    "seed": 987654,
    "hint_level": 0
  },
  "bird": {
    "latin": "Acrocephalus agricola",
    "english": "Paddyfield warbler",
    "hebrew": "...",
    "family": "Acrocephalidae",
    "genus": "Acrocephalus",
    "order": "Passeriformes",
    "status": "",
    "has_parts": true
  },
  "prompt": "hebrew name",
  "response": "acrocephalus agricola",
  "normalized_response": "acrocephalus agricola",
  "expected": "Acrocephalus agricola",
  "result": "correct",
  "genus_ok": true,
  "epithet_ok": true,
  "options": [],
  "latency_ms": 4200,
  "queue_position": 0,
  "global_counter_before": 1233,
  "global_counter_after": 1234,
  "session_card_count_before": 11,
  "session_card_count_after": 12
}
```

Event types:

- `profile_created`, `profile_renamed`, `profile_deleted`
- `session_created`, `session_opened`, `session_closed`, `session_reloaded`,
  `session_renamed`, `session_deleted`
- `card_presented` — records the exact card shown, including R/E options and
  hint availability. Re-emitted on resume.
- `card_advanced` — L and E; no graded answer.
- `element_answered` — one per E part; `result` is `correct` or `wrong`.
- `answer_submitted` — R/C/F/V; includes result, response, expected, per-word
  flags, options shown, hint level, latency.
- `hint_requested` — level and kind; not a consumed card.
- `card_skipped` — V only.
- `session_completed` — queue and pool empty.

`result` values: `correct`, `near_miss`, `wrong`, `assisted`, `revealed`,
`skipped`. L/E advancement uses `card_advanced` with no `result`.

The event log is for analysis, not for recovery. State files are the source of
truth.

## 5. Card generation

### 5.1 Chain

- With parts: `L -> E -> R -> C -> F`.
- Without parts: `L -> R -> C -> F`.
- Later: `V` when due.
- A bird is active while it has non-V cards in the queue.

### 5.2 Card views

The server generates a card view per type. Answer fields are only included
after submission.

**L — Learn (display only).** Family/order/status, Hebrew name, English name,
full Latin, every split part with its surface, English and Hebrew meaning and
theme, whole-name note if any, and the bridge line. One action: next.

**E — Elements.** One row per distinct element in the name (not per surface
occurrence), showing the surface(s) as they appear, the theme, and 4–5 Hebrew
gloss options. The user chooses a gloss for each row. Check reveals the correct
pairings and then continues. E is not a gate; wrong answers do not fail the
bird. Options are deduplicated by Hebrew gloss because 54 glosses are shared by
more than one element. Distractors come from the same theme first.

**R — Recognize.** Hebrew prompt only; 4–5 full Latin options, shuffled with
the card seed. No English, family or status. Distractors are chosen by
taxonomic proximity: same genus, then same family, then same order, then any;
the correct answer and all accepted answers are excluded from distractors. If
the pool is too small, use as many options as exist (minimum two).

**C — Construct.** Hebrew prompt; a scaffold showing, per Latin word, the
first letter and length; for split words, per part: its Hebrew meaning, first
letter and length. One text input for the full Latin name. The scaffold is part
of the design, not a hint.

**F — Produce.** Hebrew prompt; one text input; hint ladder on request. No
scaffold.

**V — Review.** Same view as F, plus `is_review`, `out_of_scope` and skip.

### 5.3 Hints

Ladder, per explicit request only:

1. F/V: first letter and length of each word (the C scaffold). For C: first two
   letters of each word or part.
2. 4–5 full Latin options, including the correct one.
3. Reveal the full answer.

- Any correct answer after a hint is recorded as `assisted`; after a reveal, as
  `revealed`. Neither advances the card. The card is reinserted 30–50 cards
  later without failure escalation.
- A reveal does not consume the card immediately: the answer is returned, the
  card is marked `revealed`, and the user's next action (next/continue)
  consumes it as `revealed`.
- R has no hint button: its options are the hint. E has no hint button.
- Hints are not available on L.

### 5.4 Grading

**Latin (v1).** Normalize NFC, trim, collapse whitespace, casefold. Expected is
the Latin name split on spaces (always two words in the current data).

- Both words exact -> `correct`.
- Both words exact except for a small spelling difference -> `near_miss`.
  Near-miss threshold: total Damerau-Levenshtein distance <= 2, same word
  count, and the first letter of each word matches. Genus/epithet flags are
  reported separately.
- Otherwise -> `wrong`.
- Near-miss is not a pass. It is a soft return: reinsert 30–50 cards later,
  no failure escalation.
- A correct retry after a wrong answer is a pass for F (the failure move is
  scheduling, not a hint). V is different: a retry pass does not advance the V
  level.

**Shared Hebrew name.** The two *Oenanthe* species share one Hebrew name. The
card is generated for one species, but either Latin species is accepted. R
options include both; both are excluded from distractors. Feedback shows both.
The card's species is the one that passes. This is the agreed edge-case rule.

**Elements.** The user picks a Hebrew gloss; the correct gloss is the element's
`he`. Because glosses are not unique, any element with that gloss is accepted;
options are deduplicated by gloss. Wrong answers reveal and continue.

**Hebrew/English (later).** Hebrew prompt matching normalizes ASCII hyphen,
maqaf, space, geresh/gershayim and whitespace. English grading will be
case-insensitive with hyphen/apostrophe/space normalization and diacritic
folding. Neither is a v1 quiz direction.

### 5.5 Bridge line

Display-only heuristic on L: for each element in the Latin name, look for its
Hebrew gloss as a word or substring of the Hebrew name after normalization.
Show matches as `Hebrew word ↔ Latin part (English meaning)`. Omit the line if
there is no confident match. It is never graded and can be turned off in
settings.

### 5.6 No answer leakage

- Current card payloads for R/C/F/V contain no `expected`, no full Latin, no
  English, no family and no status. R's options necessarily contain the correct
  Latin among the distractors; that is inherent to recognition.
- Lookahead items contain only `hebrew`, `type`, `is_review`,
  `out_of_scope`. No species ID, Latin, English, family or status.
- Session summaries contain counts and names, never the current card's Latin.
- API tests assert these rules.

## 6. Scheduling

### 6.1 Counters and due

- `global_counter`: one increment per consumed card, in any session for that
  profile. L next, E submit, R/C/F answer, V answer, V skip all increment
  exactly once. Presentations, hints and opening a session do not increment.
- `session_card_count`: same event, per session.
- `due_at` is an absolute global counter. A passed bird is due when
  `due_at <= global_counter`.
- Schedule after incrementing the counter for the card just consumed.

V intervals, by the level being scheduled:

| Level | Interval after the previous review |
|---|---|
| V1 | 20 cards after F pass |
| V2 | 60 cards after V1 pass |
| V3 | 150 cards after V2 pass |
| V4 | 400 cards after V3 pass |

- Passing V4 sets `mastered: true`, `due_at: null`; the bird stays in `passed`
  so it remains excluded from pools.
- A retry pass or hint-assisted pass at V does not advance; schedule the same
  level again using that level's interval.
- A V skip does not change the level; `due_at = counter + 100`.

### 6.2 Queue representation

- `queue` is the ordered list of concrete card descriptors; `queue[0]` is
  current.
- The active bird count is the number of distinct species with non-V cards in
  the queue. V cards do not count.
- `pool` and `queue` are disjoint.
- There is no anti-adjacency rule: two cards of the same bird may be adjacent.
- The only hard order constraint: for each bird, its remaining non-V cards
  appear in chain order.

### 6.3 Refill

Called at session creation (without reviews), on open, after every consumed
card, and on reload.

1. **Inject due V cards** for birds in `passed` with `due_at <= global_counter`,
   not mastered, not already claimed and not already in the queue. In-scope
   cards always; out-of-scope cards only if the session setting allows. Mark
   each claimed by this session. Spread them with a gap of about 10 cards
   (`V_INJECT_GAP`); if there are more due than fit, the rest wait for the
   next refill.
2. **Pull a new bird** while active count < `active_cap` and `pool` is not
   empty: pop the next shuffled bird, build its chain, insert L within the next
   5–12 cards, then insert the remaining chain cards after it in order with
   random gaps of 2–8 cards.
3. **Complete** if the queue is empty and pool is empty: status `completed`,
   emit `session_completed`, return a completed view.

The queue target of ~50 is **soft**. With cap 7 and 4–5 card chains, the
learning queue is normally 28–35 cards; retries, fallback mini-chains and V
cards can take it toward 50. We do not start birds beyond the cap just to fill
the queue.

### 6.4 Consuming a card

The server validates that the submitted `card_uid` is `queue[0]`. The transition
table:

| Card | Exact correct (unaided) | Near-miss | Assisted / revealed | Wrong |
|---|---|---|---|---|
| L | advance | — | — | — |
| E | advance (per-part results) | — | — | reveal and advance |
| R | advance to C | soft return | n/a | hard fail |
| C | advance to F | soft return | soft return | hard fail |
| F | pass; schedule V1 | soft return | soft return | hard fail |
| V | advance level if fresh, else same level | same level | same level | retry once, then fallback |

- **Soft return:** remove the card and the bird's later chain cards, move the
  card 30–50 cards ahead, then reinsert the later chain cards after it in
  order with random gaps. No failure count; `attempt` stays 1.
- **Hard fail:** first failure -> same card with `attempt: 2`, moved 30–50
  cards ahead, later chain cards after it. Second failure -> fallback one card:
  F -> C, C -> R, R -> L. Remove the failed card and later chain cards; insert
  the fallback card, then the failed card, then the rest, in order with gaps.
  The fallback card starts at `attempt: 1`.
- **Fallback chain semantics:** F fail twice -> `C -> F`; C fail twice ->
  `R -> C -> F`; R fail twice -> `L -> R -> C -> F`. E is not repeated. The
  bird stays active.
- **Passing F:** remove the bird's remaining cards (normally none after F), add
  it to `passed` with `level: 1`, `due_at: counter + 20`, `mastered: false`;
  free the active slot; pull a new bird if the pool has one.
- **E:** one card, several part answers; always advances after reveal; no
  failure move.
- **V fail, first time:** retry the same V after 30–50 cards.
- **V fail, second time:**
  - In-scope: remove from `passed`; insert a fresh F card for the bird into the
    queue. F's failure ladder applies. If F passes, re-add to `passed` with a
    fresh V1.
  - Out-of-scope: remove from `passed`; do not insert an F chain. The bird is
    handed back to normal sessions. The session records the hand-back; no
    automatic re-add.
- **V skip:** remove the V card, release the claim, `due_at = counter + 100`,
  level unchanged, emit `card_skipped`.
- **Active cap overflow:** an in-scope V-failure F chain may temporarily take
  the active count to cap + 1. Do not pull new birds until it drops below the
  cap.

### 6.5 Worked example

Two birds, global counter 100, cap 7, no V due.

- A = *Acrocephalus agricola* (parts), chain `L E R C F`.
- B = *Turdus merula* (no parts), chain `L R C F`.
- Creation pulls A and B. Queue: `A/L, A/E, B/L, A/R, B/R, A/C, B/C, A/F, B/F`.

| Step | Card | Result | Counter | State |
|---|---|---:|---:|---|
| 1 | A/L | next | 101 | A/E current |
| 2 | A/E | check | 102 | B/L current |
| 3 | B/L | next | 103 | A/R current |
| 4 | A/R | correct | 104 | B/R current |
| 5 | B/R | wrong (1st) | 105 | B/R moved ahead; A/C current |
| 6 | A/C | correct | 106 | A/F current |
| 7 | A/F | correct unaided | 107 | A passed; V1 due 127; B/R current |
| 8 | B/R | correct retry | 108 | B/C current |
| 9 | B/C | correct | 109 | B/F current |
| 10 | B/F | correct | 110 | B passed; V1 due 130; session complete |

At counter 127, A's V1 becomes due; at 130, B's. They are injected into the
next active session (in-scope or out-of-scope per settings).

### 6.6 Invariants

Checked in tests after every transition:

- Every card UID is unique in the queue.
- For each bird, its non-V cards appear in chain order.
- A bird appears in at most one of `pool`, `queue` and `passed`.
- No more than one card of a given type per bird (except the fallback chain,
  which is also one per type).
- Active count <= cap + 1 (the V-failure overflow).
- V cards are unique per bird and claimed exactly once.
- `global_counter` increases by exactly one per consumed card.
- `session_card_count` increases by exactly one per consumed card.
- Mastered entries have `due_at = null`; non-mastered entries have an integer.
- No answer fields in non-L current card payloads or lookahead.

## 7. Profiles, sessions and lifecycle

### 7.1 Profiles

- Create with a display name; generate a filesystem-safe ID.
- Main screen lists profiles and due-review counts.
- Rename changes the display name only; the ID and files stay.
- Delete requires confirmation; if committed, git is the backup. If the
  profile has an active session, close it first.
- Settings: default active cap, lookahead target, out-of-scope reviews, bridge.

### 7.2 Sessions

- Create: choose a filter, preview the eligible count, name the session (auto
  from local start time, editable), set advanced options, create. The server
  computes the eligible set, subtracts `passed`, shuffles with a stored seed,
  builds the pool and initial queue (no V injection yet), and saves.
- Eligibility default: `regular` + `introduced`; `accidental`, `historical` and
  `extinct` are opt-in. H→L always requires a Hebrew name, so the five
  no-Hebrew species are excluded.
- Filter semantics: AND across dimensions (`families`, `orders`, `genera`,
  `statuses`, `search`); OR within a dimension; empty list means unrestricted.
- Open: close any other active session, load, validate data version, prune
  passed birds from pool and queue (see open decision), re-claim
  `paused_review` if still valid, refill with V injection, return current card
  and lookahead.
- Close: save, release claims, emit event, clear active session.
- Resume: `queue[0]` is re-shown, so closing mid-card resumes exactly, except
  for passed-bird pruning and V re-derivation.
- Reload: drop passed birds from queue and pool, release stale claims, refill.
  Keeps the session's own progress and counter history.
- Completed: pool and queue empty. Can be reopened for due V. Stays saved.
- Rename/delete: same safety as profiles.
- One active session at a time. Two saved sessions may learn the same
  not-yet-passed bird; only `passed` is globally excluded.

### 7.3 Passed table and reviews

- `passed` is profile-global, keyed by species and skill.
- V cards are profile-global but claimed by the active session so the same
  review is not shown twice.
- Out-of-scope V cards are allowed by default, marked, and skippable; a session
  setting can disable them.
- The main screen shows the global due count.
- In-scope V failure re-enters F; out-of-scope V failure hands the bird back.
- A bird removed from `passed` after a V failure is available to new/reloaded
  sessions; existing sessions do not retroactively add it.

## 8. HTTP API

All API responses are JSON. Static files are served from `learn/src/web/` only.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | app/data/schema versions, counts |
| GET | `/api/profiles` | profiles + due counts |
| POST | `/api/profiles` | create profile |
| GET | `/api/profiles/<pid>` | profile summary/settings |
| PATCH | `/api/profiles/<pid>` | rename/settings |
| DELETE | `/api/profiles/<pid>` | delete profile |
| GET | `/api/profiles/<pid>/catalog` | filter options + counts |
| POST | `/api/profiles/<pid>/catalog/preview` | eligible/pool count for a filter |
| GET | `/api/profiles/<pid>/sessions` | session summaries |
| POST | `/api/profiles/<pid>/sessions` | create session |
| GET | `/api/profiles/<pid>/sessions/<sid>` | session view (current/lookahead) |
| POST | `/api/profiles/<pid>/sessions/<sid>/open` | open/resume |
| POST | `/api/profiles/<pid>/sessions/<sid>/answer` | submit L/E advance or R/C/F/V answer |
| POST | `/api/profiles/<pid>/sessions/<sid>/hint` | request next hint |
| POST | `/api/profiles/<pid>/sessions/<sid>/reload` | prune passed + refill |
| POST | `/api/profiles/<pid>/sessions/<sid>/close` | save and release |
| PATCH | `/api/profiles/<pid>/sessions/<sid>` | rename/settings |
| DELETE | `/api/profiles/<pid>/sessions/<sid>` | delete |

The answer request carries `card_uid`, `action`
(`advance`/`answer`/`skip`), `response`, `hint_level`, `latency_ms`. The server
grades and returns feedback plus the next current card and lookahead.

Errors use a stable code and a human message:

- `profile_not_found`, `session_not_found`, `session_not_active`,
  `stale_card`, `invalid_action`, `empty_pool`, `data_invalid`,
  `save_failed`, `internal_error`.

Status codes: 400 invalid request, 403 cross-origin, 404 not found, 409 stale
card/active conflict, 422 empty pool/semantic error, 500 internal.

Security and robustness:

- Bind `127.0.0.1` by default; never `0.0.0.0` without an explicit flag.
- Reject requests whose `Origin` is not the local app origin.
- Require `Content-Type: application/json` for mutations; cap body at 1 MB.
- No CORS headers. No external network calls.
- Static paths are resolved under `learn/src/web/`; reject `..`, absolute paths
  and symlink escapes. Serve only known extensions.
- Escape all user-controlled names in the UI with `textContent`.
- API responses are `Cache-Control: no-store`; static assets `no-cache` during
  local use.

## 9. UI

### 9.1 Screens

- **Main / profile:** profile switcher, due-review count, session list with
  name, progress (`passed / initial`), status, and resume/reload/rename/delete.
- **New session:** name, filters (orders, families, genera, statuses, search),
  live preview count with exclusions, advanced settings, create.
- **Session:** header (session name, counts, due count, main link), current
  card, feedback, collapsible lookahead.

### 9.2 Lookahead

- Next 5 cards.
- Each row: Hebrew name + card type badge. V cards show a review badge;
  out-of-scope V cards show a marker.
- Never Latin, English, family, status or internal IDs.
- Collapsible; the collapsed state is cosmetic and may live in localStorage.

### 9.3 Card presentation

- Book-like paper panel: cream background, ink text, grey element parts,
  ochre accents, thin rules. Hebrew RTL; Latin and English LTR spans.
- L: family/order at top, Hebrew large, English, Latin with parts, element
  list, bridge, one next button.
- E: part rows with option buttons/selects, check, reveal, continue.
- R: Hebrew prompt, large Latin option buttons, numbered shortcuts.
- C: Hebrew prompt, scaffold box, LTR input, submit, hint.
- F/V: Hebrew prompt, LTR input, submit, hint; V adds skip and out-of-scope
  badge.
- Feedback: result banner, expected Latin with parts, English, family/order,
  per-word marks; E shows per-part results. Wrong cards say they will return;
  V failure says it will return or is handed back, without exposing counters.
- No timer, no idle detection, no countdown. Stop at any time by closing.

### 9.4 Keyboard and accessibility

- Enter submits/advances.
- 1–5 choose R options.
- `h` requests a hint on C/F/V.
- `s` skips a V card.
- Shortcuts are ignored while typing in an input, except Enter.
- `aria-live` for feedback, visible focus, text labels in addition to colour,
  logical CSS properties for RTL, sufficient contrast.
- Latin inputs: `dir="ltr"`, `autocomplete="off"`, `autocapitalize="none"`,
  `spellcheck="false"`.

### 9.5 States

- No profiles: create-profile screen.
- Empty pool: explain why (no Hebrew, all passed, filter too narrow) and let
  the user change the filter.
- Data version mismatch: banner with "reload session" and a link to details.
- Stale card (409): refresh the current card automatically, with a brief note.
- Save failed: persistent banner; do not advance the in-memory state.
- Server down: "start the trainer" message.

## 10. Persistence, versions and operations

- **Atomic writes:** write `.<name>.tmp` in the same directory, flush, fsync,
  `os.replace`. JSON is UTF-8, `ensure_ascii=False`, indent 2 for state files;
  events are compact one-line JSON.
- **Event append:** open in append mode, write one line, flush, fsync. A
  partial last line is ignored on read.
- **Commit order:** compute next state in a copy; write profile and session;
  append events; then replace in-memory state. If a write fails, keep the old
  state and return `save_failed`.
- **Crash consistency:** state writes are atomic per file, but profile and
  session are two files. On startup, validate the active session; if its
  current card looks already answered in the event log, show a recovery banner
  and offer reload. This is an accepted local-app trade-off, not a database
  guarantee.
- **Locking:** in-process `threading.RLock` per profile/session. A
  `learn/data/progress/.lock` file with `fcntl.flock` prevents two server processes on
  Unix. Linux-first; Windows is not a v1 goal.
- **Schema versions:** integer on profile, session and event. Load refuses a
  future version; migrations apply in order for older versions. v1 has no
  migrations yet, but the hook exists.
- **Data version:** canonical JSON hash of both data files. Store in sessions
  and events. On mismatch, warn; drop missing species cards; offer reload. Do
  not silently rewrite progress.
- **Orphans:** passed entries whose species no longer exists are kept but
  ignored, with a warning; a cleanup action can remove them later.
- **Backup:** git is the primary backup. The app can optionally keep one
  `.bak` per state file before replace; this is a small safety net, not a
  replacement for commits. Document `git add progress && git commit`.
- **Event log growth:** one file now. Events are roughly 1 KB; rotate by month
  later if it becomes large.
- **Privacy:** everything is local; no telemetry, no external requests. Server
  logs contain IDs and errors, not answers.
- **Time:** store UTC ISO-8601 with milliseconds; display local time. Session
  names auto-generated from local time at creation.
- **Randomness:** session seed stored; card seeds stored; tests inject RNG.
  IDs use `secrets`, scheduling uses `random.Random`.

## 11. Testing

Run from the repository root:

```sh
cmake --build build --target test-learn
# or
cd learn/src && python3 -m unittest discover -v
```

Test layers:

1. **Dataset tests** against the real files:
   - 565 species, all Latin names two-word ASCII, genus+epithet match.
   - All splits reference existing elements; surfaces concatenate to the word
     case-insensitively; elements have en/he/theme; themes list is consistent.
   - Five no-Hebrew species; one shared Hebrew name; 29 families without
     Hebrew; 54 duplicate Hebrew glosses.
   - Data hash is stable and changes when content changes.
2. **Normalization/grading tests:** case, whitespace, maqaf/hyphen, geresh,
   near-miss thresholds, genus/epithet flags, shared Hebrew accepts either,
   element gloss deduplication.
3. **Card tests:** chain with/without parts; E targets only split words; R
   option count and taxonomy; no answer leakage; option determinism by seed;
   hint ladder; C/F scaffolds; L bridge.
4. **Queue tests:** insertion order, chain order, failure distance, fallback
   chain, active cap, pool/queue disjointness, V injection spacing, skip
   snooze, counter increments.
5. **Scheduler tests:** the worked example; F pass -> passed/V1; F retry pass;
   near-miss soft return; assisted/revealed; hard fail twice; V levels; V
   retry pass same level; in-scope/out-of-scope V failure; skip; reload.
6. **Store tests:** round-trip profile/session; atomic replace; corrupted JSON;
   partial last event line; schema migration hook; lock behavior.
7. **API tests:** ephemeral server on port 0, temp progress dir; every endpoint;
   stale card 409; empty pool 422; cross-origin 403; path traversal 404;
   no Latin in lookahead/non-L cards; body limit.
8. **Randomized invariant test:** for several seeds, simulate hundreds of
   random valid actions and assert all invariants after each step.
9. **Manual checklist:** create profile, create small session, complete L/E/R/C/F,
   pass a bird, see V due, hint, near-miss, fail twice, skip V, close, restart
   server, resume, reload, rename/delete. Use a dev flag to shorten intervals
   for manual V testing.

No browser automation in v1 (would add a dependency). The manual checklist is
the UI gate. Optional later: Playwright or a headless browser.

## 12. Deployment and workflow

- Run: `cmake --build build --target run-learn`, or
  `cd learn/src && python3 -m birdtrainer serve --open`.
- Default port 8765; `--port`, `--host`, `--data-dir`, `--progress-dir`,
  `--log-level`, `--no-open`, `--dev-fast-review`.
- The `run-learn` CMake target sets `PYTHONPATH=learn/src`, passes the data
  and progress paths, prints the URL, and opens the browser.
- No install step, no package build, no pip, no venv. The book's venv is
  independent and not required.
- The server writes only under `learn/data/progress/`; it never modifies
  `data/` or `book/`.
- Git workflow: the user commits `learn/data/progress/` when desired. The app
  never commits or pushes. Cross-device continuation is: close the app, commit,
  push, pull on the other machine. Do not run two machines at once.
- `.gitignore` additions: `/build/`, `/book/out/`,
  `learn/data/progress/**/*.tmp`, `learn/data/progress/**/.lock`, and
  `__pycache__/`. `data/out/` is committed.
- `learn/README.md` documents run, test, backup, restore, ports, and the
  progress file layout.

### Implementation slices (review gates)

1. **Skeleton + data:** tree, config, dataset loader/validation, `validate`
   CLI, static "hello" server, test harness. Review.
2. **Cards + grading (no persistence):** models, normalize, grading, options,
   card views, scaffolds, hints, bridge. Review.
3. **Queue + scheduler (pure):** pool, queue, failure moves, V scheduling,
   worked example, randomized invariants. Review.
4. **Profiles + sessions + store:** atomic JSON/JSONL, events, create/open/
   close/resume/reload. Review.
5. **HTTP API:** endpoints, security, static serving, no-leak tests. Review.
6. **UI core:** main, new session, L/R/F, feedback, lookahead, close/resume.
   Review.
7. **UI complete:** E, C, V, hints, skip, out-of-scope, fallback, reload.
   Review.
8. **Polish:** book styling, RTL, keyboard, accessibility, error states,
   README, manual acceptance. Review.

No slice starts before the previous one is reviewed. No commits unless asked.

## 13. Open decisions

### 13.1 Tree and package name (settled)

The trainer lives under `learn/`, parallel to `book/` and `data/`:
`learn/src/birdtrainer`, `learn/src/web`, `learn/src/tests`, and user data in
`learn/data/progress`. There is no `learn/build` or `learn/out`; all build
artifacts go to the top-level disposable `build/`, and the trainer runs from
`learn/src`. There is no separate `trainer/` directory.

### 13.2 Internal bird ID

Proposed: `species_id` = lowercase `genus-epithet` slug. It is human-readable in
progress files and stable for v1. The ringer key (`PASMOA`) is a computed
display/export label; it is not the persistent ID until the collision rule in
`learn/TODO.md` is settled. The species ID is never sent to the quiz client.
Alternative: an opaque hash, which hides taxonomy but makes progress files
unreadable and still changes if the Latin name changes. Recommendation: slug.

### 13.3 Queue target vs active cap

With cap 7 and 4–5 card chains, the learning queue is ~28–35 cards, not 50.
Proposed: treat 50 as a soft target; retries, fallback chains and V cards fill
it when present. Do not start more than 7 birds to reach 50. Alternative: raise
the cap to ~10, or prefetch L cards for pool birds (which would start them).
Recommendation: soft target, cap 7.

### 13.4 Resume with newly passed birds

Proposed refinement of `REFERENCE.md`: on open, prune birds that are now in
`passed` from the session's pool and queue, then refill. The rest of the queue
is preserved. This matches "passed birds are excluded" and avoids a learning
card and a V card for the same bird. Alternative: resume exactly and require a
manual reload. Recommendation: prune on open, with an event and a small banner
("N passed birds dropped").

### 13.5 V-card persistence

Proposed: persist only the V card that was at the front when the session was
closed (`paused_review`); re-derive other V cards from the due pool on open.
This preserves "resume mid-card" without duplicating unshown reviews across
saved sessions. Recommendation: as proposed.

### 13.6 Soft-return policy

Proposed: near-miss, assisted and revealed answers are soft returns (reinsert
30–50 cards later, no failure escalation). Only a wrong answer is a hard fail
(retry once, then fall back one card). For V, near-miss/assisted/revealed
re-schedule the same level. This is stricter than "wrong = retry" for typos and
gentler than falling back on a typo. Recommendation: as proposed.

### 13.7 Bridge line

Proposed: implement the heuristic in v1 behind a setting; omit uncertain
matches. Alternative: defer to v1.1. Recommendation: implement a conservative
version, since L is the learning card and the bridge is its main payoff.

## 14. Definition of done for v1

- A profile can be created and reopened.
- A session can be created with a family/order/genus/status/search filter,
  previewed, named, and started.
- L, E, R, C, F cards appear in the correct order; hints work; feedback is
  clear.
- Passing F adds the bird to the shared passed table and schedules V1.
- V1–V4 due cards appear in any session, in-scope or marked out-of-scope;
  skip works; failure retries and hands back correctly.
- Failures move cards, retry once, and fall back one card.
- Closing and restarting the server resumes the same queue; reload drops passed
  birds.
- Progress files and `events.jsonl` are written and git-committable.
- No writes to `data/` or `book/`.
- Tests pass, including randomized invariants and no-answer-leakage checks.
- The user can use it offline for a real session without the developer.
