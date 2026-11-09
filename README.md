# Birds of Israel

A shared data pipeline, an A5 pocket book, and an interactive trainer.

## Layout

```text
birds/
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
    src/                  book build code and render.sh
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

The top-level CMake files and `data/CMakeLists.txt` / `book/CMakeLists.txt`
exist; the `learn` per-project `CMakeLists.txt` is not present in this
checkout.

```sh
cmake --preset default
cmake --build build
cmake --build build --target data-build
cmake --build build --target data-install
cmake --build build --target data-test
cmake --build build --target book-build
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

## Status

The data pipeline and the A5 book use the post-move layout. `data-build`,
`data-install`, `data-test`, `book-build` and `book-install` work; the book
build writes to `build/book` and installs its print PDFs to `book/out`. The
`learn` per-project CMake file is not present in this checkout. See
`book/REFERENCE.md` for the book state.

The trainer foundation is implemented: `Config`, domain errors, the dataset
loader/validator with indexes, and 12 passing dataset tests. No server, cards,
queue or lifecycle code yet; see `learn/REFERENCE.md` and
`learn/IMPLEMENTATION.md`.
