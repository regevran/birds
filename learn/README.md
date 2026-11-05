# Learn — interactive bird-name trainer

This directory is the trainer project, parallel to `book/` and `data/`.
Implementation has not started. The design is in `REFERENCE.md`; the
implementation spec is in `IMPLEMENTATION.md`; follow-ups are in `TODO.md`.

## Layout

- `src/birdtrainer/` — Python package (implementation, not yet written).
- `src/web/` — browser UI (implementation, not yet written).
- `src/tests/` — unit, API and integration tests.
- `data/progress/` — user saved progress, git-committable.

There is no `learn/build` or `learn/out`: all build artifacts go to the
top-level disposable `build/`, and the trainer runs from `learn/src`.

## Status

No code yet. Do not start implementation until the first slice is approved.

## Running (when implemented)

```sh
cmake --build build --target run-learn
# or
cd learn/src && python3 -m birdtrainer
```

## Testing (when implemented)

```sh
cmake --build build --target test-learn
# or
cd learn/src && python3 -m unittest discover -v
```
