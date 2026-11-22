"""Small text client for inspecting cards during development.

It is deliberately thin: card content comes from ``cards.views`` and the text
renderer; this module only parses commands, reads answers and prints results.
"""

from __future__ import annotations

import atexit
import secrets
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from .cards.grading import (
    ElementResult,
    grade_elements,
    grade_latin,
    grade_recognize,
)
from .cards.models import (
    CardDescriptor,
    CardType,
    CardView,
    ConstructCardView,
    ElementsCardView,
    LearnCardView,
    RecognizeCardView,
)
from .cards.text import (
    render_card,
    render_construct_result,
    render_element_results,
    render_element_row,
    render_recognize_result,
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
  /<text>                                       search birds, e.g. /acro
  list|find|birds|search <text>                 search birds, e.g. search acro
  card L|L|l <species|search>                   show a Learn card
  card E|E|e <species|search> [--seed N]        practise an Elements card
  card E|E|e <species|search> --answer "..."    grade an Elements card in one shot
  card E|E|e <species|search> --reveal          show an Elements card with answers
  card R|R|r <species|search> [--seed N]        practise a Recognize card
  card R|R|r <species|search> --answer "2"      grade a Recognize card in one shot
  card R|R|r <species|search> --reveal          show a Recognize card with the answer
  card C|C|c <species|search>                   practise a Construct card
  card C|C|c <species|search> --answer "..."    grade a Construct card in one shot
  card C|C|c <species|search> --reveal          show a Construct card with the answer
  help, ?                                       show this message
  quit, exit                                    leave the client

In the interactive client, a search opens search mode. Type text there to
search again; ? shows help; exit/quit/Ctrl-D/Esc (press Esc, then Enter)
goes one prompt up. A bare / opens search mode without listing every bird.

At an Elements prompt, enter an option number. Options stay within the shown
theme, which is a hint. Each interactive card gets a fresh option order;
--seed N reproduces one. /text and the search aliases are also accepted there
and return to the same element. One-shot commands are display-only unless
--answer is given.

A Recognize card shows the Hebrew name and asks for the matching Latin name.
A wrong choice lets you try once more; a second wrong reveals the answer.

A Construct card shows the Hebrew name and a scaffold: each Latin word or
part with its first letter, length and (for split parts) Hebrew gloss. Type
the full Latin name; case and spacing are ignored. A near miss shows the
exact spelling and moves on. A wrong answer gets one retry; the second wrong
reveals the answer.

<species|search> is the same query as /<text>. One match shows one card;
several matches run through all of them in search order. Press Enter between
cards; exit/quit/Ctrl-D/Esc stops the run. R runs skip birds without Hebrew;
E runs skip birds without split elements. A run is an ephemeral study tool,
not saved progress. --answer needs a single match; plain display or --reveal
prints every matching card.

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
            'usage: card L|E|R <species|search> [--seed N] '
            '[--reveal|--answer "1 2"] (or L|E|R ...)'
        )
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

    query = " ".join(species_words).strip()
    if query.startswith("/"):
        query = query[1:].strip()
    if not query:
        print(
            'usage: card L|E|R <species|search> [--seed N] '
            '[--reveal|--answer "1 2"] (or L|E|R ...)'
        )
        return

    if card_type not in (
        CardType.L,
        CardType.E,
        CardType.R,
        CardType.C,
    ):
        print(f"card type {card_type.value} is not implemented yet")
        return

    matches = _matching_birds(catalog, query)
    if not matches:
        print(f"bird {query!r} not found")
        return

    if answer_text is not None and len(matches) != 1:
        print(
            f"--answer needs a single match; "
            f"{len(matches)} birds match {query!r}"
        )
        return

    # The card layer is deterministic given a seed.  In the interactive client
    # a fresh seed gives the expected variety; --seed reproduces an exact card
    # or run.  One-shot and --answer keep seed 0 so the numbers match.
    if (
        interactive
        and not seed_given
        and card_type in (CardType.E, CardType.R)
        and answer_text is None
    ):
        seed = secrets.randbelow(1_000_000_000)

    if len(matches) == 1:
        _single_card(
            catalog,
            matches[0],
            card_type,
            seed,
            reverse_hebrew,
            interactive=interactive,
            reveal=reveal,
            answer_text=answer_text,
        )
        return

    _run_cards(
        catalog,
        card_type,
        query,
        matches,
        seed,
        reverse_hebrew,
        interactive=interactive,
        reveal=reveal,
    )


