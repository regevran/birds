# Learn — interactive bird-name trainer

This directory is the trainer project, parallel to `book/` and `data/`.
The foundation data layer, the card layer and the text client exist. Progress
is stored in private Cloudflare R2 through the Worker in `cloudflare/`. The
design is in `../.ai/learn-reference.md`; the storage design is in
`../.ai/learn-cloudflare.md`; the implementation spec is in
`../.ai/learn-implementation.md`; follow-ups are in `../.ai/learn-todo.md`.

## Layout

- `src/trainer/` — Python package:
  - `foundation/` — config, errors, dataset, normalization, passwords.
  - `cards/` — card rules, options, grading, card views, bridge.
  - `scheduling/` — queue and scheduler (not implemented yet).
  - `lifecycle/` — profiles and sessions (not implemented yet).
  - `cli.py`, `__main__.py` at the package root.
- `src/tests/` — Python tests.
- `cloudflare/` — progress Worker, its Node tests and wrangler config.
- `tools/provision_user.py` — adds an account to the Worker's `users.json`.

There is no `learn/build` or `learn/out`: all build artifacts go to the
top-level disposable `build/`, and the trainer runs from `learn/src`. There is
no local progress store; the Worker is the single source of truth.

## Status

Foundation data layer is in place: `Config`, domain errors, the dataset
loader/validator with indexes. The card layer implements the pure L, E, R, C
and F card views, E/R/C/F answer grading and a text renderer, and
`src/trainer/cli.py` exposes them through an interactive text client. E, R, C
and F are answerable: E prompts for one option per element and reports a
score; R asks for the Latin name; C asks for a typed Latin name with a
scaffold; F asks for a typed Latin name with no scaffold. The V card, hints,
scheduling and the web UI are still design-only. There are 191 Python tests
(two live Worker tests skip unless configured) and 22 Worker tests.

## Progress Worker

The Worker is an authenticated file store over R2: login, `/fs` listing and
`GET`/`PUT`/`DELETE /fs/<path>`. The bucket is private; the Worker scopes each
token to one user's prefix or to `tests/`. See `cloudflare/README.md` for
setup and the API.

```sh
cmake --build build --target learn-worker-test
cmake --build build --target learn-worker-dev
cmake --build build --target learn-worker-deploy
```

The Worker is deployed at `https://birds-progress.regevran.workers.dev`.
Provision accounts with:

```sh
python3 learn/tools/provision_user.py <username>
```

Sign in from the text client:

```sh
cd learn/src
python3 -m trainer login --server https://birds-progress.regevran.workers.dev
python3 -m trainer whoami
python3 -m trainer logout
```

The token is stored in `~/.birds_trainer.json` with mode 0600. Live Worker
tests use a `tests`-scoped account:

```sh
BIRDS_TEST_SERVER=https://birds-progress.regevran.workers.dev \
BIRDS_TEST_USER=tester BIRDS_TEST_PASSWORD=... \
cmake --build build --target learn-test-live
```

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
card C acrocephalus-agricola
card C cormorant
card F acrocephalus-agricola
card F cormorant
help
quit
```

`card L`, `card E`, `card R`, `card C` and `card F` are the commands; `L`,
`E`, `R`, `C` and `F` are aliases. `/<text>` searches
species_id, Latin, English, Hebrew, family and order. Every word must match;
`list`, `find`, `birds` and `search` are aliases. The list shows species_id,
Latin, English, Hebrew, family and Hebrew family.

In the interactive client, a search opens `search>` mode. Type text there to
search again; `?` shows help. A bare `/` opens search mode without listing
every bird. `exit`, `quit`, Ctrl-D and Esc (press Esc, then Enter) go one
prompt up: from `search>` back to the card, from an E, R, C or F prompt or
between run cards back to `card>`, and from `card>` out of the client. Ctrl-C
leaves the client.

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

At a Construct prompt, the scaffold is one line: the concatenated word shapes
(`M····c···· p······`), followed by the part lengths and Hebrew glosses
(`(5 ..., 5 ..., 7)`). The genus is one word even when it has several parts.
Type the full Latin name; case and spacing are ignored. A near miss (small
spelling difference with matching first letters) shows the exact spelling and
moves on. A wrong answer gets one retry; the second wrong reveals the answer.

At a Produce prompt, only the Hebrew name is shown; there is no scaffold.
Type the full Latin name. Grading and feedback are the same as for Construct.

A card command also accepts a search query. `card R cormorant` runs R for
every matching bird in search order; one match behaves as a single card.
Press Enter between cards; `exit`, `quit`, Ctrl-D or Esc stops the run. R, C
and F runs skip birds without Hebrew, and E runs skip birds without splits,
reporting the count. This is an ephemeral, one-pass study tool ("search with
benefits"), not saved progress. `--seed N` reproduces the run. `--answer`
needs a single match; one-shot display and `--reveal` print every matching
card.

A one-shot command also works:

```sh
cd learn/src && python3 -m trainer card L acrocephalus-agricola
cd learn/src && python3 -m trainer card E acrocephalus-agricola --answer "1 3 5 1"
cd learn/src && python3 -m trainer card R acrocephalus-agricola --answer "5"
cd learn/src && python3 -m trainer card C acrocephalus-agricola --answer "Acrocephalus agricola"
cd learn/src && python3 -m trainer card F acrocephalus-agricola --answer "Acrocephalus agricola"
```

One-shot commands are display-only unless `--answer` is given. The E answer
string has one option number per element; commas or spaces separate them. The
R answer is one option number. The C answer is the full Latin name; case and
spacing are ignored.

## Testing

```sh
cmake --build build --target learn-test
# or
cd learn/src && python3 -m unittest discover -s tests -v
```
