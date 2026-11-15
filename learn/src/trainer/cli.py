"""Small text client for inspecting cards during development.

It is deliberately thin: card content comes from ``cards.views`` and the text
renderer; this module only parses commands, reads answers and prints results.
"""

from __future__ import annotations

import atexit
import secrets
import shlex
import sys
from pathlib import Path

from .cards.grading import grade_elements
from .cards.models import CardDescriptor, CardType, ElementsCardView
from .cards.text import (
    render_card,
    render_element_results,
    render_element_row,
)
from .cards.views import card_view
from .foundation.config import Config
from .foundation.dataset import Bird, Catalog, load_catalog
from .foundation.errors import DataError, NotFound, TrainerError

_SEARCH_ALIASES = ("list", "find", "birds", "search")
_ESCAPE = "\x1b"
_UP_SENTINEL = "<UP>"

_COMMANDS = """\
Commands:
  /<text>                             search birds, e.g. /acro
  list|find|birds|search <text>       same search
  card L <species>                    show a Learn card
  card E <species> [--seed N]         practise an Elements card
  card E <species> --answer "1 3 5 1" grade an Elements card in one shot
  card E <species> --reveal           show an Elements card with answers
  help, ?                             show this message
  quit, exit                          leave the client

In the interactive client, a search opens search mode. Type text there to
search again; ? shows help; exit/quit/Ctrl-D/Esc (press Esc, then Enter)
goes one prompt up. A bare / opens search mode without listing every bird.

At an Elements prompt, enter an option number. Options stay within the shown
theme, which is a hint. Each interactive card gets a fresh option order;
--seed N reproduces one. /text and the search aliases are also accepted there
and return to the same element. One-shot commands are display-only unless
--answer is given.

Species may be a species_id (acrocephalus-agricola), a Latin name
(Acrocephalus agricola), an English name or a unique fragment. Hebrew is
reversed for terminals that cannot display RTL; start with --no-reverse-hebrew
to print it unchanged.
"""

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


class _Up(Exception):
    """The user asked to go one prompt up."""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    reverse_hebrew = True
    if "--no-reverse-hebrew" in args:
        args.remove("--no-reverse-hebrew")
        reverse_hebrew = False

    try:
        catalog = _load_catalog()
    except DataError as exc:
        print(f"data error: {exc}", file=sys.stderr)
        return 2

    if args:
        _dispatch(catalog, args, reverse_hebrew)
        return 0
    return _interactive(catalog, reverse_hebrew)


def _load_catalog() -> Catalog:
    config = Config.default()
    return load_catalog(config.species_path, config.etymology_path)


def _interactive(catalog: Catalog, reverse_hebrew: bool) -> int:
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
                catalog, args, reverse_hebrew, interactive=True
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
    catalog: Catalog,
    args: list[str],
    reverse_hebrew: bool,
    *,
    interactive: bool = False,
) -> bool:
    command = args[0].lower()
    if command in ("quit", "exit"):
        return False
    if command in ("help", "?"):
        print(_COMMANDS)
        return True
    if args[0].startswith("/"):
        query = " ".join((args[0][1:], *args[1:])).strip()
        if interactive:
            _search_mode(catalog, query, reverse_hebrew)
        else:
            _list_command(catalog, [query] if query else [], reverse_hebrew)
        return True
    if command in _SEARCH_ALIASES:
        query = " ".join(args[1:]).strip()
        if interactive:
            _search_mode(catalog, query, reverse_hebrew)
        else:
            _list_command(catalog, args[1:], reverse_hebrew)
        return True
    if command == "card":
        _card_command(
            catalog, args[1:], reverse_hebrew, interactive=interactive
        )
        return True
    try:
        CardType(args[0].upper())
    except ValueError:
        print(f"unknown command: {args[0]!r}; type 'help'")
    else:
        _card_command(catalog, args, reverse_hebrew, interactive=interactive)
    return True


