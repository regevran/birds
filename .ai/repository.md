# Repository

## Layout

```text
birds/
  .ai/                 current context (start at README.md)
  TODO.md              actionable work
  CMakeLists.txt       build entry point
  CMakePresets.json    Ninja presets and workflows
  build/               disposable artifacts
  data/src, in, out    pipeline, sources, committed contract
  book/src, data, out  builders, text/assets, PDFs (ignored)
  learn/
    src/trainer/       Python CLI: foundation/, cards/, cli.py
    src/tests/         Python tests
    cloudflare/        Worker: core, /app, trainer modules, Node tests
    design/            browser UI mocks
    web/               browser client: index.html, src, assets
    tools/             provisioning, dev token, illustrations, dev server
    USER-MANUAL.md     user-facing manual
```

- `data/out` is the committed consumer contract; `book/` and `learn/` read only
  it. `build/` is disposable. `learn/` has no out directory.
- Progress lives in private R2 behind the Worker; there is no local store.
- The browser client runs from `build/web` on `http://localhost:8001` against
  the local Worker; the token is in `localStorage['birds.token']`.
- `learn-web-serve` uses `learn/tools/serve_web.py` and sends
  `Cache-Control: no-store`.

## Data contract

- `data/out/israel_birds_final.json` — 565 species: `latin`, `genus`,
  `epithet`, `english`, `family`, `family_order`, `family_he`, `order`,
  `status`, `hebrew`, `flags`.
- `data/out/etymology.json` — `elements`, `splits`, `whole_names`, `themes`.
- The pipeline validates coverage and reassembly before installing.

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
cmake --build build --target learn-worker-test
cmake --build build --target learn-run
cmake --build build --target learn-web-build
cmake --build build --target learn-web-illustrations
cmake --build build --target learn-web-illustrations-upload-local
cmake --build build --target learn-web-illustrations-upload-remote
cmake --build build --target learn-web-token
cmake --build build --target learn-web-serve
cmake --build build --target learn-worker-users-upload
cmake --build build --target learn-worker-users-deploy
```

Workflows: `cmake --workflow --preset data|book`; help:
`cmake --build --preset help`. CMake is the only build interface.

## Status (2026-11-26)

- **Book:** builds and installs; specification in `book-reference.md`.
- **Worker:** implemented locally; 105 Node tests. The deployed Worker
  predates the v2 `users.json` and must be redeployed before the v2 accounts
  file is uploaded.
- **Python CLI:** 117 tests (3 live Worker tests skip unless configured).
- **Browser:** shell, L card, search results/panel, fixed-centre look-ahead,
  history/redo and thin E/R/C/F forms. Pending: card-face design, session
  drawer and create flows, settings, reader.
- **Illustrations:** 565/565 generated and uploaded to local and remote R2.
  The public media route is in the new Worker, so remote serving waits for the
  deployment.
- Work: `TODO.md`.
