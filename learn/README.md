# Learn — interactive bird-name trainer

This directory is the trainer project, parallel to `book/` and `data/`.
The foundation data layer and the pure L/E card views exist, with a text
client for inspecting them; the rest is not implemented. The design is in
`../.ai/learn-reference.md`; the implementation spec is in
`../.ai/learn-implementation.md`; follow-ups are in `../.ai/learn-todo.md`.

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
loader/validator with indexes. The card layer implements the pure L and E
card views and a text renderer, and `src/trainer/cli.py` exposes them through
a small text client. The R, C, F and V cards, scheduling, lifecycle and the
web UI are still design-only. There are 31 passing tests.

## Running the text client

```sh
cmake --build build --target learn-run
# or
cd learn/src && python3 -m trainer
```

Inside the client:

```text
/paddyfield
/acro
card L paddyfield warbler
card E acrocephalus-agricola --seed 1 --reveal
help
quit
```

`card L` and `card E` are the commands; `L` and `E` are aliases, and R, C, F
and V follow the same pattern. `/<text>` searches species_id, Latin, English,
Hebrew, family and order. Every word must match; `/` with no text lists all
birds. The list shows species_id, Latin, English, Hebrew, family and Hebrew
family. `list` and `find` are aliases for the same search. Up and down arrows
scroll the command history; it is kept in `~/.birds_trainer_history`.

A one-shot command also works:

```sh
cd learn/src && python3 -m trainer card L acrocephalus-agricola
```

## Testing

```sh
cmake --build build --target learn-test
# or
cd learn/src && python3 -m unittest discover -s tests -v
```
