# Learning tool — design reference

Status: design phase. No code has been written. This file is the durable record of the design conversation; use it to continue next session. `learn/TODO.md` holds follow-ups.

## Purpose

An offline browser trainer for the same dataset as the book: Latin, English and Hebrew bird names, plus the etymology elements of the Latin names. Primary v1 skill is **Hebrew → Latin**; English directions are later (v2/v3). There is no session timer: the user practices as long as they want, stops whenever, and resumes the saved card queue later. History is collected now and analysed later.

Multiple local profiles ("this is me practising"). No sync. Everything local, in the repository.

## Source data

Read-only inputs:

- `data/out/israel_birds_final.json` — 565 species; fields `latin`, `genus`, `epithet`, `english`, `family`, `family_order`, `family_he`, `order`, `status`, `hebrew`, `flags`.
- `data/out/etymology.json` — `elements`, `splits`, `whole_names`, `themes`.
- `book/` and `data/` are never mutated by the trainer. The trainer derives its own quiz dataset with validation.

Data facts that shape the design:

- 565 species, 84 families, 249 genera, 26 orders.
- 560 unique Hebrew names; 5 species have no Hebrew; one Hebrew name (`סלעית לבנת-כנף`) is shared by *Oenanthe lugens* and *O. warriae*.
- 29 families have no `family_he` (`no-family-hebrew`, `family-hebrew-unverified`).
- Statuses: 381 unmarked (regular), 167 `A`, 11 `I`, 2 `Ex`, 3 `Ex/A`, 1 `X`.
- Etymology: 95 species fully split, 232 partially split, 238 with no split. 113 of 249 genera have a split.
- 308 elements, 312 split words, 15 whole names. 195 elements occur in only one word; the top 20 cover 31.5% of element occurrences.
- No niqqud in the Hebrew names. 124 Hebrew names use ASCII `-` rather than maqaf. 155 English names contain hyphens, 42 apostrophes, 2 diacritics (`Rüppell`).

Defaults:

- Practice scope: regular + introduced; accidental (`A`) and historical (`Ex`/`X`) are opt-in.
- H→L requires a Hebrew name: the 5 no-Hebrew species are excluded from the H→L pool.
- Family is context, never a quiz source. Family Hebrew is not quizzed.
- Only words with a source split are asked in the E card. No-split species get no E card.

## Core vocabulary

- **Profile** — a person. Holds settings, the shared `passed` table, the global card counter, and the event log.
- **Session** — a saved, named practice queue with its own filter, pool, active chains and card counter. Independent from other sessions except for the shared `passed` table and reviews. One active session at a time.
- **Pool (the set)** — the session's filtered birds minus birds already in `passed`, shuffled. Birds not yet started.
- **Active chain** — the remaining card sequence for one bird currently being learned: `L → E → R → C → F` (or `L → R → C → F`). Per-bird, ordered; not a separate stream for the user.
- **Queue** — the single ordered list of concrete cards to present next: the interleaving of all active chains plus due V cards. The user sees the front. Target lookahead ~50 cards; it may grow to place a failed card 30–50 cards ahead.
- **Passed table** — profile-global list of birds that passed F, with V level and `due_at` global card count. Passed birds are excluded from new and reloaded sessions.
- **Global counter** — every consumed card in any session, including L, E and skips.
- **V level** — review interval level 1–4. V1–V4 are the same kind of review at different card distances.

```text
POOL / SET                         ACTIVE (max 7)                  QUEUE (~50 cards)
[bird8] [bird9] [bird10] ...  ──pull──>  A: L✓ E R C F  ──interleave──>  [B/R] [V1] [A/E] [C/R] [A/R] ...
                                         B: L✓ R C F
                                         C: L✓ E✓ R C F
```

## Card types and per-bird flow

With etymology parts: **L → E → R → C → F**.
Without parts: **L → R → C → F**.
Later, when due: **V** (review).

| Card | Name | What the user does |
|---|---|---|
| **L** | Learn | Display only: family/order, Hebrew, English, Latin, all parts and meanings, bridge line. One button: next. No "show again", no "I know this". |
| **E** | Elements | All parts on one card; choose each part's Hebrew meaning from options. Wrong answers reveal the correct pairs and continue. Not a gate. |
| **R** | Recognize | Hebrew prompt → choose the Latin from 4–5 options. No English, no family. Options shuffled each time. |
| **C** | Construct | Hebrew prompt → type the Latin. Scaffold: part meanings + first letters (or first letters/length when there are no parts). |
| **F** | Produce | Hebrew prompt → type the Latin. No scaffold; hint ladder on request. |
| **V** | Review | Same as F, presented when due. V cards are the only cards that can be skipped. |

