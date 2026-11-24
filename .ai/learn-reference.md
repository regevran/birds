# Trainer design

Status: implementation is the Worker (see `learn-cloudflare.md`). The Python
text client renders JSON and stores credentials. This file records the trainer
design; V, hints and the browser UI are not implemented yet.

Canonical companions: `learn-cloudflare.md` (storage/Worker implementation),
`learn/WORKER-API.md` (endpoint contract), `learn/CLI-USAGE.md` (text client),
`decisions.md` (choices and reasons).

## Purpose

A browser trainer for the book's dataset: Latin, English and Hebrew names plus
the etymology elements of Latin names. The v1 skill is **Hebrew → Latin**;
English directions come later. No timer: practise as long as wanted, stop at
any time, resume the saved queue.

## Vocabulary

- **Profile** — a person; settings, global `passed` table and global counter.
- **Session** — a saved queue with its own filter, pool, active chains and
  card counter. Sessions are independent; `passed` and reviews are shared.
- **Pool** — the session's filtered birds minus passed birds, shuffled; birds
  not yet started.
- **Active chain** — the remaining cards for one bird: `L→E→R→C→F` or
  `L→R→C→F`.
- **Queue** — the ordered cards to present; `queue[0]` is current.
- **Passed** — profile-global map of birds that passed F, with V level and
  due counter.
- **Global counter** — one increment per consumed card in any session.

```text
POOL / SET                        ACTIVE (max 7)                 QUEUE (~50 cards)
[bird8] [bird9] ...  ──pull──>  A: L✓ E R C F  ──interleave──>  [B/R] [A/E] [C/R] ...
                                B: L✓ R C F
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
| **V** | Review | Same as F, when due; skippable. Future design. |

- **Passing F** = unaided correct. A correct retry after a wrong answer counts
  as a pass for F; V treats a retry as not advancing. A bird always goes
  through its chain once.
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
query, one card type, search order, ephemeral, no `passed` changes. The chain
`L→E→R→C→F` is just the ordering the session series allows; `R→C`, `R→E` and
others are different orderings over the same cards, not different card types.
New series are a group-level design question, taken together rather than as
ad-hoc variants.

## Scheduling

- Each consumed card increments `global_counter` and the session's
  `session_card_count` exactly once. Opening, presenting and hints do not.
- `queue` is the source of truth. `queue[0]` is current; the pool is disjoint;
  a bird is active while it has non-V cards. Only chain order is constrained;
  cards of one bird may be adjacent.
- Active cap **7** (settings 5/7/10). Look-ahead target ~50 is soft; with 4–5
  card chains the queue is normally 28–35. Never start more than 7 birds just
  to fill the queue.
- Refill: due V cards (future), then next cards of active chains, then a new
  bird's L when below the cap.
- **Soft return** (near miss, assisted, revealed): move the card and its later
  chain 30–50 cards ahead; no failure escalation; `attempt` stays 1.
- **Hard fail:** first wrong moves the card (attempt 2) and later chain ahead.
  Second wrong falls back one card (`F→C`, `C→R`, `R→L`); the fallback starts
  at attempt 1 and the bird stays active.
- E always advances after its one-pass check; L advances.
- Passing F adds the bird to `passed` (`level: 1`, `due_at: counter + 20`) and
  frees the active slot.
- A session is `completed` when queue and pool are empty; it stays saved.
- `percent_completed` = share of the session's initial birds now passed,
  floored; 100 only when done.

## Sessions and passed birds

- Sessions are independent Worker documents with **no active one**. Each
  client selects a session locally per server/account
  (`~/.birds_trainer_state.json`, `BIRDS_TRAINER_STATE` overrides). Clients may
  select different sessions or share one.
- `default` always exists, has no filters, contains every eligible bird, and
  cannot be deleted or renamed; it is the fallback when a client has no
  selection or its selection disappeared. Other names are optional and unique.
- Handles resolve Worker-side: exact name → exact id → unique id prefix,
  case-insensitive. `--name` forces a name match.
- Create: filter → eligible set minus passed → shuffled with a stored seed →
  pool and initial queue; birds are drawn randomly, with no family blocks.
  Eligibility defaults to regular + introduced; `default` has no status filter.
- The session stores `created_from`, the Worker-formatted search and criteria
  (e.g. `search "acrocephalus-agricola" · status: accidental`), and the
  `active_cap` it was created with; the summary/view returns both. The browser
  shows the origin read-only, so CLI-only family/order/genus/status criteria
  are visible; `default` has none. The string is also the base for future
  custom series.
- Two sessions may learn the same not-yet-passed bird; only `passed` is
  globally excluded. Broadening scope means creating a new session; the old
  one remains.
- Before practising, `/prepare` drops newly passed birds from queue and pool.
  Resume re-shows `queue[0]`; reload prunes and refills.
- Rename changes or clears a name; the id, queue, progress and client
  selections do not change. Delete removes any non-`default` session; a client
  whose selection vanished falls back to `default`.
- Two clients on one session see each other's progress. A consumed card returns
  `409 stale_card`; a stale write returns `412`; the client reloads and
  continues.
- `passed` is profile-global, keyed by species and skill. It excludes birds
  from new and prepared sessions. There is no unpass command; until V exists,
  a passed bird simply retires from saved sessions.

## V reviews (future)

Design recorded for later; not implemented.

- Levels V1–V4; intervals after the previous review: 20, 60, 150, 400 cards.
  Pure card count, no time-based promotion. V4 pass sets `mastered` and clears
  `due_at`.
- Unaided first-try V pass advances; retry or hint-assisted pass repeats the
  level. First failure retries once after 30–50 cards.
- Second failure removes the bird from `passed`. In-scope: insert a fresh F
  chain and re-add on pass. Out-of-scope: hand the bird back to normal
  sessions without inserting a chain.
- Skip is allowed only on V: snooze 100 cards, keep level and passed status.
- Out-of-scope V cards are allowed by default, marked and skippable; a session
  setting can disable them.
- Claims: only a V card at the front at save time (`paused_review`) is
  persisted; other V cards are re-derived from the due pool. With no active
  session, the cross-session claim model is still open.

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
