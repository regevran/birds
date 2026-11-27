# Trainer design

The Worker owns the dataset, card views, grading, search and scheduling.
Python and browser clients render JSON. This file is the current model;
endpoints are in `learn/WORKER-API.md`, storage in `learn-cloudflare.md`, UI in
`learn-ui.md`.

## Purpose

Hebrew → Latin for the book's 565 species. Latin, English and Hebrew names plus
the etymology of Latin names. No timer; progress is saved and resumed.

## Vocabulary

- **Profile** — a person; settings and the global counter.
- **Session** — a saved timeline with its own filter.
- **Pending** — ordered per-bird groups of cards not yet queued.
- **Active chain** — the queued cards of one bird.
- **Queue** — materialised unseen cards; `queue[0]` is the frontier.
- **History** — completed cards in timeline order.
- **Global counter** — one per consumed card (or wrong redo).

## Cards

| Card | Name | User action |
|---|---|---|
| **L** | Learn | Display only: family/order, names, parts, meanings, bridge, picture. Next. |
| **E** | Elements | One Hebrew gloss per element; the theme is a hint; not a gate. |
| **R** | Recognize | Choose the Latin from 4–5 closely related names. |
| **C** | Construct | Type the Latin with a one-line scaffold. |
| **F** | Produce | Type the Latin unaided. |

- Chain: with parts L→E→R→C→F; without L→R→C→F. F completes the bird.
- R distractors come from the same genus, then family, then order, then any;
  accepted answers are excluded. Shared-Hebrew species are both accepted.
- E options are deduplicated by gloss; any element with the chosen gloss is
  accepted.
- Wrong R/C/F: one retry, then reveal. Near miss: reveal and soft return.
- The browser L face omits the CLI bridge; the parts carry the glosses.

### Latin grading

NFC, trim, collapse whitespace, casefold. A near miss has the same word count,
matching first letters and a total Damerau-Levenshtein distance ≤ 2. Feedback
shows per-word marks. Hebrew/English grading is later.

## Scheduling

- A consumed card increments `global_counter` and moves from `queue[0]` to
  history. Presenting and hints do not.
- `queue` is the future; `pending` is disjoint; a bird is active while queued.
- Active cap 7 (settings 5/7/10). Refill pulls whole pending groups and
  interleaves them while fewer than the cap are active.
- Soft return moves the card and its later chain 30–50 cards ahead.
- First wrong moves the card (attempt 2) and later chain ahead. Second wrong
  falls back one card (F→C→R→L) at attempt 1; the bird stays active.
- E and L always advance.
- A session is complete when queue and pending are empty; it stays saved.
- `percent_completed` is the share of the session's initial birds with no
  pending or queued cards, floored.

## Sessions, history and redo

- Sessions are independent Worker documents; no active session. Each client
  selects one locally per server and account.
- `default` has no filters, contains every eligible bird, is protected and is
  the fallback.
- Names are optional and unique; handles resolve exact name → exact id →
  unique id prefix, case-insensitive.
- Create: filter → Hebrew-eligible birds → one pending group per bird,
  shuffled with a stored seed → initial queue. Regular + introduced by
  default; accidental and historical are opt-in.
- `created_from` is the Worker-formatted search/criteria at creation, read-only;
  `default` has none.
- Schema v2 only; no migration.
- Rename changes the name only. Delete removes any non-`default`; a vanished
  selection falls back to `default`.
- Two clients on one session see each other's progress. Answer uid
  classification: frontier live, history redo, unseen non-frontier `409
  not_current`, unknown `409 stale_card`; a stale write is `412`.
- History is served in windows; the client holds the browsing cursor.
- Correct/advance redo records only. Wrong redo truncates after the card,
  pours invalidated cards back into their pending groups and re-applies the
  failure retry; everything after is unseen. Redo grading is a final attempt
  (≥ 2).

## Data facts

- 565 species, 84 families, 249 genera, 26 orders.
- 560 with Hebrew (559 unique); 5 without; one shared Hebrew name.
- 13 families lack `family_he`.
- Statuses: 381 regular, 167 `A`, 11 `I`, 2 `Ex`, 3 `Ex/A`, 1 `X`.
- Etymology: 95 species fully split, 232 partially, 238 none; 308 elements,
  312 split words, 16 whole names.
- Default scope: regular + introduced. H→L requires Hebrew, so the 5
  no-Hebrew species are excluded. Family and status are context, never
  quizzed; only split words get an E card.

## Series

Cards are independent. A series supplies membership, ordering, persistence,
progression and completion. Sessions and card runs are the two instances.
The chain is the session's order; other orders (R→C, R→E) are future series,
not different card types. Card runs are ephemeral.

## Deferred

Passing/mastery and V reviews were removed in November 2026; replay a bird in
a new session. Hints are future.