Notes:

- **Passing F** = unaided correct. A hint-assisted correct is recorded as assisted and does not advance; the card returns later.
- A known bird still goes through the chain once, then enters the V table. There is no skip on L or F.
- Genus and epithet are scored separately for partial credit and diagnosis.
- Distractors should be plausible: same genus/family for names; same theme/meaning group for elements. Never a fixed option position.
- The L card's "bridge" line (e.g. Hebrew word ↔ Latin element) is a display aid, computed where possible; omit it when there is no match.
- No personal notes field.

## Passing F and the passed table

- Unaided correct on F → remove the bird from its session's active set, add it to the profile-global `passed` table, schedule V1 at `global_counter + 20`, free the active slot, and pull the next bird from the session pool.
- Assisted correct → no pass; retry the same card.
- If F fails, fall back one card (C → R → L) and keep the bird active.

## Queue mechanics

- The session keeps a target lookahead of ~50 cards; it is edited dynamically.
- The only hard ordering constraint is that a bird's remaining cards stay in chain order. There is no anti-adjacency rule; B3 → B4 adjacent is allowed.
- Refill when the lookahead falls short, in this priority: due V cards, next cards of active chains, then a new bird's L card if active < 7.
- **Failure move:** take the failed card and the rest of its chain out, move the failed card 30–50 cards ahead, then reinsert the remaining chain cards after it in order with random gaps.
- **Repeat once:** a failed card is retried once in the session. A second failure falls back one card.
- Active-chain cap: **7** (setting 5/7/10). Counts birds in L→F, including in-scope V-failure exception chains. V cards themselves do not count.
- Pool and queue are per session; passed birds and V reviews are profile-global.
- If the pool is exhausted and no active chains remain, the queue is V cards only; when those are done, return to the main selection screen. The completed session stays saved.

## V reviews (profile-global)

- `passed`: bird → V level 1–4, `due_at` global card count, last result.
- Intervals: V1 = 20 cards after F; V2 = 60 after V1; V3 = 150 after V2; V4 = 400 after V3. After V4, the bird is mastered.
- Pure card count: timestamps are recorded but do not affect scheduling; a long break does not promote overdue cards. A session resumes exactly.
- Unaided first-try V pass advances the level. A retry pass or hint-assisted pass does not advance; schedule the same level again.
- **V failure:** first failure → retry the same V once after 30–50 cards. Second failure:
  - **In-scope** (bird matches the session filter): remove from `passed`; re-enter at F in the current session. If F passes, the bird returns to `passed` with a fresh V1.
  - **Out-of-scope** (bird was injected into a focused session): remove from `passed`; do **not** insert an F chain into the focused session. The bird is handed back: a normal session whose filter includes it can pick it up. Existing saved sessions do not retroactively add it; the user picks it up manually.
- **Skip:** V cards only. Non-failure; V level and passed status unchanged; snooze 100 cards; the skip consumes a card and advances the global counter.
- **Out-of-scope V cards:** allowed by default, visually marked, skippable. A per-session toggle can turn them off. The main screen shows a global due-reviews count.
- V cards are claimed by the active session so the same review is not duplicated across saved sessions; unshown V cards return to the shared due pool on save/switch.

## Sessions and profiles

- Sessions are independent: each has its own filter, pool, active chains, queue and learning progress.
- Shared across sessions: the `passed` table, the global card counter, and V reviews.
- In-progress overlap is allowed: two saved sessions may be learning the same not-yet-passed bird. Only passed birds are excluded.
- New session: choose a filter → pool = filtered set minus passed, shuffled → name (auto from start time, editable) → start. New birds are drawn randomly from the pool; no family blocks.
- Resume: load the saved queue exactly; if closed mid-card, re-show the same card.
- Reload: drop birds that are now passed from the queue, active chains and pool; refill.
- Broadening scope = create a new session; the old one remains.
- Queue empty → main selection screen.

## Persistence

Chosen approach: **A — local server**.

