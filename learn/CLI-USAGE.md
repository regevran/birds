# Trainer CLI usage

The text client is `python3 -m trainer` from `learn/src`, or
`cmake --build build --target learn-run` from the repository root.

```text
Usage: python3 -m trainer [--no-reverse-hebrew]
       python3 -m trainer [--no-reverse-hebrew] <command> [arguments]
```

Run without arguments for the interactive client. `--help` (or `-h`) prints
the terse usage and command list. Per-command help is available with
`<command> --help` or `help <command>`; this file keeps the longer explanations.

## Login and the Worker

Progress, search, card views and grading live in the Cloudflare Worker.
`login` prompts for the username and password and stores the token in
`~/.birds_trainer.json` with mode 0600; `logout` removes it. The server can also
come from the `BIRDS_TRAINER_SERVER` environment variable. `whoami` shows the
account and token expiry without printing the token.

```sh
python3 -m trainer login --server http://127.0.0.1:8787
python3 -m trainer login --server https://birds-progress.regevran.workers.dev
python3 -m trainer whoami
python3 -m trainer logout
```

Search, card and session commands require a stored login and a reachable
Worker. A login is tied to one server; logging in to another server replaces
the stored one. Token expiry is stored in UTC and displayed in local time.

## Search

```text
/<text>
list|find|birds|search <text>
```

Search is case-insensitive. Every whitespace-separated term must match at least
one of: species id, Latin name, English name, Hebrew name, family, Hebrew
family, order, or an etymology element of the bird's name (element id, display,
English gloss, Hebrew gloss or a variant form). A short fragment can match a
family as well as a bird; for example `acro` matches both `Acrocephalus` and
`Phalacrocoracidae`. Use a longer name or a species id to narrow the result.

Searches also find birds by what their name parts mean: `summit` finds the
`Acrocephalus` birds because `acro` means “summit, peak”, and `locust` finds
`Acridotheres` because its genus means “locust hunter”. The list shows species
id, Latin, English, Hebrew, family and Hebrew family. When an element causes a
match, a `matched` column says which part and text matched, for example
`acrido (=locust)`; a Hebrew query shows the Hebrew match text. Name-only
matches show `name`. After the table, an `Elements matching ...` section lists
the dictionary entries that match, with their English and Hebrew glosses,
theme, origin and bird count.

Saved-session filters (`session new --search ...`) still match identity fields
only, so a session is never filtered by a gloss. Card commands use the full
search, so `card E summit` practises every bird whose name has a part meaning
“summit”.

A species for `card` may be a species id (`acrocephalus-agricola`), a Latin
name, an English name or a unique fragment; the same search rules apply.

In the interactive client, a search opens `search>` mode. Type text there to
search again; `?` shows help; `exit`, `quit`, Ctrl-D or Esc (press Esc, then
Enter) returns to the previous prompt. A bare `/` opens search mode without
listing every bird.

## Cards

```text
card L|L|l <species|search> [--seed N]
card E|E|e <species|search> [--seed N]
card R|R|r <species|search> [--seed N]
card C|C|c <species|search>
card F|F|f <species|search>
```

The card header includes the family name, for example:

```text
[E 1/15] Gulosus aristotelis (Phalacrocoracidae)
```

L is the learning card with the full name, classification, parts, bridge and
whole-word notes. It is also the reference view when you want the answer.

E shows one row per element with Hebrew gloss options. Options stay within the
row's theme, which is a hint. Enter one option number per row; feedback shows
the chosen and correct glosses and the `correct/total` score.

R shows the Hebrew name and numbered Latin options. A wrong choice gets one
retry without revealing the answer; a second wrong reveals the correct Latin.
All species sharing the prompt's Hebrew name are accepted.

C shows the Hebrew name and a scaffold: each Latin word or part with its first
letter, length and, for split parts, its Hebrew gloss. Type the full Latin
name; case and spacing are ignored. A near miss shows the exact spelling and
moves on. A wrong answer gets one retry; the second wrong reveals the answer.

F is C without the scaffold: only the Hebrew name, then a typed Latin name.
Grading and feedback are the same as C.

Each E or R card gets a fresh random option order. `--seed N` reproduces one
exact card. There is no `--answer` or `--reveal` flag: the normal practice flow
reveals the answer, and `card L` is the reference view.

E, R, C and F practise whether you run them from a shell
(`python3 -m trainer card C acro`) or inside the client; L only prints. Running
from a shell starts the same answering flow and prompt as the client.

## Card runs

A card command also accepts a search query. One match shows one card; several
matches run through all matching birds in search order. Press Enter between
cards; `exit`, `quit`, Ctrl-D or Esc stops the run. The Worker filters the run:
R, C and F need Hebrew, E needs split elements. It returns the skipped count
and reason, and an interactive run ends with a summary.

A card run is an ephemeral study tool, not saved progress. Use a session for
saved progress. Plain card commands print every matching card.

## Saved sessions