def _single_card(
    catalog: Catalog,
    bird: Bird,
    card_type: CardType,
    seed: int,
    reverse_hebrew: bool,
    *,
    interactive: bool,
    reveal: bool,
    answer_text: str | None,
) -> None:
    try:
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
    elif isinstance(view, RecognizeCardView):
        if answer_text is not None:
            _grade_recognize_text(
                catalog, view, answer_text, reverse_hebrew
            )
            return
        if interactive and not reveal:
            _answer_recognize(catalog, view, reverse_hebrew)
            return
    elif isinstance(view, ConstructCardView):
        if answer_text is not None:
            _grade_construct_text(
                bird, view, answer_text, reverse_hebrew
            )
            return
        if interactive and not reveal:
            _answer_construct(catalog, bird, view, reverse_hebrew)
            return

    if answer_text is not None:
        print("--answer is only for E, R and C cards")
        return

    element_answers: dict[str, str] = {}
    if isinstance(view, ElementsCardView) and reveal:
        element_answers = {
            row.element_id: catalog.element(row.element_id).he
            for row in view.rows
        }
    recognize_answers: tuple[str, ...] = ()
    if isinstance(view, RecognizeCardView) and reveal:
        recognize_answers = tuple(
            other.latin
            for other in catalog.birds_with_hebrew(view.hebrew)
        )
    print(
        render_card(
            view,
            reverse_hebrew=reverse_hebrew,
            reveal_elements=reveal,
            element_answers=element_answers,
            reveal_recognize=reveal,
            recognize_answers=recognize_answers,
            reveal_construct=reveal,
            construct_answer=bird.latin,
        )
    )


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
    catalog: Catalog,
    card_type: CardType,
    query: str,
    matches: list[Bird],
    seed: int,
    reverse_hebrew: bool,
    *,
    interactive: bool,
    reveal: bool,
) -> None:
    eligible, skipped, skip_reason = _eligible_birds(card_type, matches)
    if not eligible:
        suffix = (
            f" ({len(skipped)} skipped: {skip_reason})" if skipped else ""
        )
        print(
            f"no birds matching {query!r} can make a card of type "
            f"{card_type.value}{suffix}"
        )
        return

    print(_run_header(card_type, query, eligible, skipped, skip_reason))
    stats = _RunStats(total=len(eligible))
    stopped = False

    for offset, bird in enumerate(eligible):
        position = (offset + 1, stats.total)
        view = card_view(
            catalog,
            CardDescriptor(
                species_id=bird.species_id,
                card_type=card_type,
            ),
            seed=seed + offset,
        )

        if reveal:
            _print_revealed_card(
                catalog,
                view,
                reverse_hebrew,
                position,
                bird.latin,
            )
            print()
            continue

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
                catalog, view, reverse_hebrew, position=position
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
                catalog, view, reverse_hebrew, position=position
            )
            if outcome is None:
                stopped = True
                break
            _count_recognize(stats, outcome)
        elif isinstance(view, ConstructCardView):
            outcome = _answer_construct(
                catalog,
                bird,
                view,
                reverse_hebrew,
                position=position,
            )
            if outcome is None:
                stopped = True
                break
            _count_construct(stats, outcome)
        else:
            raise TypeError(f"cannot present {type(view).__name__}")

        stats.completed += 1
        if offset + 1 < stats.total and not _wait_for_next():
            stopped = True
            break

    if reveal:
        print(
            f"{card_type.value} run: {stats.total} cards "
            "(answers revealed)."
        )
        return
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


def _count_construct(stats: _RunStats, outcome: str) -> None:
    if outcome == "first":
        stats.first_try += 1
    elif outcome == "near_miss":
        stats.near_miss += 1
    elif outcome == "retry":
        stats.retry += 1
    else:
        stats.revealed += 1


def _eligible_birds(
    card_type: CardType, matches: list[Bird]
) -> tuple[list[Bird], list[Bird], str]:
    if card_type is CardType.R:
        eligible = [bird for bird in matches if bird.has_hebrew]
        skipped = [bird for bird in matches if not bird.has_hebrew]
        return eligible, skipped, "no Hebrew"
    if card_type is CardType.E:
        eligible = [bird for bird in matches if bird.has_parts]
        skipped = [bird for bird in matches if not bird.has_parts]
        return eligible, skipped, "no split elements"
    if card_type is CardType.C:
        eligible = [bird for bird in matches if bird.has_hebrew]
        skipped = [bird for bird in matches if not bird.has_hebrew]
        return eligible, skipped, "no Hebrew"
    return list(matches), [], ""


