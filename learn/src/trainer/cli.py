"""Text client for the Worker-owned trainer.

The Worker owns search, cards, grading and sessions. This module parses
commands, collects input and renders the JSON views; it holds no bird data and
no trainer rules.
"""

from __future__ import annotations

import atexit
import getpass
import os
import re
import secrets
import shlex
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .cards.models import (
    CardType,
    CardView,
    ConstructCardView,
    ElementsCardView,
    LearnCardView,
    ProduceCardView,
    RecognizeCardView,
)
from .cards.results import ElementResult, LatinResult
from .cards.text import (
    render_card,
    render_element_results,
    render_element_row,
    render_latin_result,
    render_recognize_result,
)
from .cards.wire import (
    card_view_from_json,
    element_results_from_json,
    latin_result_from_json,
    recognize_result_from_json,
)
from .foundation import cloud, selection
from .foundation.errors import InvalidRequest

_SEARCH_ALIASES = ("list", "find", "birds", "search")
_ESCAPE = "\x1b"
_UP_SENTINEL = "<UP>"

_HELP_HEADER = """\
Usage: python3 -m trainer [--no-reverse-hebrew]
       python3 -m trainer [--no-reverse-hebrew] <command> [arguments]
"""

_COMMANDS = """\
Commands:
  /<text>                                       search birds, e.g. /acro
  list|find|birds|search <text>                 search birds, e.g. search acro
  card L|L|l <species|search>                   show a Learn card
  card E|E|e <species|search> [--seed N]        practise an Elements card
  card R|R|r <species|search> [--seed N]        practise a Recognize card
  card C|C|c <species|search>                   practise a Construct card
  card F|F|f <species|search>                   practise a Produce card
  login --server <url> [--username <name>]      log in to the progress store
  logout                                        forget the stored login
  whoami                                        show the signed-in account
  session new [X] [options]                     create a session
  session list                                  list sessions; * marks selected
  session open X | --name X                     select a session for this client
  session status [X | --name X]                 show a session and its card
  session run [X | --name X]                    practise a session
  session rename OLD [NEW]                      rename or clear a session name
  session delete X | --name X                   delete a session
  help, ?                                       show this message
  quit, exit                                    leave the client

Run '<command> --help' for command help.
See learn/CLI-USAGE.md for details.
"""



_TOP_HELP = _HELP_HEADER + "\n" + _COMMANDS

_SEARCH_USAGE = """\
Usage: /<text>
       list|find|birds|search <text>

Every whitespace-separated term must match a species id, Latin name, English
name, Hebrew name, family, Hebrew family, order or the meaning of an etymology
element in the name (id, display, English/Hebrew gloss or form). Matching is
case-insensitive.

Results show a `matched` column when an element caused the match, for example
`acrido (=locust)`, followed by an `Elements matching ...` section with the
glosses, theme, origin and bird count. Session filters match names only.
"""

_CARD_USAGE = """\
Usage: card L|E|R|C|F <species|search>
       card E|R <species|search> [--seed N]
       L|E|R|C|F <species|search>

L  learning card: full name, classification, parts and notes (prints only)
E  elements: choose the Hebrew meaning of each element
R  recognize: choose the matching Latin name
C  construct: type the Latin name with a scaffold
F  produce: type the Latin name without a scaffold

E, R, C and F prompt for answers when run from a shell. --seed N reproduces
E/R option order. Run 'card <type> --help' for one card's question and response.
"""

_CARD_TYPE_HELP = {
    "L": """\
Usage: card L <species|search>

Shows the learning card: Latin, English and Hebrew names, family, order,
status, etymology parts, bridge matches and whole-word notes. L only prints and
has no answer prompt. This is the reference view when you want the answer.
""",
    "E": """\
Usage: card E <species|search> [--seed N]

Question:
  One row per element. Each row shows its theme and numbered Hebrew gloss
  options, and the options stay within that theme.

  <element> [1-N]: <option number>
  Enter one option number per row.

Response:
  Feedback shows the chosen and correct glosses and the correct/total score.
  Each E card gets a fresh option order; --seed N reproduces one.
""",
    "R": """\
Usage: card R <species|search> [--seed N]

Question:
  Which Latin name matches the Hebrew name? The options are numbered Latin
  names.

  [1-N]: <option number>
  Enter one option number.

Response:
  A wrong choice gets one retry without revealing the answer; a second wrong
  reveals the correct Latin. All species sharing the prompt's Hebrew name are
  accepted. Each R card gets a fresh option order; --seed N reproduces one.
""",
    "C": """\
Usage: card C <species|search>

Question:
  Shows the Hebrew name and a scaffold: word shapes, part lengths and, for
  split parts, Hebrew glosses.

  Latin: <answer>
  Type the full Latin name.

Response:
  A near miss moves on; a wrong answer gets one retry, then reveals the answer.
""",
    "F": """\
Usage: card F <species|search>

Question:
  Shows only the Hebrew name; there is no scaffold.

  Latin: <answer>
  Type the full Latin name.

Response:
  A near miss moves on; a wrong answer gets one retry, then reveals the answer.
""",
}

_LOGIN_USAGE = """\
Usage: login --server <url> [--username <name>]

Stores a Worker token in ~/.birds_trainer.json with mode 0600. The server can
also come from BIRDS_TRAINER_SERVER. A login replaces the stored server.
"""

_LOGOUT_USAGE = """\
Usage: logout

Removes the stored Worker login.
"""

_WHOAMI_USAGE = """\
Usage: whoami

Shows the signed-in account, server, and token state. The token is never
printed; expiry is shown in local time.
"""

_SESSION_USAGE = """\
Usage: session <command> [options]

Commands:
  new      create a session and select it
  list     list sessions; * marks the selected one
  open     select a session for this client
  status   show a session's current card
  run      practise a session
  rename   change or clear a session name
  delete   delete a saved session

Sessions live in the Worker; each client remembers its own selected session.
The `default` session contains every eligible bird and cannot be deleted.
Names, ids and id prefixes match case-insensitively.

Session counters:
  completed cards  cards consumed in this session
  % completed      birds already learned, 0-100%
  queue            cards waiting in the session queue
  pool             eligible birds not yet added to the queue
"""

_SESSION_ACTION_USAGE = {
    "new": """\
Usage: session new [X | --name X] [--search T] [--status LIST] [--family F]
                   [--order O] [--genus G] [--active-cap N] [--seed N]

Creates a session, selects it for this client and prints it. With no X the
session is unnamed. X is the new name, not an existing session; names are
unique and an existing name is rejected. The session is not started.

Eligible birds have Hebrew. The `default` session contains every eligible
bird and is always present.

Options:
  --name N        the same as X; give the name once
  --search T      free text; every word must match species id, Latin, English,
                  Hebrew, family, Hebrew family or order
  --status LIST   status categories (default: regular, introduced):
                  regular, introduced, accidental, historical, extinct
  --family F      family name
  --order O       order name
  --genus G       genus name
  --active-cap N  birds studied at once (default 7); not a filter
  --seed N        reproduces the card and option order

LIST, F, O and G take comma- or space-separated values and may be repeated.
Filters combine with AND between options and OR within one option: a bird needs
at least one listed value in every option you give, and must satisfy --search.
Element meanings are not searched here; `search` covers those.
""",
    "list": """\
Usage: session list

Lists sessions and marks this client's selected session with *. The default
session is first.
""",
    "open": """\
Usage: session open X | --name X

Selects X for this client. X is an exact name, a full id or an unambiguous id
prefix; --name X matches a name exactly. Other clients keep their own
selection.
""",
    "status": """\
Usage: session status [X | --name X]

Shows a session's counters and current card. Without X it shows this client's
selected session. With X it reads that session without selecting it.
""",
    "run": """\
Usage: session run [X | --name X]

Practises a session. With X it first selects X for this client. Without X it
practises the selected session. Pausing with exit, Esc or Ctrl-D leaves it
saved; run it again to resume.
""",
    "rename": """\
Usage: session rename OLD [NEW]
       session rename OLD --clear

Renames a session. OLD is an exact name, full id or unambiguous id prefix;
--name OLD selects by exact name. NEW is a literal unique name and is never
resolved. With no NEW, or with --clear, the session becomes unnamed. The
default session cannot be renamed.
""",
    "delete": """\
Usage: session delete X | --name X

Deletes a saved session. The default session cannot be deleted. If this client
had selected X, it falls back to default.
""",
}