def _search_mode(
    catalog: Catalog, initial_query: str, reverse_hebrew: bool
) -> None:
    """Read-only bird search; every input is a query except ? and up."""
    if initial_query:
        _list_command(catalog, [initial_query], reverse_hebrew)
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
            _list_command(catalog, [query], reverse_hebrew)


def _card_command(
    catalog: Catalog,
    args: list[str],
    reverse_hebrew: bool,
    *,
    interactive: bool = False,
) -> None:
    if len(args) < 2:
        print(
            'usage: card L|E <species> [--seed N] [--reveal|--answer "1 2"] '
            "(or L|E ...)"
        )
        return

    try:
        card_type = CardType(args[0].upper())
    except ValueError:
        choices = ", ".join(card_type.value for card_type in CardType)
        print(f"unknown card type {args[0]!r}; choose {choices}")
        return

    species_words: list[str] = []
    seed = 0
    seed_given = False
    reveal = False
    answer_text: str | None = None
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
        elif option == "--reveal":
            reveal = True
            index += 1
        elif option == "--answer" and index + 1 < len(args):
            if answer_text is not None:
                print("--answer given more than once")
                return
            answer_text = args[index + 1]
            index += 2
        elif option == "--answer":
            print('--answer needs a value, e.g. --answer "1 2 3"')
            return
        elif option.startswith("--"):
            print(f"unknown option: {option!r}")
            return
        else:
            species_words.append(option)
            index += 1

    if answer_text is not None and reveal:
        print("choose either --answer or --reveal")
        return

    species_text = " ".join(species_words).strip()
    if not species_text:
        print(
            'usage: card L|E <species> [--seed N] [--reveal|--answer "1 2"] '
            "(or L|E ...)"
        )
        return

    # The card layer is deterministic given a seed.  In the interactive client
    # a fresh seed per card gives the expected variety; --seed reproduces an
    # exact card.  One-shot and --answer keep seed 0 so the numbers match.
    if (
        interactive
        and not seed_given
        and card_type is CardType.E
        and answer_text is None
    ):
        seed = secrets.randbelow(1_000_000_000)

    try:
        bird = _find_bird(catalog, species_text)
        view = card_view(
            catalog,
            CardDescriptor(
                species_id=bird.species_id,
                card_type=card_type,
            ),
            seed=seed,
        )
    except (NotFound, TrainerError) as exc:
        print(str(exc))
        return

    if isinstance(view, ElementsCardView):
        if answer_text is not None:
            _grade_answer_text(catalog, view, answer_text, reverse_hebrew)
            return
        if interactive and not reveal:
            _answer_interactively(catalog, view, reverse_hebrew)
            return

    if answer_text is not None:
        print("--answer is only for E cards")
        return

    answers: dict[str, str] = {}
    if isinstance(view, ElementsCardView) and reveal:
        answers = {
            row.element_id: catalog.element(row.element_id).he
            for row in view.rows
        }
    print(
        render_card(
            view,
            reverse_hebrew=reverse_hebrew,
            reveal_elements=reveal,
            element_answers=answers,
        )
    )


def _grade_answer_text(
    catalog: Catalog,
    view: ElementsCardView,
    answer_text: str,
    reverse_hebrew: bool,
) -> None:
    numbers = _parse_element_answers(answer_text, view)
    if numbers is None:
        return
    choices = {
        row.element_id: row.options[number - 1]
        for row, number in zip(view.rows, numbers)
    }
    print(render_card(view, reverse_hebrew=reverse_hebrew))
    results = grade_elements(catalog, view, choices)
    print()
    print(render_element_results(view, results, reverse_hebrew=reverse_hebrew))


