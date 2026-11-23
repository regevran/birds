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
- The trainer is Worker-owned: the dataset, L/E/R/C/F views, grading, search
  and scheduler live in `learn/cloudflare/`. The Python text client is a thin
  Worker client with a text renderer and credential store. All 112 Python
  tests pass through `learn-test`; the three live Worker tests skip unless
  `BIRDS_TEST_*` is set.
- The text client supports `/<text>` search, `card L|E|R|C|F ...` and their
  aliases, multi-word species names, `--seed`, and readline history at
  `~/.birds_trainer_history`. Search matches names, taxonomy and the meanings
  of etymology parts; results explain the matched element and text, and list
  the matching element entries. Search, card views and grading go through the
  Worker; there is no local dataset or card layer. E, R, C and F are
  answerable: E prompts for one option per element and reports a score; R asks
  for the Latin name and retries once before revealing; C asks for a typed
  Latin name with a scaffold, showing a near miss and retrying a wrong answer
  once; F asks for the typed Latin name with no scaffold, with the same
  feedback. E/R cards pick a fresh random seed per card; `--seed N` reproduces
  one. E, R, C and F practise from a shell as well as inside the client; L
  only prints.
- A card command also accepts a search query. One match is a single card;
  several matches run in search order with Enter between cards and
  exit/quit/Ctrl-D/Esc stopping the run. The Worker's `/app/cards/run` filters
  eligible birds: R/C/F need Hebrew and E needs split elements, reporting the
  skipped count and reason. This is an ephemeral learner tool, not saved
  progress.
- A search opens a nested, read-only `search>` mode; `exit`, `quit`, Ctrl-D
  and Esc (Esc then Enter) go one prompt up, and from `card>` leave the
  client.
- Saved sessions are independent Worker documents with no active one; the
  protected `default` session contains every eligible bird and cannot be
  deleted or renamed. Each client remembers its own selected session per server
  and account in `~/.birds_trainer_state.json` (`BIRDS_TRAINER_STATE`
  overrides), falling back to `default`. `session new [X]` creates and selects
  without printing a card; `session open|status|run|delete` accept a name, id
  or id prefix, or `--name`. `run` calls `/prepare` so the Worker drops passed
  birds first. The Worker resolves handles case-insensitively. `session rename
  OLD [NEW]` changes or clears a name. `session list` marks the selected
  session with `*`. Two clients may practise the same session; a consumed card
  returns `409 stale_card` and the client reloads and continues. The CLI no
  longer has `session close` or `--start`.
- The Cloudflare Worker in `learn/cloudflare/` implements an authenticated,
  private R2 file store, login, the `/app` session API and the stateless
  card/search API. Its 90 Node tests run through `learn-worker-test`. The
  Worker is at `https://birds-progress.regevran.workers.dev`; the text client
  drives search, cards and saved sessions through it. The stateless routes
  still need a deployment to reach the live Worker. The browser client
  remains.
- The V card, hints and web UI are still design-only.