_AUTH_USAGE = """\
Usage: login/logout/whoami

See `python3 -m trainer login --help`, `logout --help` or `whoami --help`.
"""


def _card_help(card_type: str | None = None) -> str:
    if card_type in _CARD_TYPE_HELP:
        return _CARD_TYPE_HELP[card_type]
    return _CARD_USAGE


def _help_for(words: list[str]) -> str:
    if not words:
        return _TOP_HELP
    first = words[0].lower()
    if words[0].startswith("/") or first in _SEARCH_ALIASES:
        return _SEARCH_USAGE
    if first == "card":
        kind = words[1].upper() if len(words) > 1 else ""
        return _card_help(kind)
    if len(words[0]) == 1 and words[0].upper() in _CARD_TYPE_HELP:
        return _card_help(words[0].upper())
    if first == "login":
        return _LOGIN_USAGE
    if first == "logout":
        return _LOGOUT_USAGE
    if first == "whoami":
        return _WHOAMI_USAGE
    if first == "session":
        action = words[1].lower() if len(words) > 1 else ""
        return _SESSION_ACTION_USAGE.get(action, _SESSION_USAGE)
    if first in ("help", "?"):
        return _TOP_HELP
    return _TOP_HELP + f"\nNo detailed help for {words[0]!r}; see learn/CLI-USAGE.md."


def _help_page(args: list[str]) -> str | None:
    if not args:
        return _TOP_HELP
    if args[0] in ("help", "?"):
        return _help_for(args[1:])
    if not any(arg in ("--help", "-h") for arg in args):
        return None
    words = [arg for arg in args if arg not in ("--help", "-h")]
    return _help_for(words)

_SEARCH_HELP = """\
Search mode:
  text        search birds (same as /text)
  /text       search birds
  ?           show this message
  exit, quit, Ctrl-D, Esc (press Esc, then Enter)
              return to the previous prompt
"""

_E_HELP = """\
Elements card:
  1-N         choose an option
  /text       search birds; list/find/birds/search <text> also work
  ?           show this message
  exit, quit, Ctrl-D, Esc (press Esc, then Enter)
              abandon this card and return to card>
"""

_R_HELP = """\
Recognize card:
  1-N         choose the Latin name
  /text       search birds; list/find/birds/search <text> also work
  ?           show this message
  exit, quit, Ctrl-D, Esc (press Esc, then Enter)
              abandon this card and return to card>
"""

_C_HELP = """\
Construct card:
  type the full Latin name; case and spacing are ignored
  /text       search birds; list/find/birds/search <text> also work
  ?           show this message
  exit, quit, Ctrl-D, Esc (press Esc, then Enter)
              abandon this card and return to card>
"""

_F_HELP = """\
Produce card:
  type the full Latin name; case and spacing are ignored
  /text       search birds; list/find/birds/search <text> also work
  ?           show this message
  exit, quit, Ctrl-D, Esc (press Esc, then Enter)
              abandon this card and return to card>
"""

_SESSION_HELP = """\
Saved session:
  answer the current card as usual
  /text       search birds; list/find/birds/search <text> also work
  ?           show this message
  exit, quit, Ctrl-D, Esc (press Esc, then Enter)
              pause the session; it stays saved
"""


class _Up(Exception):
    """The user asked to go one prompt up."""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    reverse_hebrew = True
    if "--no-reverse-hebrew" in args:
        args.remove("--no-reverse-hebrew")
        reverse_hebrew = False

    if args:
        page = _help_page(args)
        if page is not None:
            print(page)
            return 0
        _dispatch(args, reverse_hebrew, interactive=_practises(args))
        return 0
    return _interactive(reverse_hebrew)


def _practises(args: list[str]) -> bool:
    """True when the command is an E/R/C/F card command run from a shell.

    Answerable cards prompt directly; L only prints. Inside the client every
    command is already interactive.
    """
    words = args[1:] if args[0].lower() == "card" else args
    return bool(words) and words[0].upper() in ("E", "R", "C", "F")


def _interactive(reverse_hebrew: bool) -> int:
    _enable_line_editing()
    print("Trainer text client. Type 'help' for commands.")
    while True:
        try:
            raw = _read_line("card> ")
        except (_Up, KeyboardInterrupt):
            print()
            return 0
        try:
            args = shlex.split(raw)
        except ValueError as exc:
            print(f"parse error: {exc}")
            continue
        if not args:
            continue
        try:
            keep_going = _dispatch(
                args, reverse_hebrew, interactive=True
            )
        except KeyboardInterrupt:
            print()
            return 0
        if not keep_going:
            return 0


def _read_line(prompt: str) -> str:
    """Read one line; exit, quit, Ctrl-D and Esc ask to go one prompt up.

    Esc is line-based: press Esc, then Enter.  With readline that sequence is
    bound to a sentinel; plain line input returns the ESC character itself.
    """
    try:
        text = input(prompt)
    except EOFError:
        raise _Up from None
    stripped = text.strip()
    if stripped.lower() in ("exit", "quit"):
        raise _Up
    if stripped == _UP_SENTINEL:
        _forget_history_item(_UP_SENTINEL)
        raise _Up
    if stripped == _ESCAPE:
        raise _Up
    return text


def _forget_history_item(text: str) -> None:
    """Drop a synthetic readline history entry, if it was recorded."""
    try:
        import readline
    except ImportError:
        return
    length = readline.get_current_history_length()
    if length == 0:
        return
    try:
        if readline.get_history_item(length) == text:
            readline.remove_history_item(length - 1)
    except (ValueError, OSError):
        pass


def _enable_line_editing() -> None:
    """Enable readline editing and persisted command history when available."""
    try:
        import readline
    except ImportError:
        return

    # Esc, then Enter: clear the line, insert the sentinel, accept the line.
    readline.parse_and_bind(
        rf'"\e\C-m": "\C-a\C-k{_UP_SENTINEL}\C-m"'
    )

    history_path = Path.home() / ".birds_trainer_history"
    readline.set_history_length(1000)
    try:
        readline.read_history_file(history_path)
    except OSError:
        pass

    def save_history() -> None:
        try:
            readline.write_history_file(history_path)
        except OSError:
            pass

    atexit.register(save_history)


