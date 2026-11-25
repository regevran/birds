# Trainer design

Status: the Worker is implemented (see `learn-cloudflare.md`) and the browser
L face is in development. The Python text client renders JSON and stores
credentials. This file records the trainer design; hints and review levels are
not implemented, and passing/mastery was removed (see "Deferred" below).

Canonical companions: `learn-cloudflare.md` (storage/Worker implementation),
`learn/WORKER-API.md` (endpoint contract), `learn/CLI-USAGE.md` (text client),
`decisions.md` (choices and reasons).

## Purpose

A browser trainer for the book's dataset: Latin, English and Hebrew names plus
the etymology elements of Latin names. The v1 skill is **Hebrew → Latin**;
English directions come later. No timer: practise as long as wanted, stop at
any time, resume the saved queue.

## Vocabulary

- **Profile** — a person; settings and the global counter. There is no
  mastery table.
- **Session** — a saved timeline with its own filter and card counter.
  Sessions are independent.
- **Pending** — ordered per-bird groups of card specs not yet in the queue.
  Every eligible bird starts with its chain here; pulling a bird moves its
  group into the queue.
- **Active chain** — the queued cards of one bird: `L→E→R→C→F` or
  `L→R→C→F`.
- **Queue** — the materialised unseen cards; `queue[0]` is the frontier.
- **History** — completed cards in timeline order; the client may browse it.
- **Global counter** — one increment per consumed card (or wrong redo).

```text
PENDING (per bird, ordered)        ACTIVE (max 7)                 QUEUE
A: [L E R C F]  ──pull whole─>  A: L✓ E R C F  ──interleave──>  [B/R] [A/E] [C/R] ...
B: [L R C F]
C: [L E R C F] ...
```

## Dataset facts that shape the trainer

- 565 species, 84 families, 249 genera, 26 orders.
- 560 species have Hebrew (559 unique names); 5 have no Hebrew; one name
  (`סלעית לבנת-כנף`) is shared by *Oenanthe lugens* and *O. warriae*.
- 13 families (29 species) lack `family_he`.
- Statuses: 381 regular, 167 `A`, 11 `I`, 2 `Ex`, 3 `Ex/A`, 1 `X`.
- Etymology: 95 species fully split, 232 partially, 238 not; 113 of 249 genera
  have a split. 308 elements, 312 split words, 16 whole names.
- No niqqud; 124 Hebrew names use ASCII `-`; 155 English names contain
  hyphens, 42 apostrophes, 2 diacritics.
- Default practice scope: regular + introduced; accidental and historical are
  opt-in. H→L requires Hebrew, so the five no-Hebrew species are excluded.
  Family and status are context, never quizzed. Only split words get an E card.

## Cards

| Card | Name | User action |
|---|---|---|
| **L** | Learn | Display only: family/order, Hebrew, English, Latin, parts and meanings, bridge. Next only. |
| **E** | Elements | Choose one Hebrew gloss per element row. Options stay within the row's theme; the theme is a hint. Not a gate. |
| **R** | Recognize | Hebrew → choose the Latin from 4–5 options. No English/family. Wrong: one retry; second wrong reveals. |
| **C** | Construct | Hebrew → type the Latin with a one-line scaffold of word shapes and part lengths/glosses. Near miss reveals and moves on; wrong: one retry, then reveals. |
| **F** | Produce | Hebrew → type the Latin unaided. Same grading as C. |

- F is the last card of a bird's chain. A correct F completes the chain; there
  is no passing, retirement or review-level state. A bird may appear again in
  a later session.
- Genus and epithet are scored separately for partial credit.
- R distractors come from the same genus, then family, then order, then any;
  the correct answer and all accepted answers are excluded. Shared-Hebrew
  species are both accepted and both shown in feedback.
- E options are deduplicated by Hebrew gloss; any element with the chosen
  gloss is accepted.
- The L **bridge** line heuristically shows Hebrew-word ↔ Latin-part matches;
  it is display-only, never graded, and can be turned off. The browser L face
  does not render it — the parts decomposition carries the glosses — but the
  CLI still prints it.
- **Hints** (future): request length/first letters → 4–5 options → reveal.
  Assisted or revealed answers are soft returns; R's options are its hint, and
  L has no hints.

### Latin grading

Normalize with NFC, trim, collapse whitespace and casefold. A near miss has
the same word count, matching first letters and total Damerau-Levenshtein
distance ≤ 2; otherwise the answer is wrong. Feedback shows per-word status
and caret markers under differing letters. Hebrew/English grading is later
(normalize hyphen/maqaf/space, geresh/gershayim; English also diacritics).

## Series

Cards are independent units: a card defines no relation to L, E, R, C or F. The
order is imposed by an external **series**, which combines membership (how cards
enter), ordering (per-bird chains, interleaving, fixed list vs pooled refill),
persistence (ephemeral or saved, with or without concurrency), progression
(retiring a bird, reviews) and completion.