def _run_header(
    card_type: CardType,
    query: str,
    eligible: list[Bird],
    skipped: list[Bird],
    skip_reason: str,
) -> str:
    count = len(eligible)
    line = (
        f"{card_type.value} run: {count} "
        f"bird{'s' if count != 1 else ''} matching {query!r}"
    )
    if skipped:
        line += f" ({len(skipped)} skipped: {skip_reason})"
    return line


def _print_revealed_card(
    catalog: Catalog,
    view: CardView,
    reverse_hebrew: bool,
    position: tuple[int, int],
    construct_answer: str = "",
) -> None:
    element_answers: dict[str, str] = {}
    if isinstance(view, ElementsCardView):
        element_answers = {
            row.element_id: catalog.element(row.element_id).he
            for row in view.rows
        }
    recognize_answers: tuple[str, ...] = ()
    if isinstance(view, RecognizeCardView):
        recognize_answers = tuple(
            bird.latin for bird in catalog.birds_with_hebrew(view.hebrew)
        )
    print(
        render_card(
            view,
            reverse_hebrew=reverse_hebrew,
            reveal_elements=True,
            element_answers=element_answers,
            reveal_recognize=True,
            recognize_answers=recognize_answers,
            reveal_construct=True,
            construct_answer=construct_answer,
            position=position,
        )
    )


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
    elif card_type is CardType.C:
        print(
            f"C run complete: {stats.total} cards, "
            f"first try {stats.first_try}, near miss {stats.near_miss}, "
            f"retry {stats.retry}, revealed {stats.revealed}."
        )
    else:
        print(f"L run complete: {stats.total} cards.")


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


def _grade_recognize_text(
    catalog: Catalog,
    view: RecognizeCardView,
    answer_text: str,
    reverse_hebrew: bool,
) -> None:
    number = _parse_recognize_answer(answer_text, view)
    if number is None:
        return
    print(render_card(view, reverse_hebrew=reverse_hebrew))
    result = grade_recognize(
        catalog, view, view.options[number - 1].species_id
    )
    print()
    print(render_recognize_result(result))


def _parse_recognize_answer(
    text: str, view: RecognizeCardView
) -> int | None:
    parts = text.replace(",", " ").split()
    if len(parts) != 1:
        print(f"expected 1 answer, got {len(parts)}")
        return None
    try:
        number = int(parts[0])
    except ValueError:
        print(f"answer is not a number: {parts[0]!r}")
        return None
    if not 1 <= number <= len(view.options):
        print(f"answer must be between 1 and {len(view.options)}")
        return None
    return number


def _answer_recognize(
    catalog: Catalog,
    view: RecognizeCardView,
    reverse_hebrew: bool,
    *,
    position: tuple[int, int] | None = None,
) -> str | None:
    print(
        render_card(
            view, reverse_hebrew=reverse_hebrew, position=position
        )
    )
    wrong_attempts = 0
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
            _search_mode(catalog, query, reverse_hebrew)
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
        result = grade_recognize(
            catalog, view, view.options[number - 1].species_id
        )
        if result.correct:
            print(render_recognize_result(result))
            return "first" if wrong_attempts == 0 else "retry"
        wrong_attempts += 1
        if wrong_attempts == 1:
            print(f"  wrong: chose {result.chosen.latin!r}; try again.")
            continue
        print(render_recognize_result(result))
        return "revealed"


def _answer_interactively(
    catalog: Catalog,
    view: ElementsCardView,
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
    return results


def _grade_construct_text(
    bird: Bird,
    view: ConstructCardView,
    answer_text: str,
    reverse_hebrew: bool,
) -> None:
    print(render_card(view, reverse_hebrew=reverse_hebrew))
    result = grade_latin(bird.latin, answer_text)
    print()
    print(render_construct_result(result))


def _answer_construct(
    catalog: Catalog,
    bird: Bird,
    view: ConstructCardView,
    reverse_hebrew: bool,
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
    wrong_attempts = 0
    while True:
        try:
            raw = _read_line("  Latin: ")
        except _Up:
            print("card cancelled.")
            return None
        text = raw.strip()
        if text == "?":
            print(_C_HELP)
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
            _search_mode(catalog, query, reverse_hebrew)
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
        result = grade_latin(bird.latin, text)
        if result.outcome == "correct":
            print(render_construct_result(result))
            return "first" if wrong_attempts == 0 else "retry"
        if result.outcome == "near_miss":
            print(render_construct_result(result))
            return "near_miss"
        wrong_attempts += 1
        if wrong_attempts == 1:
            print(f"  wrong: chose {result.response!r}; try again.")
            continue
        print(render_construct_result(result))
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