def _dispatch(
    args: list[str],
    reverse_hebrew: bool,
    *,
    interactive: bool = False,
) -> bool:
    page = _help_page(args)
    if page is not None:
        print(page)
        return True
    command = args[0].lower()
    if command in ("quit", "exit"):
        return False
    if command == "login":
        _login_command(args[1:])
        return True
    if command == "logout":
        _logout_command()
        return True
    if command == "whoami":
        _whoami_command()
        return True
    if command == "session":
        _session_command(args[1:], reverse_hebrew)
        return True
    if args[0].startswith("/"):
        query = " ".join((args[0][1:], *args[1:])).strip()
        app = _require_app()
        if app is not None:
            if interactive:
                _search_mode(app, query, reverse_hebrew)
            else:
                _list_command(
                    app, [query] if query else [], reverse_hebrew
                )
        return True
    if command in _SEARCH_ALIASES:
        query = " ".join(args[1:]).strip()
        app = _require_app()
        if app is not None:
            if interactive:
                _search_mode(app, query, reverse_hebrew)
            else:
                _list_command(app, args[1:], reverse_hebrew)
        return True
    if command == "card":
        _card_command(
            args[1:], reverse_hebrew, interactive=interactive
        )
        return True
    try:
        CardType(args[0].upper())
    except ValueError:
        print(f"unknown command: {args[0]!r}; type 'help'")
    else:
        _card_command(args, reverse_hebrew, interactive=interactive)
    return True


def _require_app() -> cloud.CloudApp | None:
    """Return a Worker client or print the login problem."""
    try:
        credentials = cloud.load_credentials()
    except cloud.CredentialsError as exc:
        print(str(exc))
        return None
    try:
        return cloud.CloudApp(
            credentials.server,
            credentials.token,
            username=credentials.username,
        )
    except ValueError as exc:
        print(f"stored login is invalid: {exc}")
        return None