- A small local server (Python stdlib) serves the static UI and reads/writes progress files in the repository. Offline; `./start.sh` or `python3 app.py`; git-committable progress. The app itself is browser-based.
- Profile data: `learn/data/progress/<profile>/profile.json` (name, settings, passed table, global counter) and `events.jsonl`.
- Session data: `learn/data/progress/<profile>/sessions/<session-id>.json` (name, filter, seed, pool, active chains, queue, card counter).
- Data version hash stored with the session; card content is regenerated from item IDs.
- V cards are not persisted as part of a session queue; they are injected from the shared due pool and claimed by the active session. This prevents the same review appearing in two saved sessions.
- Event log: timestamp, profile, session, card type, bird/item, stage, prompt, response, expected, result (`correct` / `near_miss` / `wrong` / `assisted` / `revealed` / `skipped`), hint level, options shown, latency, queue position, global counter. Snapshot analysis fields (family, genus, order, status, has-elements, themes) on the event, or rely on the data version.
- No dashboards or progress views yet; collect raw events now.

## UI

- Hebrew book-style interface; English names and element glosses shown as in the book. Hebrew labels with English names/values.
- Main screen: profile → saved sessions + "new session"; global due-reviews count; rename/delete.
- Session screen: current card; a collapsible look-ahead of the next **5** cards showing **Hebrew name + card type**, never the Latin; user can stop at any time.
- L: next only.
- E: check; wrong answers reveal and continue; next.
- R: options; feedback.
- C: scaffold visible; typed answer.
- F: typed answer; hints on request (ladder: length/first letter → 4–5 options → reveal).
- V: typed answer; skip button.
- No timer. No idle detection. Record open/close and card events; later analysis can infer gaps.

## Data edge cases and grading

- 5 no-Hebrew species: excluded from H→L.
- Shared Hebrew name (`סלעית לבנת-כנף`): accept either *Oenanthe* species as correct; show both in feedback.
- 29 families without Hebrew: never shown as a Hebrew family; family context optional.
- 238 species with no etymology: no E card.
- Partial etymology: E asks only about the split words.
- Hebrew grading: normalize ASCII hyphen / maqaf / space, geresh/gershayim; no niqqud in the source.
- English grading (later): case-insensitive, hyphens/apostrophes/spaces normalized.
- Latin grading: case-insensitive, trim; genus and epithet scored separately; distinguish near-miss from wrong.
- Status markers (`A`, `I`, `Ex`, `X`) are context, not v1 quiz targets.
- English directions, whole-name deck, and element free-typing are later.

## Decisions locked

- Offline browser app with local server and file-based progress (option A).
- Hebrew book-style UI; English names shown; English quizzing later.
- No session timer; pure card-count scheduling; global counter across sessions.
- L is display-only with only "next"; E is a reveal-and-continue element check; R/C/F as described.
- Pass F = unaided correct; passed birds are profile-global and excluded from new/reloaded sessions.
- Session learning is independent; passed birds and V reviews are shared.
- Active-chain cap 7; random bird draw from the filtered, shuffled pool; no family blocks.
- Queue lookahead ~50; failure moves 30–50 cards; repeat once; fall back one card on second failure.
- V levels 20/60/150/400; no time-based promotion; V skip snoozes 100 cards.
- Out-of-scope V cards on by default with skip; global due count.
- Look-ahead 5 cards, Hebrew name + card type, no Latin.
- Collect events now; analyse later.
- No code until the spec is agreed; implement in small user-reviewed slices.

## Open / later

- Write the one-page implementation spec (file structures, exact state transitions, screen flow).
- Out-of-scope V hand-back UX: a future "needs relearning" badge; today the bird is simply no longer passed and is available to normal sessions.
- Optional dedicated "Review due" run/session.
- Global search (future): `/` from anywhere opens a grouped search screen
  (families, completed birds, elements, cards); results open read-only card
  previews; previews do not advance the queue or the global counter. Requires
  dataset search indexes and pure, session-independent card views from the
  start. No family/genus pages are planned.
- English directions (v2/v3), whole-name deck, element free-typing.
- Typo tolerance and near-miss presentation.
- Images/audio, cross-device sync, session export/import.
- Ringer keys (`learn/TODO.md`).

## Working agreement

- Work closely with the user; no large autonomous implementation.
- Propose the plan/diff for each small slice and wait for review.
- Do not change `data/` or `book/` without explicit approval.
- Do not commit unless asked.
