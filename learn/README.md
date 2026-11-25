# Learn — interactive bird-name trainer

This directory is the trainer project, parallel to `book/` and `data/`.
The Worker owns the dataset and trainer logic; the Python text client renders
its JSON and stores credentials. Progress is stored in private Cloudflare R2
through the Worker in `cloudflare/`. The design is in
`../.ai/learn-reference.md`; the storage/Worker design is in
`../.ai/learn-cloudflare.md`; the endpoint reference is in
[`WORKER-API.md`](WORKER-API.md); command-line explanations are in
[`CLI-USAGE.md`](CLI-USAGE.md); work items are in `../TODO.md`.

## Layout

- `src/trainer/` — Python package:
  - `foundation/` — errors, Worker HTTP client, passwords.
  - `cards/` — card models, Worker JSON decoding and the text renderer.
  - `cli.py`, `__main__.py` at the package root.
- `src/tests/` — Python tests.
- `cloudflare/` — Worker (`/fs` file API, `/app` sessions and stateless
  cards/search), its Node tests, JS trainer modules and wrangler config.
- `WORKER-API.md` — endpoint reference with request/response examples and a
  local quickstart.
- `CLI-USAGE.md` — full text-client usage, commands, practice flow and keys.
- `tools/provision_user.py` — adds an account to the Worker's `users.json`.

There is no `learn/build` or `learn/out`: all build artifacts go to the
top-level disposable `build/`, and the trainer runs from `learn/src`. There is
no local progress store or local bird data; the Worker is the source of truth.

## Status

The Worker implements the dataset, L/E/R/C/F card views, grading, search,
session handle resolution, card-run eligibility, sessions and the scheduler.
`src/trainer/cli.py` is a thin client: it parses
commands, collects answers, renders Worker JSON and stores credentials. E, R,
C and F are answerable; E prompts for one option per element and reports a
score; R asks for the Latin name; C asks for a typed Latin name with a
scaffold; F asks for a typed Latin name with no scaffold. Search matches names
and taxonomy plus the meanings of a bird's etymology parts; results show the
matching element and text and list the matching element entries. Search, card
views and grading require a stored login and a reachable Worker. The V card,
hints and the web UI are still to come. There are 113 Python tests (three live
Worker tests skip unless configured) and 100 Worker tests.

## Progress Worker

The Worker is an authenticated store over R2 with a raw file API and the
`/app` trainer API that owns card views, grading and the scheduler. The bucket
is private; every token maps to one user's prefix (`users/<username>/`).
See `cloudflare/README.md` for setup and `WORKER-API.md` for the endpoint
contract.

```sh
cmake --build build --target learn-worker-test
cmake --build build --target learn-worker-dev
cmake --build build --target learn-worker-deploy
```

The Worker is deployed at `https://birds-progress.regevran.workers.dev`; that
deployment predates the v2 session model and users.json format, so it is only
updated together with a client release. Provision accounts with a generated
`users.json`:

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

The token is stored in `~/.birds_trainer.json` with mode 0600. Search, card
views and grading go through the Worker:

```sh
python3 -m trainer search paddyfield
python3 -m trainer card L paddyfield
python3 -m trainer card F paddyfield
```

Saved sessions are driven from the same prompt. Sessions live in the Worker
with no active one; each client selects the session it works on. The protected
`default` session contains every eligible bird:

```sh
python3 -m trainer session new --search paddyfield --status accidental
python3 -m trainer session new passers --search passer
python3 -m trainer session list
python3 -m trainer session run
python3 -m trainer session run passers
python3 -m trainer session status
python3 -m trainer session open default
python3 -m trainer session rename passers evening
python3 -m trainer session rename evening --clear
python3 -m trainer session delete <id|name>
```

`session new` takes an optional name as `X` or `--name X`, selects the new
session for this client and prints one row; it does not start practising.
`session list` marks this client's selected session with `*`. The choice is
stored locally per server and account, so other clients keep their own.
`session open X` selects a session without practising. The other commands
accept `X` as an exact name, a full id or an unambiguous id prefix, or
`--name X` for an exact name. The Worker resolves handles case-insensitively.
`session rename OLD [NEW]` changes or clears a name without changing the id,
queue or progress. `session new` accepts `--search`, `--status`, `--family`,
`--order`, `--genus`, `--active-cap` and `--seed`. Filters AND between
different options and OR within one option's comma/space-separated list; by
default only `regular` and `introduced` birds are eligible. See `python3 -m
trainer session new --help`. Every session except `default` can be deleted;
deleting the selected session falls back to `default`. Live Worker tests run
against a local `wrangler dev` and a local account; they write under a random
`probe/` prefix in that account's own space:

```sh
cmake --build build --target learn-worker-dev   # in another terminal

BIRDS_TEST_SERVER=http://127.0.0.1:8787 \
BIRDS_TEST_USER=ran BIRDS_TEST_PASSWORD=... \
cmake --build build --target learn-test-live
```

## Running the text client

```sh
cmake --build build --target learn-run
# or
cd learn/src && python3 -m trainer
```

Use `python3 -m trainer --help` for the terse usage and command list, and
`python3 -m trainer <command> --help` (or `help <command>`) for one command.
The longer explanations are in [`CLI-USAGE.md`](CLI-USAGE.md). Inside the
client:

```text
/paddyfield
/acro
card L acrocephalus-agricola
card E acrocephalus-agricola
card E acrocephalus-agricola --seed 1
card R acrocephalus-agricola
card R acrocephalus-agricola --seed 1
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
`E`, `R`, `C` and `F` are aliases. `/<text>` searches species_id, Latin,
English, Hebrew, family, order and the meanings of the name's etymology parts.
Every word must match; `list`, `find`, `birds` and `search` are aliases. The
list shows species_id, Latin, English, Hebrew, family and Hebrew family, plus a
`matched` column when an element caused the match; matching elements are
listed after the table.

In the interactive client, a search opens `search>` mode. Type text there to
search again; `?` shows help. A bare `/` opens search mode without listing
every bird. `exit`, `quit`, Ctrl-D and Esc (press Esc, then Enter) go one
prompt up: from `search>` back to the card, from an E, R, C or F prompt or
between run cards back to `card>`, and from `card>` out of the client. Ctrl-C
leaves the client. Search and card commands require a stored login and a
reachable Worker.

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
Press Enter between cards; `exit`, `quit`, Ctrl-D or Esc stops the run. The
Worker filters the run: R, C and F need Hebrew, and E needs splits. The skipped
count and reason come from the Worker. This is an ephemeral, one-pass study
tool ("search with benefits"), not saved progress. `--seed N` reproduces the
run.

Card views and grading come from the Worker. `card L` is the reference view;
there is no `--answer` or `--reveal` flag. The normal practice flow reveals the
answer: E immediately, R/C/F on the second wrong attempt or a near miss.

A card command also runs outside the interactive prompt:

```sh
cd learn/src && python3 -m trainer card L acrocephalus-agricola
cd learn/src && python3 -m trainer card E acrocephalus-agricola
```

E, R, C and F practise from a shell too: they print the card and prompt for the
answer in the terminal. L only prints.

## Testing

```sh
cmake --build build --target learn-test
# or
cd learn/src && python3 -m unittest discover -s tests -v
```
