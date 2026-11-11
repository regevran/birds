# Learn — interactive bird-name trainer

This directory is the trainer project, parallel to `book/` and `data/`.
The package skeleton and the foundation `Config` exist; the rest is not
implemented. The design is in `REFERENCE.md`; the implementation spec is in
`IMPLEMENTATION.md`; follow-ups are in `TODO.md`.

## Layout

- `src/trainer/` — Python package:
  - `foundation/` — config, errors, dataset, normalization.
  - `cards/` — card rules, options, grading, card views, bridge.
  - `scheduling/` — queue and scheduler.
  - `lifecycle/` — store, events, profiles, sessions.
  - `api.py`, `static.py`, `__main__.py` at the package root.
- `src/web/` — browser UI (implementation, not yet written).
- `src/tests/` — unit, API and integration tests.
- `data/progress/` — user saved progress, git-committable.

There is no `learn/build` or `learn/out`: all build artifacts go to the
top-level disposable `build/`, and the trainer runs from `learn/src`.

## Status

Foundation data layer is in place: `Config`, domain errors, the dataset
loader/validator with indexes, and 12 passing dataset tests. No server, cards,
queue or lifecycle code yet. Card model structure is deferred until after the
dataset layer is reviewed.

## Running (when implemented)

```sh
cmake --build build --target learn-run
# or
cd learn/src && python3 -m trainer
```

## Testing (when implemented)

```sh
cmake --build build --target learn-test
# or
cd learn/src && python3 -m unittest discover -s tests -v
```
