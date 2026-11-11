# Birds of Israel

A shared data pipeline, an A5 pocket book, and an interactive trainer.

## Layout

```text
birds/
  .ai/                    durable AI/project context
  CMakeLists.txt          top-level build entry point
  CMakePresets.json       Ninja presets
  build/                  disposable build tree (ignored)
  data/
    src/                  pipeline scripts
      pipeline/           default build steps
      oneoff/             manual fetch/upgrade/maintenance
    in/                   sources and frozen snapshots
    out/                  installed final data (committed)
  book/
    src/                  book build code
    data/                 text.md, assets, reports
    out/                  installed PDFs (ignored)
  learn/
    src/                  trainer code and web assets
    data/                 user progress
```

- `data/in` is the source of truth. The default data build is offline; network
  fetch/upgrade scripts are one-off tools.
- `data/out` is the committed consumer contract. Both `book` and `learn` read
  only from `data/out`.
- `build/` is disposable and holds all intermediate and final build artifacts
  for data, book and learn.
- `book/out` is the installed book output; intermediate build files are in
  `build/book`.
- `learn` has no `out`: it runs from `learn/src`; user data lives in
  `learn/data/progress`.

## Build

The top-level CMake files and the `data/CMakeLists.txt`,
`book/CMakeLists.txt` and `learn/CMakeLists.txt` per-project files are in
place.

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

Data workflow — configure, build, test, install in one command:

```sh
cmake --workflow --preset data
```

Book workflow — configure, build, install in one command:

```sh
cmake --workflow --preset book
```

After configuring, print the command list with:

```sh
cmake --build --preset help
```

CMake reserves `help` as a built-in target name; the preset gives the same
short command without a custom target.

## Status

The data pipeline and the A5 book use the post-move layout. `data-build`,
`data-install`, `data-test`, `book-build`, `book-one-file` and `book-install` work; the book
build writes to `build/book` and installs its print PDFs to `book/out`. The
`learn` CMake targets work too. See
`.ai/book-reference.md` for the book state.

The trainer foundation is implemented: `Config`, domain errors, the dataset
loader/validator with indexes. The card layer has pure L and E views and a
text client, with 31 passing tests. The R, C, F and V cards, scheduling,
lifecycle and the web UI are still design-only; see `.ai/learn-reference.md`
and `.ai/learn-implementation.md`.
