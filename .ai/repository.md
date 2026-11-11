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
    data/                 user progress
```

- `data/in` is the source of truth. The default data build is offline;
  network fetch/upgrade scripts are one-off tools.
- `data/out` is the committed consumer contract. Both `book/` and `learn/`
  read only from `data/out`.
- `build/` is disposable and holds all intermediate and final build artifacts.
- `book/out` is the installed book output; intermediates are in `build/book/`.
- `learn` has no `out`: it runs from `learn/src`; user data lives in
  `learn/data/progress`.
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
- The trainer card layer implements the pure L and E views plus a text
  renderer and text client. All 31 tests pass through `learn-test`.
- The text client supports `/<text>` search, `card L|E ...` and their
  `L`/`E` aliases, multi-word species names, `--seed`, `--reveal`, and
  readline history at `~/.birds_trainer_history`.
- The R/C/F/V cards, scheduling, lifecycle and web UI are still design-only.
