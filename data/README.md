# Data

Shared data project for the book and the trainer.

## Layout

- `src/pipeline/` — default build steps. The intended pipeline is offline and
  starts from `in/`. `src/pipeline/data_paths.py` is the single path table
  used by those steps.
- `src/oneoff/` — manual fetch, upgrade, migration and inspection scripts.
  `src/oneoff/superseded/` holds historical modules kept only for reference.
- `in/` — sources and frozen snapshots:
  - `etymology.md` — authoritative etymology source.
  - `raw/` — Wikipedia source pages.
  - `jobling/` — Jobling dictionary OCR.
  - `hebrew_names.json`, `hebrew_wikidata.json`, `family_hebrew.json` —
    frozen network snapshots.
  - `conversation.txt` — original project conversation dump (provenance).
  - `overrides/` — candidate corrections, not yet wired into the build.
- `out/` — installed final data, committed. Both `book/` and `learn/` are
  intended to read only from here once their paths are updated.

Build intermediates and final build artifacts go to the top-level disposable
`build/data/`; they are not committed.

## Status

The default pipeline scripts use `src/pipeline/data_paths.py` and the new
layout. The one-off scripts still use the old `data/...` paths and assume the
repository root as their working directory; they are not part of the default
build. `data/CMakeLists.txt` is written and defines `data-build`,
`data-install`, and `data-test`. The `data` workflow runs configure,
`data-build`, `data-test`, then `data-install`:

```sh
cmake --workflow --preset data
```

The final JSON includes `family_order`; the book still uses the
merged order source until its TODO is implemented. See the
“Repository move — TODO” section in `book/REFERENCE.md` for the remaining
items.
