# Learn — interactive bird-name trainer

This directory is the trainer project, parallel to `book/` and `data/`.
The package skeleton and the foundation `Config` exist; the rest is not
implemented. The design is in `REFERENCE.md`; the implementation spec is in
`IMPLEMENTATION.md`; follow-ups are in `TODO.md`.

## Layout

- `src/trainer/` — Python package:
  - `foundation/` — config, errors, models, dataset, normalization.
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

Foundation skeleton only: `trainer/` package markers and `foundation/config.py`.
No server, dataset loader, cards, queue or lifecycle code yet. The next slice
is the dataset loader/validator.

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
cd learn/src && python3 -m unittest discover -v
```
