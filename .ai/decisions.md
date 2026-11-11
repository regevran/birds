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
- The foundation data layer and the pure L/E card views are implemented, with
  a text client (`python -m trainer`, CMake `learn-run`) and 31 passing tests.
  R/C/F/V, scheduling, lifecycle and the web UI are still design-only.
- The card layer is pure and session-independent. `CardDescriptor` identifies
  the species and card type only; the option seed is supplied by the caller of
  `card_view` and affects option order only. A Latin segment is called `latin`
  (`latin_forms` for several), not `surface`.
- The text client is a thin adapter over the same views; the web UI comes last.

## Deferred items

- Trainer R/C/F/V cards, queue/scheduler, lifecycle/persistence and web UI.
- Trainer hosting and the browser UI; global search.

