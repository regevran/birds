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
- `book/out` is the installed book output.
- `learn` has no `out`: it runs from `learn/src`; user data lives in
  `learn/data/progress`.

## Build

The top-level CMake files and `data/CMakeLists.txt` exist; the `book` and
`learn` per-project `CMakeLists.txt` files are still to be written.

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

## Status

The repository was restructured on 2026-11-05. The book and data code still
use pre-move paths, so the current build is expected to fail. The complete
move to-do list is in `book/REFERENCE.md` under “Repository move — TODO”.

The trainer is in design phase. No trainer code has been written; see
`learn/IMPLEMENTATION.md` before starting.