A session is one series instance — the complex one. A card run is another —
query, one card type, search order, ephemeral. The chain `L→E→R→C→F` is just
the ordering the session series allows; `R→C`, `R→E` and others are different
orderings over the same cards, not different card types. Because the pending
pool is card-based, a future series (for example every bird's C card) is a
selection over the same inventory. New series are a group-level design
question, taken together rather than as ad-hoc variants.

## Scheduling

- A live consumed card increments `global_counter` and moves from `queue[0]`
  to `history`. Opening, presenting and hints do not. `session_card_count` is
  the history length.
- `queue` is the source of truth for the future. `queue[0]` is the frontier;
  `pending` is disjoint from it. A bird is active while it has queued cards.
  Only chain order is constrained; cards of one bird may be adjacent.
- Active cap **7** (settings 5/7/10). With 4–5 card chains the queue is
  normally 28–35. Never start more than 7 birds just to fill the queue.
- Refill: pull whole pending groups and interleave them while fewer than
  `active_cap` birds are active.
- **Soft return** (near miss): move the card (as a fresh instance) and its
  later chain 30–50 cards ahead; `attempt` stays 1.
- **Hard fail:** first wrong moves the card (attempt 2) and later chain ahead.
  Second wrong falls back one card (`F→C`, `C→R`, `R→L`); the fallback starts
  at attempt 1 and the bird stays active.
- E always advances after its one-pass check; L advances.
- A correct F completes the chain; no bird is retired.
- A session is `completed` when queue and pending are empty; it stays saved.
- `percent_completed` = share of the session's initial birds with no pending
  or queued cards, floored; 100 only when done.

## Sessions, history and redo

- Sessions are independent Worker documents with **no active one**. Each
  client selects a session locally per server/account
  (`~/.birds_trainer_state.json`, `BIRDS_TRAINER_STATE` overrides). Clients may
  select different sessions or share one.
- `default` always exists, has no filters, contains every eligible bird, and
  cannot be deleted or renamed; it is the fallback when a client has no
  selection or its selection disappeared. Other names are optional and unique.
- Handles resolve Worker-side: exact name → exact id → unique id prefix,
  case-insensitive. `--name` forces a name match.
- Create: filter → eligible birds (Hebrew only) → one pending group per bird,
  shuffled with a stored seed → initial queue; birds are drawn randomly, with
  no family blocks. Eligibility defaults to regular + introduced; `default`
  has no status filter.
- The session stores `created_from`, the Worker-formatted search and criteria
  (e.g. `search "acrocephalus-agricola" · status: accidental`), and the
  `active_cap` it was created with; the summary/view returns both. The browser
  shows the origin read-only, so CLI-only family/order/genus/status criteria
  are visible; `default` has none. The string is also the base for future
  custom series.
- Two sessions may contain the same bird. Broadening scope means creating a
  new session; the old one remains.
- `/prepare` refreshes the view only; it no longer prunes anything.
- Session documents are schema version 2 only; there is no migration from the
  earlier species-pool shape.
- Rename changes or clears a name; the id, queue, progress and client
  selections do not change. Delete removes any non-`default` session; a client
  whose selection vanished falls back to `default`.
- Two clients on one session see each other's progress. The answer route
  classifies the submitted uid: the frontier is a live answer, a history card
  is a redo, an unseen non-frontier card is `409 not_current`, an unknown uid
  is `409 stale_card`. A stale write returns `412`; the client reloads.
- The client holds the browsing cursor; the Worker serves history windows
  (`GET /app/sessions/<id>/history?before=&limit=`) and the frontier.
- **Redo:** a correct/advance redo records only — no refill, no new bird, the
  future is unchanged. A wrong redo truncates history after the redone card,
  pours the invalidated cards (completed future and planned queue) back into
  their birds' pending groups in timeline order, re-applies the failure retry,
  and returns a view where everything after the redone card is unseen. Redo
  grading is a final attempt (at least 2), so a single wrong answer is `wrong`.

## Deferred: passing, mastery and V reviews

Removed from the model in November 2026 to simplify the history/redo work. A
bird may be replayed in a new session. Reintroducing mastery or review levels
later should build on the card-level pending pool and the redo rules above;
the earlier V1–V4 design is not part of the current schema.

## Browser UI (next)

- Screens and regions: settled in `learn-ui.md` (shell, learning area, search
  region, session drawer); the earlier three-screen sketch is superseded.
- Look-ahead: next 5 cards, Hebrew name + card type only; never Latin, English,
  family or internal ids. Collapsible.
- Card presentation: book-like cream paper, ink text, grey parts, ochre
  accents. L shows the reference panel; E uses option buttons; R uses large
  Latin options with number keys; C/F use a Latin input (LTR) and submit.
- Feedback: result banner, expected Latin with parts, English and family;
  per-word marks for C/F, per-part results for E. Do not expose counters.
- Keyboard: Enter submits/advances; 1–5 choose R options; hints and V skip when
  those exist. Ignore shortcuts while typing except Enter.
- Accessibility: `aria-live` feedback, visible focus, labels in addition to
  colour, logical CSS properties for RTL. Latin inputs use `dir="ltr"`,
  `autocomplete="off"`, `autocapitalize="none"`, `spellcheck="false"`.
- States: no profile; empty pool (explain why); data mismatch; stale card
  (reload); save failed (do not advance); server down.
- Bird illustrations: https://github.com/alchaincyf/huashu-bird-sticker (CC BY
  4.0, credit next to the image) cover every species and are in v1, on every
  card. A reader speaks visible names from pre-generated clips (Latin
  required; English and Hebrew later); the pronunciation convention is not
  chosen. Details: `learn-ui.md`.

## Later

- Global search: `/` from any screen; grouped read-only results (families,
  completed birds, elements, cards) opening card previews; never changes
  progress. Needs dataset search indexes and session-independent card views;
  no family/genus pages.
- English directions, whole-name deck, element free-typing, typography
  tolerance, images/audio, export/import.
