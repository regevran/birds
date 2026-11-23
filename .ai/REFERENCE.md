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
- `learn` has no `out`: it runs from `learn/src`. User progress lives in
  private Cloudflare R2 through the Worker in `learn/cloudflare/`; there is no
  local progress store.

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

The trainer is Worker-owned: the dataset, L/E/R/C/F views, grading, search and
scheduler live in `learn/cloudflare/`. The Python text client is a thin Worker
client with a text renderer and credential store, with 112 passing Python tests
(three live Worker tests skip unless configured). The text client supports
search, answerable E, R, C and F cards, multi-match card runs, nested search
mode and one-prompt-up navigation. The Cloudflare Worker implements an
authenticated, private R2 file store, login, the `/app` session API and the
stateless card/search API, with 90 passing Node tests. It is at
`https://birds-progress.regevran.workers.dev`; the stateless routes still need
a deployment. Python `CloudFiles`/`CloudApp` and CLI
`login`/`logout`/`whoami` are implemented. Search and cards go through the
Worker; `--answer`, `--reveal` and the local card/dataset layer are gone.
Saved sessions are driven through
`session new|list|open|status|run|rename|delete`. Sessions are independent
Worker documents with no active one; each client locally selects the session
it works on, and a protected `default` session always exists.
The V card, hints and the web UI are still to come; see
`.ai/learn-reference.md`, `.ai/learn-implementation.md` and
`.ai/learn-cloudflare.md`.
