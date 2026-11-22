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

- The trainer is an offline browser trainer for the same dataset: Latin,
  English and Hebrew names plus etymology elements. The primary v1 skill is
  **Hebrew → Latin**; English directions are later.
- There is no session timer. The user practises as long as wanted, stops at any
  time, and resumes the saved card queue. History is collected now and analysed
  later. Everything is local; multiple local profiles; no sync.
- Card chain with parts: `L → E → R → C → F`; without parts:
  `L → R → C → F`. `V` appears when due. L is display-only; E is a separate
  element-check card. This superseded the earlier idea of putting the
  parts-matching exercise on L.
- The foundation data layer and the pure L/E/R/C/F card views are implemented,
  with a text client (`python -m trainer`, CMake `learn-run`) and 167 passing
  tests. E, R, C and F are answerable: E collects one gloss choice per element
  and grades them with the pure `cards/grading.py` layer; R grades a Latin-name
  choice; C and F grade a typed Latin name. An E row shows its theme and draws
  every option from that same theme, so the theme is a deliberate hint. R draws
  distractors by taxonomic proximity (genus, family, order, any) and accepts
  every species that shares the prompt's Hebrew name. V, the hint ladder,
  scheduling, lifecycle and the web UI are still design-only.
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
  learner-driven "search with benefits" tool, not saved progress or the
  planned scheduling/skills system: one pass, no repetition, no logging.
  R/C/F runs skip birds without Hebrew, E runs skip birds without split
  elements, and the count is reported. `--answer` requires a
  single match; one-shot display and `--reveal` batch-print all cards.
- The card layer is pure and session-independent. `CardDescriptor` identifies
  the species and card type only; the option seed is supplied by the caller of
  `card_view` and affects E/R option order only. A Latin segment is called
  `latin` (`latin_forms` for several), not `surface`.
- The card layer is deterministic given a seed. The interactive client supplies
  a fresh random seed per E or R card unless `--seed N` is given; one-shot
  commands and `--answer` use seed 0 so the output and answer numbers are
  reproducible.
- The text client is a thin adapter over the same views; the web UI comes last.
  Its commands are `card L|E|R|C ...` with `L`/`E`/`R`/`C` aliases, `/<text>`
  for bird search, multi-word Latin/English species names, and `--answer` for
  a one-shot graded E, R or C card. Readline history is persisted in
  `~/.birds_trainer_history`.
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
- Progress is not persisted yet. Gate 2 adds the profile/session store so the
  text and browser clients can resume the same saved queue.

## Deferred items

- Trainer V card, the hint ladder, queue/scheduler, lifecycle/persistence
  and web UI.
- Trainer hosting and the browser UI; global search.