```text
session new [X | --name X] [options]
session list
session open X | --name X
session status [X | --name X]
session run [X | --name X]
session rename OLD [NEW]
session delete X | --name X
```

Sessions are saved queues of cards stored in the Worker. They are independent
documents; the Worker has no "active" session. Each client remembers which
session it points at, the way git remembers the checked-out branch. The choice
is local, per server and account, kept in `~/.birds_trainer_state.json`
(override the path with `BIRDS_TRAINER_STATE`).

Two clients may point at different sessions, or at the same session. If both
practise the same session they see each other's progress: when a card was
already consumed by the other client, this client says the state changed in
another client, reloads the session and continues from the new current card.

A protected session named `default` is always present: it has no filters, so
it contains every eligible bird, and it cannot be deleted or renamed. It is the
fallback when a client has not selected anything or its selection disappeared.
Other sessions may be named or unnamed ("unnamed" sessions are addressed by
id).

`session new` creates a session in the Worker, selects it for this client and
prints one line; it does not start practising:

```text
* passers  20261123-0902-1a2b  queue 32  pool 164
Practise with: session run
```

With no `X` the session is unnamed. `X` is the **new name**, not an existing
session; names are unique (trimmed, case-insensitive) and an existing one is
rejected. `--name X` is the same as positional `X`; give the name once.

For the other commands, `X` is a handle resolved by the Worker in this order:
exact name, exact id, unambiguous id prefix. `--name X` forces an exact name
match. Giving both positional `X` and `--name` is an error. Handles match
case-insensitively; the stored id remains the lowercase canonical form.

`session list` marks this client's selected session with `*`, like the
checked-out branch in `git branch`, and lists `default` first. If the selected
session no longer exists, the client falls back to `default` and says so:

```text
* default       default               cards 0   queue 7   pool 558
  passers       20261123-0902-1a2b   cards 12  queue 20  pool 150
```

`session open X` selects X for this client without practising. `session run`
with no X practises the selected session; `session run X` selects X here first.
Before practising, the Worker drops birds that already passed from the
session's queue and pool, so an idle session does not re-ask learned birds.
`session status` with no X shows the selected session's row and current card;
`session status X` reads X without selecting it.

`session delete X` deletes any session except `default`, even one another
client has selected. If this client had selected X, its selection falls back to
`default` and the command says so. Other clients notice the next time they use
the deleted session, fall back to `default`, and say so.

`session rename OLD NEW` changes a session's name; `OLD` is resolved like any
handle (or `--name OLD`), and `NEW` is a literal unique name. With no `NEW`, or
with `--clear`, the session becomes unnamed:

```text
session rename evening morning
session rename evening --clear
session rename evening
```

The id, queue and progress do not change, and this client's selection does not
change. The `default` session cannot be renamed or cleared.

Session errors are kept short, for example:

```text
error: session name 'morning' is taken by: 20261122-1831-3c34 'MoRnInG' (case-insensitive name collision)
error: no session named 'evening'
error: the default session cannot be deleted: default 'default' (protected)
```

`session new` accepts `--search`, `--status`, `--family`, `--order`, `--genus`,
`--active-cap N` and `--seed N`; see `session new --help` for the list. The
filters combine with **AND between different options** and **OR within one
option's list**: `--family` and `--order` accept comma- or space-separated
values, and a bird needs at least one value from each option you give.
`--search` requires every word to match names and taxonomy (not element
meanings; use `search` for those). `--active-cap` sets how many birds are
studied at once (default 7) and `--seed` reproduces the order. Eligible birds
always have Hebrew, are not yet passed, and by default are `regular` or
`introduced`; name other statuses with `--status`. The `default` session is
the exception: it has no status filter.

Pausing `session run` (`exit`, Esc or Ctrl-D) leaves the session saved; running
it again resumes the queue. A completed session is not deleted automatically.

The session row shows the counters:

```text
* passers  20261123-0902-1a2b  cards 12  queue 20  pool 150
```

- **cards** — cards consumed in this session.
- **queue** — cards currently waiting in the session queue.
- **pool** — eligible birds not yet added to the queue. This counts birds, not
  cards.

`session list` uses the same meanings. A session starts by taking up to
`active_cap` birds from the pool into the queue; it moves another bird from the
pool when an active bird's chain finishes.

## Keys and display

`exit`, `quit`, Ctrl-D and Esc (press Esc, then Enter) go one prompt up:
`search>` back to its caller, an E/R/C/F answer prompt back to `card>`
(abandoning the card), and `card>` out of the CLI. Ctrl-C leaves the CLI.

Up and down arrows recall command history, kept in
`~/.birds_trainer_history`. Hebrew is reversed for terminals that cannot display
RTL; start with `--no-reverse-hebrew` to print it unchanged.

## Related documentation

- [Worker API](WORKER-API.md) — endpoints and JSON examples.
- [Trainer README](README.md) — build, test and Worker commands.
