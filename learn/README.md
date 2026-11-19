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
loader/validator with indexes. The card layer implements the pure L, E and R
card views, E/R answer grading and a text renderer, and `src/trainer/cli.py`
exposes them through an interactive text client. E and R are answerable: E
prompts for one option per element and reports a score; R asks for the Latin
name. The C, F and V cards, scheduling, lifecycle and the web UI are still
design-only. There are 96 passing tests.

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
card L acrocephalus-agricola
card E acrocephalus-agricola
card E acrocephalus-agricola --seed 1 --reveal
card R acrocephalus-agricola
card R acrocephalus-agricola --seed 1 --reveal
card R cormorant
card E cormorant --seed 1
help
quit
```

`card L`, `card E` and `card R` are the commands; `L`, `E` and `R` are
aliases, and C, F and V follow the same pattern. `/<text>` searches
species_id, Latin, English, Hebrew, family and order. Every word must match;
`list`, `find`, `birds` and `search` are aliases. The list shows species_id,
Latin, English, Hebrew, family and Hebrew family.

In the interactive client, a search opens `search>` mode. Type text there to
search again; `?` shows help. A bare `/` opens search mode without listing
every bird. `exit`, `quit`, Ctrl-D and Esc (press Esc, then Enter) go one
prompt up: from `search>` back to the card, from an E or R prompt or between
run cards back to `card>`, and from `card>` out of the client. Ctrl-C leaves
the client.

At an Elements prompt, enter an option number. Each row shows its theme, and
the options are drawn only from that theme, so the theme is a hint. `/text`
and the search aliases also work there and return to the same element with
earlier answers kept. Wrong answers reveal the correct glosses and continue;
correct rows repeat the correct gloss. E is not a gate. Each interactive
`card E` gets a fresh random option order; `--seed N` reproduces one. Up and
down arrows scroll the command history, kept in `~/.birds_trainer_history`.

At a Recognize prompt, choose the Latin name that matches the Hebrew name. A
wrong choice lets you try once more without revealing the answer; a second
wrong reveals the correct Latin. The shared Hebrew name accepts either
*Oenanthe* species, and both are shown in the feedback. Interactive R cards
also get a fresh random option order.

A card command also accepts a search query. `card R cormorant` runs R for
every matching bird in search order; one match behaves as a single card.
Press Enter between cards; `exit`, `quit`, Ctrl-D or Esc stops the run. R
runs skip birds without Hebrew and E runs skip birds without splits,
reporting the count. This is an ephemeral, one-pass study tool ("search with
benefits"), not saved progress. `--seed N` reproduces the run. `--answer`
needs a single match; one-shot display and `--reveal` print every matching
card.

A one-shot command also works:

```sh
cd learn/src && python3 -m trainer card L acrocephalus-agricola
cd learn/src && python3 -m trainer card E acrocephalus-agricola --answer "1 3 5 1"
cd learn/src && python3 -m trainer card R acrocephalus-agricola --answer "5"
```

One-shot commands are display-only unless `--answer` is given. The E answer
string has one option number per element; commas or spaces separate them. The
R answer is one option number.

## Testing

```sh
cmake --build build --target learn-test
# or
cd learn/src && python3 -m unittest discover -s tests -v
```