def _parse_element_answers(
    text: str, view: ElementsCardView
) -> list[int] | None:
    parts = text.replace(",", " ").split()
    if len(parts) != len(view.rows):
        print(f"expected {len(view.rows)} answers, got {len(parts)}")
        return None
    numbers: list[int] = []
    for position, (part, row) in enumerate(zip(parts, view.rows), start=1):
        try:
            number = int(part)
        except ValueError:
            print(f"answer {position} is not a number: {part!r}")
            return None
        if not 1 <= number <= len(row.options):
            print(
                f"answer {position} must be between 1 and "
                f"{len(row.options)}"
            )
            return None
        numbers.append(number)
    return numbers


def _answer_interactively(
    catalog: Catalog,
    view: ElementsCardView,
    reverse_hebrew: bool,
) -> None:
    print(render_card(view, reverse_hebrew=reverse_hebrew))
    answers: dict[str, str] = {}
    for index, row in enumerate(view.rows):
        label = ", ".join(row.latin_forms)
        while True:
            try:
                raw = _read_line(f"  {label} [1-{len(row.options)}]: ")
            except _Up:
                print("card cancelled.")
                return
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
                _search_mode(catalog, query, reverse_hebrew)
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
    results = grade_elements(catalog, view, answers)
    print()
    print(render_element_results(view, results, reverse_hebrew=reverse_hebrew))


def _search_request(text: str) -> str | None:
    """Return a search query when text asks for search, else None."""
    stripped = text.strip()
    if stripped.startswith("/"):
        return stripped[1:].strip()
    first, _, rest = stripped.partition(" ")
    if first.lower() in _SEARCH_ALIASES:
        return rest.strip()
    return None


def _list_command(
    catalog: Catalog, args: list[str], reverse_hebrew: bool
) -> None:
    query = " ".join(args).strip()
    birds = _matching_birds(catalog, query)
    if not birds:
        if query:
            print(f"no birds match {query!r}")
        else:
            print("no birds in the dataset")
        return

    count = f"{len(birds)} bird{'s' if len(birds) != 1 else ''}"
    if query:
        count += f" matching {query!r}"
    print(count)
    print(
        f"{'species_id':<30} {'Latin':<30} {'English':<30} "
        f"{'Hebrew':<20} {'Family':<18} Hebrew family"
    )
    for bird in birds:
        hebrew = bird.hebrew or "-"
        family_he = bird.family_he or "-"
        if reverse_hebrew:
            if bird.hebrew:
                hebrew = hebrew[::-1]
            if bird.family_he:
                family_he = family_he[::-1]
        print(
            f"{bird.species_id:<30} {bird.latin:<30} "
            f"{bird.english:<30} {hebrew:<20} {bird.family:<18} "
            f"{family_he}"
        )


def _matching_birds(catalog: Catalog, text: str) -> list[Bird]:
    terms = text.casefold().split()
    if not terms:
        return list(catalog.birds)

    matches = []
    for bird in catalog.birds:
        haystack = " ".join(
            (
                bird.species_id,
                bird.latin,
                bird.english,
                bird.hebrew,
                bird.family,
                bird.family_he,
                bird.order,
            )
        ).casefold()
        if all(term in haystack for term in terms):
            matches.append(bird)
    return sorted(
        matches, key=lambda bird: (bird.family_order, bird.genus, bird.latin)
    )


def _find_bird(catalog: Catalog, text: str) -> Bird:
    text = text.strip()
    try:
        return catalog.bird(text.lower())
    except NotFound:
        pass

    folded = text.casefold()
    exact = [bird for bird in catalog.birds if bird.latin.casefold() == folded]
    if len(exact) == 1:
        return exact[0]

    matches = _matching_birds(catalog, text)
    if len(matches) == 1:
        return matches[0]
    if matches:
        names = ", ".join(bird.species_id for bird in matches[:8])
        if len(matches) > 8:
            names += f", ... ({len(matches)} total)"
        raise NotFound(f"ambiguous species {text!r}: {names}; use 'list {text}'")
    raise NotFound(f"bird {text!r} not found")
