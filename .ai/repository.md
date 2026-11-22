# Repository context

## Tree

```text
birds/
  .ai/                    AI context and design records
  CMakeLists.txt          top-level build entry point
  CMakePresets.json       Ninja presets and workflows
  build/                  disposable build tree (ignored)
  data/
    src/
      pipeline/           default offline build steps
      oneoff/             manual fetch/upgrade/maintenance scripts
    in/                   sources and frozen snapshots
    out/                  installed final data (committed)
  book/
    src/                  book build code
    data/                 text, assets, reports
    out/                  installed PDFs (ignored)
  learn/
    src/                  trainer code
    cloudflare/           progress Worker and its Node tests
    tools/                provisioning and maintenance scripts
    data/                 local placeholders and development data
```

- `data/in` is the source of truth. The default data build is offline;
  network fetch/upgrade scripts are one-off tools.
- `data/out` is the committed consumer contract. Both `book/` and `learn/`
  read only from `data/out`.
- `build/` is disposable and holds all intermediate and final build artifacts.
- `book/out` is the installed book output; intermediates are in `build/book/`.
- `learn` has no `out`: it runs from `learn/src`. Progress lives in private
  Cloudflare R2 behind the Worker in `learn/cloudflare/`; there is no local
  progress store.
- `.ai/` holds the durable AI/project context described in `.ai/README.md`.

## Data contract

- `data/out/israel_birds_final.json` — 565 species. Fields include `latin`,
  `genus`, `epithet`, `english`, `family`, `family_order`, `family_he`,
  `order`, `status`, `hebrew` and `flags`.
- `data/out/etymology.json` — `elements`, `splits`, `whole_names`, `themes`.
- `family_order` is one integer per family, 1..84 by first appearance in the
  source checklist. The book sorts families by it.
- The data pipeline validates coverage and reassembly before installing.

## Build

```sh
cmake --preset default
cmake --build build
cmake --build build --target data-build
cmake --build build --target data-install
cmake --build build --target data-test
cmake --build build --target book-build
cmake --build build --target book-one-file
cmake --build build --target book-install
cmake --build build --target learn-test
cmake --build build --target learn-run
```

Workflows:

```sh
cmake --workflow --preset data
cmake --workflow --preset book
```

After configuring, print the command list with:

```sh
cmake --build --preset help
```

CMake reserves `help` as a built-in target name; the preset gives the same
short command without a custom target.

## Current state

- `data-build`, `data-install`, `data-test`, `book-build`, `book-one-file` and
  `book-install` work. The book is a 96-page A5 third edition; the combined
  one-file PDF is 98 A5 pages.
- The trainer foundation is implemented: `Config`, domain errors, the dataset
  loader/validator with indexes.
- The trainer card layer implements the pure L, E, R, C and F views, E/R/C/F
  answer grading and a text renderer, plus a text client and the Cloudflare
  `CloudFiles` client. All 191 Python tests pass through `learn-test`; the two
  live Worker tests skip unless `BIRDS_TEST_*` is set.
- The text client supports `/<text>` search, `card L|E|R|C|F ...` and their
  `L`/`E`/`R`/`C`/`F` aliases, multi-word species names, `--seed`, `--reveal`,
  and readline history at `~/.birds_trainer_history`. E, R, C and F are
  answerable: E prompts for one option per element and reports a score; R asks
  for the Latin name and retries once before revealing; C asks for a typed
  Latin name with a scaffold, showing a near miss and retrying a wrong answer
  once; F asks for the typed Latin name with no scaffold, with the same
  feedback. `--answer` grades a one-shot E, R, C or F card. Interactive E/R
  cards pick a fresh random seed per card; `--seed N` reproduces one, and
  one-shot commands stay at seed 0.
- A card command also accepts a search query. One match is a single card;
  several matches run in search order with Enter between cards and
  exit/quit/Ctrl-D/Esc stopping the run. R/C/F runs skip birds without Hebrew
  and E runs skip birds without split elements, reporting the count. This is
  an ephemeral learner tool, not saved progress.
- A search opens a nested, read-only `search>` mode; `exit`, `quit`, Ctrl-D
  and Esc (Esc then Enter) go one prompt up, and from `card>` leave the
  client.
- The Cloudflare Worker in `learn/cloudflare/` implements an authenticated,
  private R2 file store and login. Its 22 Node tests run through
  `learn-worker-test`. It is deployed at
  `https://birds-progress.regevran.workers.dev`; the Python remote client, CLI
  login, the scheduler and the browser client are still to come.
- The V card, hints, scheduling, lifecycle and web UI are still design-only.