def _local_time(value: str) -> str:
    """Render the Worker's UTC timestamp in the local timezone."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone()
    zone = local.strftime("%Z") or local.strftime("%z")
    return f"{local:%Y-%m-%d %H:%M:%S} {zone}".strip()


def _login_command(args: list[str]) -> None:
    server: str | None = None
    username: str | None = None
    index = 0
    while index < len(args):
        option = args[index]
        if option == "--server" and index + 1 < len(args):
            server = args[index + 1]
            index += 2
        elif option == "--username" and index + 1 < len(args):
            username = args[index + 1]
            index += 2
        elif option.startswith("--"):
            print(f"unknown option: {option!r}")
            _print_login_usage()
            return
        else:
            print(f"unexpected argument: {option!r}")
            _print_login_usage()
            return

    if server is None:
        server = os.environ.get(cloud.SERVER_ENV)
    if not server:
        _print_login_usage()
        return

    if username is None:
        try:
            username = input("Username: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
    if not username:
        print("username is required")
        return

    try:
        password = getpass.getpass("Password: ")
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if not password:
        print("password is required")
        return

    try:
        credentials = cloud.login(server, username, password)
        cloud.save_credentials(credentials)
    except (cloud.CloudError, cloud.CredentialsError, OSError, ValueError) as exc:
        print(f"login failed: {exc}")
        return

    print(
        f"Logged in as {credentials.username} ({credentials.scope}) "
        f"at {credentials.server}."
    )
    print(f"Token expires {_local_time(credentials.expires_at)}.")


def _print_login_usage() -> None:
    print("usage: login --server <url> [--username <name>]")


def _logout_command() -> None:
    try:
        removed = cloud.delete_credentials()
    except OSError as exc:
        print(f"logout failed: {exc}")
        return
    print("Logged out." if removed else "Not logged in.")


def _whoami_command() -> None:
    try:
        credentials = cloud.load_credentials(require_valid=False)
    except cloud.CredentialsError as exc:
        print(str(exc))
        return
    state = (
        "expired"
        if cloud.credentials_expired(credentials)
        else "valid"
    )
    print(
        f"{credentials.username} ({credentials.scope}) "
        f"at {credentials.server}"
    )
    print(f"Token {state}; expires {_local_time(credentials.expires_at)}.")


def _session_command(
    args: list[str], reverse_hebrew: bool
) -> None:
    if not args:
        _print_session_usage()
        return
    app = _require_app()
    if app is None:
        return

    subcommand = args[0].lower()
    rest = args[1:]
    try:
        if subcommand == "new":
            _session_new(app, rest)
        elif subcommand == "list":
            _session_list(app)
        elif subcommand == "open":
            _session_open(app, rest)
        elif subcommand == "status":
            _session_status(app, rest, reverse_hebrew)
        elif subcommand == "run":
            _session_run_command(app, rest, reverse_hebrew)
        elif subcommand == "rename":
            _session_rename(app, rest)
        elif subcommand == "delete":
            _session_delete(app, rest)
        else:
            _print_session_usage()
    except cloud.CloudError as exc:
        _print_session_failure(f"session {subcommand}", app, exc)
    except InvalidRequest as exc:
        print(f"invalid Worker response: {exc}")
    except ValueError as exc:
        print(f"session {subcommand}: {exc}")


def _print_session_usage() -> None:
    print(
        "usage: session new [X | --name X] [--search T] [--status LIST] "
        "[--family F] [--order O] [--genus G] [--active-cap N] [--seed N]"
    )
    print("       session list")
    print("       session open|delete X | --name X")
    print("       session status|run [X | --name X]")
    print("       session rename OLD [NEW] [--clear]")


def _session_new(
    app: cloud.CloudApp, args: list[str]
) -> None:
    name: str | None = None
    positional_name: str | None = None
    search_words: list[str] = []
    statuses: list[str] = []
    families: list[str] = []
    orders: list[str] = []
    genera: list[str] = []
    active_cap: int | None = None
    seed: int | None = None

    index = 0
    while index < len(args):
        option = args[index]
        if option in ("--name", "--search", "--status", "--family",
                      "--order", "--genus", "--active-cap", "--seed"):
            if index + 1 >= len(args):
                print(f"{option} needs a value")
                return
            value = args[index + 1]
            index += 2
            if option == "--name":
                if name is not None:
                    print("--name given more than once")
                    return
                name = value.strip()
                if not name:
                    print("--name must not be empty")
                    return
            elif option == "--search":
                search_words.extend(value.split())
            elif option == "--status":
                statuses.extend(_split_values(value))
            elif option == "--family":
                families.extend(_split_values(value))
            elif option == "--order":
                orders.extend(_split_values(value))
            elif option == "--genus":
                genera.extend(_split_values(value))
            elif option == "--active-cap":
                try:
                    active_cap = int(value)
                except ValueError:
                    print("--active-cap needs an integer")
                    return
                if active_cap < 1:
                    print("--active-cap must be positive")
                    return
            else:
                try:
                    seed = int(value)
                except ValueError:
                    print("--seed needs an integer")
                    return
                if seed < 0:
                    print("--seed must not be negative")
                    return
        elif option.startswith("-"):
            print(f"unknown option: {option!r}")
            _print_session_usage()
            return
        else:
            if positional_name is not None:
                print(f"unexpected argument: {option!r}")
                _print_session_usage()
                return
            positional_name = option.strip()
            if not positional_name:
                print("session name must not be empty")
                return
            index += 1

    if name is not None and positional_name is not None:
        print("give the session name once, as X or --name X")
        _print_session_usage()
        return
    chosen_name = name if name is not None else positional_name

    filter_data: dict[str, object] = {}
    if families:
        filter_data["families"] = families
    if orders:
        filter_data["orders"] = orders
    if genera:
        filter_data["genera"] = genera
    if statuses:
        filter_data["statuses"] = statuses
    if search_words:
        filter_data["search"] = " ".join(search_words)

    settings = {"active_cap": active_cap} if active_cap is not None else None
    view = app.create_session(
        name=chosen_name,
        filter=filter_data or None,
        settings=settings,
        seed=seed,
    )
    session = view.get("session") or {}
    session_id = str(session["session_id"])
    _remember_selected(app, session_id)
    print(_session_row(session, selected=True, cards=False))
    if view.get("current"):
        print("Practise with: session run")
    else:
        print("Session complete.")


def _split_values(value: str) -> list[str]:
    return [
        part
        for part in value.replace(",", " ").split()
        if part
    ]


def _session_list(app: cloud.CloudApp) -> None:
    document = app.list_sessions()
    try:
        sessions = list(document["sessions"])
    except (KeyError, TypeError) as exc:
        raise InvalidRequest(
            "session list has no sessions"
        ) from exc
    if not sessions:
        print("no saved sessions")
        return
    selected = _selected_session_id(app)
    ids = {
        str(session.get("session_id", "")) for session in sessions
    }
    if selected not in ids:
        selected = "default"
        _remember_selected(app, selected)
    width = max(len(_session_display_name(session)) for session in sessions)
    for session in sessions:
        print(
            _session_row(
                session,
                selected=str(session.get("session_id", "")) == selected,
                name_width=width,
            )
        )


def _session_open(app: cloud.CloudApp, args: list[str]) -> None:
    target = _parse_session_target(
        args,
        "usage: session open X | --name X",
        required=True,
    )
    if target is None:
        return
    handle, by_name = target
    session = _resolve_session(app, handle, by_name=by_name)
    session_id = str(session["session_id"])
    _remember_selected(app, session_id)
    print(_session_row(session, selected=True, cards=False))


def _session_status(
    app: cloud.CloudApp, args: list[str], reverse_hebrew: bool
) -> None:
    target = _parse_session_target(
        args,
        "usage: session status [X | --name X]",
        required=False,
    )
    if target is None:
        return
    handle, by_name = target
    selected = _selected_session_id(app)
    if handle is None:
        view = _selected_session_view(app)
        marked = True
    else:
        session = _resolve_session(app, handle, by_name=by_name)
        session_id = str(session["session_id"])
        view = app.session(session_id)
        marked = session_id == selected
    _print_session_view(view, reverse_hebrew, selected=marked)


def _session_run_command(
    app: cloud.CloudApp, args: list[str], reverse_hebrew: bool
) -> None:
    target = _parse_session_target(
        args,
        "usage: session run [X | --name X]",
        required=False,
    )
    if target is None:
        return
    handle, by_name = target
    if handle is None:
        view = _selected_session_view(app, prepare=True)
    else:
        session = _resolve_session(app, handle, by_name=by_name)
        session_id = str(session["session_id"])
        _remember_selected(app, session_id)
        view = app.prepare_session(session_id)
    _session_run(app, view, reverse_hebrew)


def _session_rename(app: cloud.CloudApp, args: list[str]) -> None:
    selector_handle: str | None = None
    selector_name: str | None = None
    new_name: str | None = None
    clear = False
    index = 0
    while index < len(args):
        option = args[index]
        if option == "--name":
            if selector_handle is not None or selector_name is not None:
                print("give the old session once, as OLD or --name OLD")
                _print_session_usage()
                return
            if index + 1 >= len(args):
                print("--name needs a value")
                return
            selector_name = args[index + 1].strip()
            index += 2
            if not selector_name:
                print("--name must not be empty")
                return
        elif option == "--clear":
            if clear:
                print("--clear given more than once")
                return
            clear = True
            index += 1
        elif option.startswith("-"):
            print(f"unknown option: {option!r}")
            _print_session_usage()
            return
        else:
            value = option.strip()
            if selector_handle is None and selector_name is None:
                selector_handle = value
            elif new_name is None:
                new_name = value
                if not new_name:
                    print(
                        "error: a session name must not be empty; "
                        "use --clear to remove a name"
                    )
                    return
            else:
                print("too many arguments")
                _print_session_usage()
                return
            index += 1

    if selector_handle is None and selector_name is None:
        _print_session_usage()
        return
    if clear and new_name is not None:
        print("error: give a new name or --clear, not both")
        return
    if not clear and new_name is None:
        clear = True

    session = _resolve_session(
        app,
        selector_name if selector_name is not None else selector_handle,
        by_name=selector_name is not None,
    )
    view = app.rename_session(
        str(session["session_id"]), None if clear else new_name
    )
    renamed = view.get("session") or {}
    print(
        _session_row(
            renamed,
            selected=str(renamed.get("session_id", ""))
            == _selected_session_id(app),
            cards=False,
        )
    )


def _session_delete(app: cloud.CloudApp, args: list[str]) -> None:
    target = _parse_session_target(
        args,
        "usage: session delete X | --name X",
        required=True,
    )
    if target is None:
        return
    handle, by_name = target
    session = _resolve_session(app, handle, by_name=by_name)
    session_id = str(session["session_id"])
    selected = _selected_session_id(app)
    app.delete_session(session_id)
    name = session.get("name")
    print(f"Deleted {name or session_id}.")
    if session_id == selected:
        _remember_selected(app, "default")
        print("Selected session deleted; using default.")


def _resolve_session(
    app: cloud.CloudApp, handle: str, *, by_name: bool = False
) -> dict:
    document = app.resolve_session(handle, by_name=by_name)
    try:
        session = document["session"]
        str(session["session_id"])
    except (KeyError, TypeError) as exc:
        raise InvalidRequest(
            "session resolve response has no session"
        ) from exc
    return session


def _selected_session_id(app: cloud.CloudApp) -> str:
    return (
        selection.load_selected(app.server, app.username) or "default"
    )


def _remember_selected(app: cloud.CloudApp, session_id: str) -> None:
    selection.save_selected(app.server, app.username, session_id)


def _selected_session_view(
    app: cloud.CloudApp, *, prepare: bool = False
) -> dict:
    selected = _selected_session_id(app)
    try:
        if prepare:
            return app.prepare_session(selected)
        return app.session(selected)
    except cloud.CloudError as exc:
        if exc.code != "session_not_found" or selected == "default":
            raise
        _remember_selected(app, "default")
        print(
            f"selected session {selected!r} no longer exists; "
            "using default."
        )
        if prepare:
            return app.prepare_session("default")
        return app.session("default")


def _parse_session_target(
    args: list[str], usage: str, *, required: bool
) -> tuple[str, bool] | tuple[None, bool] | None:
    handle: str | None = None
    name: str | None = None
    index = 0
    while index < len(args):
        option = args[index]
        if option == "--name":
            if name is not None:
                print("--name given more than once")
                print(usage)
                return None
            if index + 1 >= len(args):
                print("--name needs a value")
                print(usage)
                return None
            name = args[index + 1].strip()
            index += 2
            if not name:
                print("--name must not be empty")
                print(usage)
                return None
        elif option.startswith("-"):
            print(f"unknown option: {option!r}")
            print(usage)
            return None
        else:
            if handle is not None:
                print("only one session may be given")
                print(usage)
                return None
            handle = option.strip()
            index += 1
    if handle is not None and name is not None:
        print("give the session once, as X or --name X")
        print(usage)
        return None
    if required and handle is None and name is None:
        print(usage)
        return None
    if name is not None:
        return name, True
    return handle, False


def _session_display_name(session: dict) -> str:
    name = session.get("name")
    return str(name) if name else "(unnamed)"


def _session_row(
    session: dict,
    *,
    selected: bool,
    cards: bool = True,
    name_width: int = 0,
) -> str:
    name = _session_display_name(session)
    if name_width < len(name):
        name_width = len(name)
    session_id = str(session.get("session_id", ""))
    marker = "*" if selected else " "
    row = f"{marker} {name:<{name_width}}  {session_id:<20}"
    if cards:
        count = session.get("session_card_count", 0)
        row += f"  completed cards {count}"
    percent = session.get("percent_completed")
    if percent is None:
        percent = 100 if session.get("status") == "completed" else 0
    row += f"  {percent}%"
    row += (
        f"  queue {session.get('queue_size', 0)}"
        f"  pending {session.get('pending_size', 0)}"
        f"  history {session.get('history_size', 0)}"
    )
    return row


def _print_session_view(
    view: dict, reverse_hebrew: bool, *, selected: bool
) -> None:
    session = view.get("session") or {}
    print(_session_row(session, selected=selected))
    current = view.get("current")
    if not current:
        print("Session complete.")
        return
    print()
    print(
        render_card(
            card_view_from_json(current.get("card")),
            reverse_hebrew=reverse_hebrew,
        )
    )


def _session_run(
    app: cloud.CloudApp,
    view: dict,
    reverse_hebrew: bool,
) -> None:
    session = view.get("session") or {}
    session_id = str(session.get("session_id", ""))
    print(_session_row(session, selected=True))
    while True:
        current = view.get("current")
        if not current:
            print("Session complete.")
            return
        card = card_view_from_json(current.get("card"))
        print()
        print(render_card(card, reverse_hebrew=reverse_hebrew))
        try:
            payload = _session_answer_prompt(
                app, card, reverse_hebrew
            )
        except _Up:
            print("session paused; it stays saved.")
            return
        if payload is None:
            return
        action = payload.pop("action")
        try:
            response = app.answer(
                session_id, str(current.get("uid", "")), action, **payload
            )
        except cloud.CloudError as exc:
            if exc.status != 412 and exc.code != "stale_card":
                raise
            print(
                "state changed in another client; "
                "reloading the session."
            )
            view = app.session(session_id)
            continue
        feedback = response.get("feedback")
        if feedback:
            print()
            _print_session_feedback(feedback, card, reverse_hebrew)
        view = response.get("session") or {}


def _session_answer_prompt(
    app: cloud.CloudApp, card: CardView, reverse_hebrew: bool
) -> dict | None:
    if isinstance(card, LearnCardView):
        while True:
            raw = _read_line("  [Enter] next, exit to pause: ")
            text = raw.strip()
            if text == "?":
                print(_SESSION_HELP)
                print(render_card(card, reverse_hebrew=reverse_hebrew))
                continue
            query = _search_request(text)
            if query is not None:
                _search_mode(app, query, reverse_hebrew)
                print(render_card(card, reverse_hebrew=reverse_hebrew))
                continue
            if not text:
                return {"action": "advance"}
            print("press Enter for the next card, or exit to pause")

    if isinstance(card, ElementsCardView):
        choices: dict[str, str] = {}
        for index, row in enumerate(card.rows):
            label = ", ".join(row.latin_forms)
            while True:
                raw = _read_line(
                    f"  {label} [1-{len(row.options)}]: "
                )
                text = raw.strip()
                if text == "?":
                    print(_SESSION_HELP)
                    print(
                        render_element_row(
                            card,
                            index,
                            reverse_hebrew=reverse_hebrew,
                        )
                    )
                    continue
                query = _search_request(text)
                if query is not None:
                    _search_mode(app, query, reverse_hebrew)
                    print(
                        render_element_row(
                            card,
                            index,
                            reverse_hebrew=reverse_hebrew,
                        )
                    )
                    continue
                try:
                    number = int(text)
                except ValueError:
                    print(
                        "enter an option number, /text to search, "
                        "? for help, or exit to pause"
                    )
                    continue
                if not 1 <= number <= len(row.options):
                    print(f"choose 1-{len(row.options)}")
                    continue
                choices[row.element_id] = row.options[number - 1]
                break
        return {"action": "answer", "choices": choices}

    if isinstance(card, RecognizeCardView):
        while True:
            raw = _read_line(f"  choice [1-{len(card.options)}]: ")
            text = raw.strip()
            if text == "?":
                print(_SESSION_HELP)
                print(render_card(card, reverse_hebrew=reverse_hebrew))
                continue
            query = _search_request(text)
            if query is not None:
                _search_mode(app, query, reverse_hebrew)
                print(render_card(card, reverse_hebrew=reverse_hebrew))
                continue
            try:
                number = int(text)
            except ValueError:
                print(
                    "enter an option number, /text to search, "
                    "? for help, or exit to pause"
                )
                continue
            if not 1 <= number <= len(card.options):
                print(f"choose 1-{len(card.options)}")
                continue
            return {
                "action": "answer",
                "choice": card.options[number - 1].species_id,
            }

    if isinstance(card, (ConstructCardView, ProduceCardView)):
        while True:
            raw = _read_line("  Latin: ")
            text = raw.strip()
            if text == "?":
                print(_SESSION_HELP)
                print(render_card(card, reverse_hebrew=reverse_hebrew))
                continue
            query = _search_request(text)
            if query is not None:
                _search_mode(app, query, reverse_hebrew)
                print(render_card(card, reverse_hebrew=reverse_hebrew))
                continue
            if not text:
                print(
                    "type the Latin name, /text to search, "
                    "? for help, or exit to pause"
                )
                continue
            return {"action": "answer", "response": text}

    raise InvalidRequest(f"cannot answer {type(card).__name__}")


def _print_session_feedback(
    feedback: dict, card: CardView, reverse_hebrew: bool
) -> None:
    kind = feedback.get("kind")
    if kind == "elements":
        results = element_results_from_json(feedback.get("results"))
        print(
            render_element_results(
                card, results, reverse_hebrew=reverse_hebrew
            )
        )
    elif kind == "recognize":
        print(
            render_recognize_result(
                recognize_result_from_json(feedback.get("result"))
            )
        )
    elif kind == "latin":
        print(
            render_latin_result(
                latin_result_from_json(feedback.get("result"))
            )
        )
    elif kind == "retry":
        chosen = feedback.get("chosen") or feedback.get("response") or ""
        print(f"  wrong: chose {chosen!r}; try again.")
    else:
        print(f"  feedback: {feedback}")


@dataclass(frozen=True)
class _SearchText:
    field: str
    text: str


@dataclass(frozen=True)
class _SearchMatch:
    kind: str
    element_id: str = ""
    texts: tuple[_SearchText, ...] = ()


@dataclass(frozen=True)
class _SearchElement:
    element_id: str
    en: str
    he: str
    theme: str
    origin: str
    bird_count: int
    matched: tuple[_SearchText, ...]


@dataclass(frozen=True)
class _SearchBird:
    species_id: str
    latin: str
    english: str
    hebrew: str
    family: str
    family_he: str
    order: str
    matched: tuple[_SearchMatch, ...]


@dataclass
class _SearchResults:
    birds: list[_SearchBird]
    elements: list[_SearchElement]


def _search_mode(
    app: cloud.CloudApp, initial_query: str, reverse_hebrew: bool
) -> None:
    """Read-only bird search; every input is a query except ? and up."""
    if initial_query:
        _list_command(app, [initial_query], reverse_hebrew)
    else:
        print("Search mode: type text to search; ? for help; exit to return.")
    while True:
        try:
            raw = _read_line("search> ")
        except _Up:
            return
        text = raw.strip()
        if not text or text == "/":
            continue
        if text == "?":
            print(_SEARCH_HELP)
            continue
        query = text[1:].strip() if text.startswith("/") else text
        if query:
            _list_command(app, [query], reverse_hebrew)


def _card_command(
    args: list[str],
    reverse_hebrew: bool,
    *,
    interactive: bool = False,
) -> None:
    usage = (
        'usage: card L|E|R|C|F <species|search> [--seed N] '
        '(or L|E|R|C|F ...)'
    )
    if len(args) < 2:
        print(usage)
        return

    try:
        card_type = CardType(args[0].upper())
    except ValueError:
        choices = ", ".join(member.value for member in CardType)
        print(f"unknown card type {args[0]!r}; choose {choices}")
        return

    species_words: list[str] = []
    seed = 0
    seed_given = False
    index = 1
    while index < len(args):
        option = args[index]
        if option == "--seed" and index + 1 < len(args):
            try:
                seed = int(args[index + 1])
            except ValueError:
                print("--seed needs an integer")
                return
            seed_given = True
            index += 2
        elif option.startswith("--"):
            print(f"unknown option: {option!r}")
            return
        else:
            species_words.append(option)
            index += 1

    query = " ".join(species_words).strip()
    if query.startswith("/"):
        query = query[1:].strip()
    if not query:
        print(usage)
        return

    app = _require_app()
    if app is None:
        return
    run = _card_run(app, query, card_type.value)
    if run is None:
        return
    matches, skipped, skip_reason = run
    if not matches:
        if skipped:
            print(
                f"no birds matching "
                f"{_display_query(query, reverse_hebrew)!r} can make a card of "
                f"type {card_type.value} "
                f"({skipped} skipped: {skip_reason})"
            )
        else:
            print(f"bird {_display_query(query, reverse_hebrew)!r} not found")
        return

    # E/R option order is deterministic given a seed.  Practised cards get
    # fresh variety; --seed reproduces an exact card or run.
    if (
        interactive
        and not seed_given
        and card_type in (CardType.E, CardType.R)
    ):
        seed = secrets.randbelow(1_000_000_000)

    if len(matches) == 1 and skipped == 0:
        _single_card(
            app,
            matches[0],
            card_type,
            seed,
            reverse_hebrew,
            interactive=interactive,
        )
        return

    _run_cards(
        app,
        card_type,
        query,
        matches,
        skipped,
        skip_reason,
        seed,
        reverse_hebrew,
        interactive=interactive,
    )


def _print_cloud_failure(
    action: str, app: cloud.CloudApp, exc: cloud.CloudError
) -> None:
    """Print the server and status, not just a bare server message."""
    detail = (
        f"{exc.code} (HTTP {exc.status})"
        if exc.status
        else exc.code
    )
    print(f"{action} failed at {app.server}: {detail}: {exc}")


def _print_session_failure(
    action: str, app: cloud.CloudApp, exc: cloud.CloudError
) -> None:
    """Keep semantic session errors short; keep transport failures detailed."""
    if exc.status and 400 <= exc.status < 500:
        print(f"error: {exc.message or exc.code}")
        return
    _print_cloud_failure(action, app, exc)


def _search_texts(raw) -> tuple[_SearchText, ...]:
    texts = []
    for item in raw:
        texts.append(_SearchText(str(item["field"]), str(item["text"])))
    return tuple(texts)


def _search_matches(raw) -> tuple[_SearchMatch, ...]:
    matches = []
    for item in raw:
        kind = str(item["kind"])
        if kind == "name":
            matches.append(
                _SearchMatch("name", texts=_search_texts(item["texts"]))
            )
        elif kind == "element":
            matches.append(
                _SearchMatch(
                    "element",
                    str(item["element_id"]),
                    _search_texts(item["texts"]),
                )
            )
        else:
            raise TypeError(f"unknown match kind {kind!r}")
    return tuple(matches)


def _search_elements(raw) -> list[_SearchElement]:
    elements = []
    for item in raw:
        elements.append(
            _SearchElement(
                element_id=str(item["element_id"]),
                en=str(item["en"]),
                he=str(item["he"]),
                theme=str(item["theme"]),
                origin=str(item["origin"]),
                bird_count=int(item["bird_count"]),
                matched=_search_texts(item["matched"]),
            )
        )
    return elements


def _search_bird(item: dict) -> _SearchBird:
    return _SearchBird(
        species_id=str(item["species_id"]),
        latin=str(item["latin"]),
        english=str(item["english"]),
        hebrew=str(item["hebrew"]),
        family=str(item["family"]),
        family_he=str(item["family_he"]),
        order=str(item["order"]),
        matched=_search_matches(item["matched"]),
    )


def _search_birds(
    app: cloud.CloudApp, query: str
) -> _SearchResults | None:
    try:
        document = app.search_birds(query)
    except cloud.CloudError as exc:
        _print_cloud_failure("search", app, exc)
        return None
    birds: list[_SearchBird] = []
    try:
        for item in document["birds"]:
            birds.append(_search_bird(item))
        elements = _search_elements(document["elements"])
    except (KeyError, TypeError, ValueError):
        print("invalid Worker search response")
        return None
    return _SearchResults(birds=birds, elements=elements)


def _card_run(
    app: cloud.CloudApp, query: str, card_type: str
) -> tuple[list[_SearchBird], int, str] | None:
    try:
        document = app.card_run(query, card_type)
    except cloud.CloudError as exc:
        _print_cloud_failure("card", app, exc)
        return None
    try:
        birds = [_search_bird(item) for item in document["birds"]]
        skipped = int(document["skipped"])
        skip_reason = str(document["skip_reason"])
    except (KeyError, TypeError, ValueError):
        print("invalid Worker card-run response")
        return None
    return birds, skipped, skip_reason


def _card_from_worker(
    app: cloud.CloudApp,
    species_id: str,
    card_type: str,
    seed: int,
) -> CardView | None:
    try:
        document = app.card_view(species_id, card_type, seed)
        return card_view_from_json(document.get("card"))
    except cloud.CloudError as exc:
        _print_cloud_failure("card", app, exc)
        return None
    except InvalidRequest as exc:
        print(f"invalid Worker card: {exc}")
        return None


def _single_card(
    app: cloud.CloudApp,
    bird: _SearchBird,
    card_type: CardType,
    seed: int,
    reverse_hebrew: bool,
    *,
    interactive: bool,
) -> None:
    view = _card_from_worker(app, bird.species_id, card_type.value, seed)
    if view is None:
        return

    if interactive:
        if isinstance(view, ElementsCardView):
            _answer_interactively(app, bird, view, seed, reverse_hebrew)
            return
        if isinstance(view, RecognizeCardView):
            _answer_recognize(app, bird, view, seed, reverse_hebrew)
            return
        if isinstance(view, (ConstructCardView, ProduceCardView)):
            _answer_typed(
                app,
                bird,
                view,
                seed,
                reverse_hebrew,
                _C_HELP if isinstance(view, ConstructCardView) else _F_HELP,
            )
            return

    print(render_card(view, reverse_hebrew=reverse_hebrew))


@dataclass
class _RunStats:
    total: int
    completed: int = 0
    element_correct: int = 0
    element_total: int = 0
    first_try: int = 0
    retry: int = 0
    revealed: int = 0
    near_miss: int = 0


def _run_cards(
    app: cloud.CloudApp,
    card_type: CardType,
    query: str,
    matches: list[_SearchBird],
    skipped: int,
    skip_reason: str,
    seed: int,
    reverse_hebrew: bool,
    *,
    interactive: bool,
) -> None:
    print(
        _run_header(
            card_type,
            query,
            len(matches),
            skipped,
            skip_reason,
            reverse_hebrew,
        )
    )
    stats = _RunStats(total=len(matches))
    stopped = False

    for offset, bird in enumerate(matches):
        position = (offset + 1, stats.total)
        card_seed = seed + offset
        view = _card_from_worker(
            app, bird.species_id, card_type.value, card_seed
        )
        if view is None:
            stopped = True
            break

        if not interactive:
            print(
                render_card(
                    view,
                    reverse_hebrew=reverse_hebrew,
                    position=position,
                )
            )
            print()
            continue

        if isinstance(view, LearnCardView):
            print(
                render_card(
                    view,
                    reverse_hebrew=reverse_hebrew,
                    position=position,
                )
            )
        elif isinstance(view, ElementsCardView):
            results = _answer_interactively(
                app,
                bird,
                view,
                card_seed,
                reverse_hebrew,
                position=position,
            )
            if results is None:
                stopped = True
                break
            stats.element_correct += sum(
                result.correct for result in results
            )
            stats.element_total += len(results)
        elif isinstance(view, RecognizeCardView):
            outcome = _answer_recognize(
                app,
                bird,
                view,
                card_seed,
                reverse_hebrew,
                position=position,
            )
            if outcome is None:
                stopped = True
                break
            _count_recognize(stats, outcome)
        elif isinstance(view, (ConstructCardView, ProduceCardView)):
            outcome = _answer_typed(
                app,
                bird,
                view,
                card_seed,
                reverse_hebrew,
                _C_HELP if isinstance(view, ConstructCardView) else _F_HELP,
                position=position,
            )
            if outcome is None:
                stopped = True
                break
            _count_latin(stats, outcome)
        else:
            raise TypeError(f"cannot present {type(view).__name__}")

        stats.completed += 1
        if offset + 1 < stats.total and not _wait_for_next():
            stopped = True
            break

    if not interactive:
        return
    _print_run_summary(card_type, stats, stopped)


def _count_recognize(stats: _RunStats, outcome: str) -> None:
    if outcome == "first":
        stats.first_try += 1
    elif outcome == "retry":
        stats.retry += 1
    else:
        stats.revealed += 1


def _count_latin(stats: _RunStats, outcome: str) -> None:
    if outcome == "first":
        stats.first_try += 1
    elif outcome == "near_miss":
        stats.near_miss += 1
    elif outcome == "retry":
        stats.retry += 1
    else:
        stats.revealed += 1


def _run_header(
    card_type: CardType,
    query: str,
    count: int,
    skipped: int,
    skip_reason: str,
    reverse_hebrew: bool,
) -> str:
    line = (
        f"{card_type.value} run: {count} "
        f"bird{'s' if count != 1 else ''} matching "
        f"{_display_query(query, reverse_hebrew)!r}"
    )
    if skipped:
        line += f" ({skipped} skipped: {skip_reason})"
    return line


def _wait_for_next() -> bool:
    while True:
        try:
            raw = _read_line("  [Enter] next, exit to stop: ")
        except _Up:
            return False
        if not raw.strip():
            return True
        print("press Enter for the next card, or exit to stop")


def _print_run_summary(
    card_type: CardType,
    stats: _RunStats,
    stopped: bool,
) -> None:
    if stopped:
        print(
            f"{card_type.value} run stopped after {stats.completed} "
            f"of {stats.total} cards."
        )
        return
    if card_type is CardType.E:
        print(
            f"E run complete: {stats.total} cards, "
            f"{stats.element_correct}/{stats.element_total} "
            "elements correct."
        )
    elif card_type is CardType.R:
        print(
            f"R run complete: {stats.total} cards, "
            f"first try {stats.first_try}, retry {stats.retry}, "
            f"revealed {stats.revealed}."
        )
    elif card_type in (CardType.C, CardType.F):
        print(
            f"{card_type.value} run complete: {stats.total} cards, "
            f"first try {stats.first_try}, near miss {stats.near_miss}, "
            f"retry {stats.retry}, revealed {stats.revealed}."
        )
    else:
        print(f"L run complete: {stats.total} cards.")


def _grade_worker(
    app: cloud.CloudApp,
    bird: _SearchBird,
    card_type: str,
    seed: int,
    attempt: int,
    *,
    choices: dict[str, str] | None = None,
    choice: str | None = None,
    response: str | None = None,
) -> dict | None:
    try:
        return app.grade_card(
            bird.species_id,
            card_type,
            seed,
            attempt,
            choices=choices,
            choice=choice,
            response=response,
        )
    except cloud.CloudError as exc:
        _print_cloud_failure("grading", app, exc)
        return None
    except InvalidRequest as exc:
        print(f"invalid Worker response: {exc}")
        return None


def _feedback(document: dict | None) -> dict | None:
    if document is None:
        return None
    feedback = document.get("feedback")
    return feedback if isinstance(feedback, dict) else None


def _answer_recognize(
    app: cloud.CloudApp,
    bird: _SearchBird,
    view: RecognizeCardView,
    seed: int,
    reverse_hebrew: bool,
    *,
    position: tuple[int, int] | None = None,
) -> str | None:
    print(
        render_card(
            view, reverse_hebrew=reverse_hebrew, position=position
        )
    )
    attempt = 1
    while True:
        try:
            raw = _read_line(f"  choice [1-{len(view.options)}]: ")
        except _Up:
            print("card cancelled.")
            return None
        text = raw.strip()
        if text == "?":
            print(_R_HELP)
            print(
                render_card(
                    view, reverse_hebrew=reverse_hebrew, position=position
                )
            )
            continue
        query = _search_request(text)
        if query is not None:
            _search_mode(app, query, reverse_hebrew)
            print(
                render_card(
                    view, reverse_hebrew=reverse_hebrew, position=position
                )
            )
            continue
        try:
            number = int(text)
        except ValueError:
            print(
                "enter an option number, /text to search, "
                "? for help, or exit"
            )
            continue
        if not 1 <= number <= len(view.options):
            print(f"choose 1-{len(view.options)}")
            continue
        document = _grade_worker(
            app,
            bird,
            "R",
            seed,
            attempt,
            choice=view.options[number - 1].species_id,
        )
        feedback = _feedback(document)
        if feedback is None:
            return None
        if feedback.get("kind") == "retry":
            print(
                f"  wrong: chose {feedback.get('chosen', '?')!r}; "
                "try again."
            )
            attempt = 2
            continue
        if feedback.get("kind") != "recognize":
            print("invalid Worker feedback")
            return None
        try:
            result = recognize_result_from_json(feedback.get("result"))
        except InvalidRequest as exc:
            print(f"invalid Worker feedback: {exc}")
            return None
        print(render_recognize_result(result))
        if result.correct:
            return "first" if attempt == 1 else "retry"
        return "revealed"


def _answer_interactively(
    app: cloud.CloudApp,
    bird: _SearchBird,
    view: ElementsCardView,
    seed: int,
    reverse_hebrew: bool,
    *,
    position: tuple[int, int] | None = None,
) -> tuple[ElementResult, ...] | None:
    print(
        render_card(
            view, reverse_hebrew=reverse_hebrew, position=position
        )
    )
    answers: dict[str, str] = {}
    for index, row in enumerate(view.rows):
        label = ", ".join(row.latin_forms)
        while True:
            try:
                raw = _read_line(f"  {label} [1-{len(row.options)}]: ")
            except _Up:
                print("card cancelled.")
                return None
            text = raw.strip()
            if text == "?":
                print(_E_HELP)
                print(
                    render_element_row(
                        view, index, reverse_hebrew=reverse_hebrew
                    )
                )
                continue
            query = _search_request(text)
            if query is not None:
                _search_mode(app, query, reverse_hebrew)
                print(
                    render_element_row(
                        view, index, reverse_hebrew=reverse_hebrew
                    )
                )
                continue
            try:
                number = int(text)
            except ValueError:
                print(
                    "enter an option number, /text to search, "
                    "? for help, or exit"
                )
                continue
            if not 1 <= number <= len(row.options):
                print(f"choose 1-{len(row.options)}")
                continue
            answers[row.element_id] = row.options[number - 1]
            break
    document = _grade_worker(
        app, bird, "E", seed, 1, choices=answers
    )
    feedback = _feedback(document)
    if feedback is None or feedback.get("kind") != "elements":
        if feedback is not None:
            print("invalid Worker feedback")
        return None
    try:
        results = element_results_from_json(feedback.get("results"))
    except InvalidRequest as exc:
        print(f"invalid Worker feedback: {exc}")
        return None
    print()
    print(render_element_results(view, results, reverse_hebrew=reverse_hebrew))
    return results


def _answer_typed(
    app: cloud.CloudApp,
    bird: _SearchBird,
    view: ConstructCardView | ProduceCardView,
    seed: int,
    reverse_hebrew: bool,
    help_text: str,
    *,
    position: tuple[int, int] | None = None,
) -> str | None:
    print(
        render_card(
            view,
            reverse_hebrew=reverse_hebrew,
            position=position,
        )
    )
    attempt = 1
    while True:
        try:
            raw = _read_line("  Latin: ")
        except _Up:
            print("card cancelled.")
            return None
        text = raw.strip()
        if text == "?":
            print(help_text)
            print(
                render_card(
                    view,
                    reverse_hebrew=reverse_hebrew,
                    position=position,
                )
            )
            continue
        query = _search_request(text)
        if query is not None:
            _search_mode(app, query, reverse_hebrew)
            print(
                render_card(
                    view,
                    reverse_hebrew=reverse_hebrew,
                    position=position,
                )
            )
            continue
        if not text:
            print(
                "type the Latin name, /text to search, "
                "? for help, or exit"
            )
            continue
        document = _grade_worker(
            app,
            bird,
            view.card_type.value,
            seed,
            attempt,
            response=text,
        )
        feedback = _feedback(document)
        if feedback is None:
            return None
        if feedback.get("kind") == "retry":
            print(
                f"  wrong: chose {feedback.get('response', '?')!r}; "
                "try again."
            )
            attempt = 2
            continue
        if feedback.get("kind") != "latin":
            print("invalid Worker feedback")
            return None
        try:
            result: LatinResult = latin_result_from_json(
                feedback.get("result")
            )
        except InvalidRequest as exc:
            print(f"invalid Worker feedback: {exc}")
            return None
        print(render_latin_result(result))
        if result.outcome == "correct":
            return "first" if attempt == 1 else "retry"
        if result.outcome == "near_miss":
            return "near_miss"
        return "revealed"


def _search_request(text: str) -> str | None:
    """Return a search query when text asks for search, else None."""
    stripped = text.strip()
    if stripped.startswith("/"):
        return stripped[1:].strip()
    first, _, rest = stripped.partition(" ")
    if first.lower() in _SEARCH_ALIASES:
        return rest.strip()
    return None


_DISPLAYED_NAME_FIELDS = {
    "species_id",
    "latin",
    "english",
    "hebrew",
    "family",
    "family_he",
}


def _match_text(text: _SearchText, reverse_hebrew: bool) -> str:
    if reverse_hebrew and text.field == "he":
        return text.text[::-1]
    return text.text


def _display_query(query: str, reverse_hebrew: bool) -> str:
    """Reverse Hebrew words so the query reads like the data it matched."""
    if not reverse_hebrew:
        return query
    return "".join(
        token[::-1]
        if any("֐" <= char <= "׿" for char in token)
        else token
        for token in re.split(r"(\s+)", query)
    )


def _name_match(reason: _SearchMatch, reverse_hebrew: bool) -> str:
    shown = [
        _match_text(text, reverse_hebrew)
        for text in reason.texts
        if text.field not in _DISPLAYED_NAME_FIELDS
    ]
    if not shown:
        return "name"
    return f"name (={', '.join(shown)})"


def _element_match(reason: _SearchMatch, reverse_hebrew: bool) -> str:
    shown = []
    for text in reason.texts:
        if text.field == "element_id":
            continue
        if (
            text.field == "display"
            and text.text.lower() == reason.element_id.lower()
        ):
            continue
        shown.append(_match_text(text, reverse_hebrew))
    if not shown:
        return reason.element_id
    return f"{reason.element_id} (={', '.join(shown)})"


def _render_matched(bird: _SearchBird, reverse_hebrew: bool) -> str:
    parts = []
    for reason in bird.matched:
        if reason.kind == "name":
            parts.append(_name_match(reason, reverse_hebrew))
        elif reason.kind == "element":
            parts.append(_element_match(reason, reverse_hebrew))
    return ", ".join(parts)


def _bird_count(count: int) -> str:
    return f"{count} bird" if count == 1 else f"{count} birds"


def _list_elements(
    elements: list[_SearchElement], query: str, reverse_hebrew: bool
) -> None:
    if not elements:
        return
    print()
    print(
        f"Elements matching "
        f"{_display_query(query, reverse_hebrew)!r} ({len(elements)})"
    )
    for element in elements:
        hebrew = element.he[::-1] if reverse_hebrew else element.he
        extra = []
        for text in element.matched:
            if text.field in ("element_id", "display"):
                continue
            if text.field in ("en", "he"):
                continue
            extra.append(_match_text(text, reverse_hebrew))
        suffix = f" (={', '.join(extra)})" if extra else ""
        print(
            f"  {element.element_id:<8} {element.en} · {hebrew}   "
            f"{element.theme} · {element.origin}   "
            f"{_bird_count(element.bird_count)}{suffix}"
        )


def _list_command(
    app: cloud.CloudApp, args: list[str], reverse_hebrew: bool
) -> None:
    query = " ".join(args).strip()
    results = _search_birds(app, query)
    if results is None:
        return
    birds = results.birds
    if not birds:
        if query:
            print(f"no birds match {_display_query(query, reverse_hebrew)!r}")
        else:
            print("no birds in the dataset")
        _list_elements(results.elements, query, reverse_hebrew)
        return

    count = f"{len(birds)} bird{'s' if len(birds) != 1 else ''}"
    if query:
        count += f" matching {_display_query(query, reverse_hebrew)!r}"
    print(count)
    show_matched = any(
        reason.kind == "element"
        or any(
            text.field not in _DISPLAYED_NAME_FIELDS
            for text in reason.texts
        )
        for bird in birds
        for reason in bird.matched
    )
    header = (
        f"{'species_id':<30} {'Latin':<30} {'English':<30} "
        f"{'Hebrew':<20} {'Family':<18} Hebrew family"
    )
    if show_matched:
        header += " matched"
    print(header)
    for bird in birds:
        hebrew = bird.hebrew or "-"
        family_he = bird.family_he or "-"
        if reverse_hebrew:
            hebrew = hebrew[::-1]
            family_he = family_he[::-1]
        row = (
            f"{bird.species_id:<30} {bird.latin:<30} "
            f"{bird.english:<30} {hebrew:<20} "
            f"{bird.family:<18} {family_he}"
        )
        if show_matched:
            row += f" {_render_matched(bird, reverse_hebrew)}"
        print(row)
    _list_elements(results.elements, query, reverse_hebrew)
