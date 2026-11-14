"""Small text client for inspecting cards during development.

It is deliberately thin: card content comes from ``cards.views`` and the text
renderer; this module only parses commands and prints the result.
"""

from __future__ import annotations

import atexit
import shlex
import sys
from pathlib import Path

from .cards.models import CardDescriptor, CardType, ElementsCardView
from .cards.text import render_card
from .cards.views import card_view
from .foundation.config import Config
from .foundation.dataset import Bird, Catalog, load_catalog
from .foundation.errors import DataError, NotFound, TrainerError

_COMMANDS = """\
Commands:
  [/ | list | find] <text>                     search birds, e.g. /acro
  [card L | L] <species> [--seed N]            show a Learn card
  [card E | E] <species> [--seed N] [--reveal] show an Elements card
  [help | ?]                                   show this message
  [quit | exit]                                leave the client

The search looks in species_id, Latin, English, Hebrew, family
and order. Every word must match somewhere; case is ignored. 
`/` with no text lists all birds.
Hebrew is reversed for terminals that cannot display RTL; 
start with --no-reverse-hebrew to print it unchanged.
"""


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
            raw = input("card> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        try:
            args = shlex.split(raw)
        except ValueError as exc:
            print(f"parse error: {exc}")
            continue
        if not args:
            continue
        if not _dispatch(catalog, args, reverse_hebrew):
            return 0


def _enable_line_editing() -> None:
    """Enable readline editing and persisted command history when available."""
    try:
        import readline
    except ImportError:
        return

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


def _dispatch(catalog: Catalog, args: list[str], reverse_hebrew: bool) -> bool:
    command = args[0].lower()
    if command in ("quit", "exit"):
        return False
    if command in ("help", "?"):
        print(_COMMANDS)
        return True
    if args[0].startswith("/"):
        query = " ".join((args[0][1:], *args[1:])).strip()
        _list_command(catalog, [query] if query else [], reverse_hebrew)
        return True
    if command in ("list", "find", "birds"):
        _list_command(catalog, args[1:], reverse_hebrew)
        return True
    if command == "card":
        _card_command(catalog, args[1:], reverse_hebrew)
        return True
    try:
        CardType(args[0].upper())
    except ValueError:
        print(f"unknown command: {args[0]!r}; type 'help'")
    else:
        _card_command(catalog, args, reverse_hebrew)
    return True


def _card_command(
    catalog: Catalog, args: list[str], reverse_hebrew: bool
) -> None:
    if len(args) < 2:
        print("usage: card L|E <species> [--seed N] [--reveal] (or L|E ...)")
        return

    try:
        card_type = CardType(args[0].upper())
    except ValueError:
        choices = ", ".join(card_type.value for card_type in CardType)
        print(f"unknown card type {args[0]!r}; choose {choices}")
        return

    species_words: list[str] = []
    seed = 0
    reveal = False
    index = 1
    while index < len(args):
        option = args[index]
        if option == "--seed" and index + 1 < len(args):
            try:
                seed = int(args[index + 1])
            except ValueError:
                print("--seed needs an integer")
                return
            index += 2
        elif option == "--reveal":
            reveal = True
            index += 1
        elif option.startswith("--"):
            print(f"unknown option: {option!r}")
            return
        else:
            species_words.append(option)
            index += 1

    species_text = " ".join(species_words).strip()
    if not species_text:
        print("usage: card L|E <species> [--seed N] [--reveal] (or L|E ...)")
        return

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
    return sorted(matches, key=lambda bird: (bird.family_order, bird.genus, bird.latin))


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
