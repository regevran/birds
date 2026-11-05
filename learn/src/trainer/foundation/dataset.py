"""Load, validate and index the shared bird dataset.

The dataset layer is the single source of truth for species and etymology
entities. Card and lifecycle layers compose these objects; they must not
redefine birds or elements.

The loader validates structure and cross-references. It does not assert exact
row counts; the tests do that against the current data release.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .errors import DataError, NotFound

STATUS_CATEGORIES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "": ("regular",),
        "I": ("introduced",),
        "A": ("accidental",),
        "Ex": ("historical",),
        "Ex/A": ("historical", "accidental"),
        "X": ("extinct",),
    }
)

_SPECIES_REQUIRED = {
    "latin",
    "genus",
    "epithet",
    "english",
    "family",
    "family_he",
    "family_order",
    "order",
    "status",
    "hebrew",
    "flags",
}
_ETYMOLOGY_REQUIRED = {"elements", "splits", "whole_names", "themes"}
_ELEMENT_REQUIRED = {"en", "he", "origin", "theme", "display", "forms"}
_WHOLE_NAME_REQUIRED = {"en", "he", "source"}


@dataclass(frozen=True)
class SplitPart:
    """One surface form and the element it represents.

    Examples below are the ``Acro`` part of ``Acrocephalus``.
    """

    surface: str  # "Acro"
    element_id: str  # "acro"


@dataclass(frozen=True)
class Element:
    """A Latin word element and its meanings.

    Examples below use the ``cola`` element from ``agricola``.
    """

    element_id: str  # "cola"
    en: str  # "dweller"
    he: str  # "שוכן"
    origin: str  # "Latin"
    theme: str  # "Behaviour"
    display: str  # "cola"
    forms: tuple[str, ...]  # ("cola", "cula")


@dataclass(frozen=True)
class WholeName:
    """A name with a known meaning that is not split into elements.

    Examples below use the ``Thalasseus`` genus.
    """

    en: str  # "fisherman, from Greek thalassa (sea)"
    he: str  # "דייג"
    source: str  # "Jobling 2010"


@dataclass(frozen=True)
class Bird:
    """A canonical species record loaded from the shared dataset.

    All field examples below are one bird: ``Acrocephalus agricola``.
    """

    species_id: str  # "acrocephalus-agricola"
    latin: str  # "Acrocephalus agricola"
    genus: str  # "Acrocephalus"
    epithet: str  # "agricola"
    english: str  # "Paddyfield warbler"
    hebrew: str  # "קנית אורז"; "" when the species has no Hebrew name
    family: str  # "Acrocephalidae"
    family_he: str  # "קניתיים"; "" when the family has no Hebrew name
    family_order: int  # 60 (1..84; first appearance in the source order)
    order: str  # "Passeriformes"
    status: str  # "A"; possible: "", "I", "A", "Ex", "Ex/A", "X"
    status_categories: tuple[str, ...]  # ("accidental",)
    flags: tuple[str, ...]  # (); or ("no-hebrew",), ("no-family-hebrew",), ("family-hebrew-unverified",)
    genus_parts: tuple[SplitPart, ...]  # (SplitPart("Acro", "acro"), SplitPart("cephalus", "cephalus"))
    epithet_parts: tuple[SplitPart, ...]  # (SplitPart("agri", "agri"), SplitPart("cola", "cola"))

    @property
    def has_hebrew(self) -> bool:
        return bool(self.hebrew)

    @property
    def has_parts(self) -> bool:
        return bool(self.genus_parts or self.epithet_parts)

    @property
    def ringer_key(self) -> str:
        """Display label: first 3 letters of genus + first 3 of epithet.

        Collisions such as CURMEL are not resolved here; the ringer-key rule
        is still an open item in ``learn/TODO.md``.
        """
        return f"{self.genus[:3]}{self.epithet[:3]}".upper()

    def parts_for(self, word: str) -> tuple[SplitPart, ...]:
        if word == self.genus:
            return self.genus_parts
        if word == self.epithet:
            return self.epithet_parts
        return ()


@dataclass(frozen=True)
class Catalog:
    """The loaded dataset and its lookup indexes.

    Comments show the key type and one example value.
    """

    birds: tuple[Bird, ...]  # all 565 birds, in source order
    by_id: Mapping[str, Bird]  # "acrocephalus-agricola" -> Bird
    by_family: Mapping[str, tuple[Bird, ...]]  # "Acrocephalidae" -> its birds
    by_order: Mapping[str, tuple[Bird, ...]]  # "Passeriformes" -> its birds
    by_genus: Mapping[str, tuple[Bird, ...]]  # "Acrocephalus" -> its birds
    by_hebrew: Mapping[str, tuple[Bird, ...]]  # "קנית אורז" -> birds; empty names omitted
    by_status: Mapping[str, tuple[Bird, ...]]  # "accidental" -> birds; "Ex/A" appears in two groups
    elements: Mapping[str, Element]  # "cephalus" -> Element
    elements_by_form: Mapping[str, tuple[Element, ...]]  # "cephala" -> elements using that form
    splits: Mapping[str, tuple[SplitPart, ...]]  # "Acrocephalus" -> its SplitParts
    whole_names: Mapping[str, WholeName]  # "Thalasseus" -> WholeName
    themes: tuple[str, ...]  # ("Colour", "Body", "Size", ...)
    data_version: str  # "sha256:<64 hex characters>"

    def bird(self, species_id: str) -> Bird:
        try:
            return self.by_id[species_id]
        except KeyError:
            raise NotFound(f"bird {species_id!r}") from None

    def element(self, element_id: str) -> Element:
        try:
            return self.elements[element_id]
        except KeyError:
            raise NotFound(f"element {element_id!r}") from None

    def parts_for(self, word: str) -> tuple[SplitPart, ...]:
        return self.splits.get(word, ())

    def family(self, name: str) -> tuple[Bird, ...]:
        return self.by_family.get(name, ())

    def order(self, name: str) -> tuple[Bird, ...]:
        return self.by_order.get(name, ())

    def genus(self, name: str) -> tuple[Bird, ...]:
        return self.by_genus.get(name, ())

    def birds_with_hebrew(self, hebrew: str) -> tuple[Bird, ...]:
        return self.by_hebrew.get(hebrew, ())

    def elements_for_form(self, form: str) -> tuple[Element, ...]:
        return self.elements_by_form.get(form.lower(), ())


def load_catalog(species_path: Path, etymology_path: Path) -> Catalog:
    """Load both data files and return a validated, indexed :class:`Catalog`."""
    species_raw = _read_json(species_path, "species")
    etymology_raw = _read_json(etymology_path, "etymology")

    if not isinstance(species_raw, list):
        raise DataError(f"{species_path}: top-level value must be a list")
    if not isinstance(etymology_raw, dict):
        raise DataError(f"{etymology_path}: top-level value must be an object")

    elements, splits, whole_names, themes = _load_etymology(etymology_raw)
    birds = tuple(
        _build_bird(record, splits, index)
        for index, record in enumerate(species_raw)
    )
    _validate_birds(birds)

    return Catalog(
        birds=birds,
        by_id=MappingProxyType({bird.species_id: bird for bird in birds}),
        by_family=_group_by(birds, lambda bird: bird.family),
        by_order=_group_by(birds, lambda bird: bird.order),
        by_genus=_group_by(birds, lambda bird: bird.genus),
        by_hebrew=_group_hebrew(birds),
        by_status=_group_status(birds),
        elements=elements,
        elements_by_form=_group_elements_by_form(elements),
        splits=splits,
        whole_names=whole_names,
        themes=themes,
        data_version=_data_version(species_raw, etymology_raw),
    )


def _read_json(path: Path, label: str) -> Any:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise DataError(f"cannot read {label} data at {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DataError(f"invalid JSON in {label} data at {path}: {exc}") from exc


def _object(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise DataError(f"{where} must be an object")
    return value


def _array(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise DataError(f"{where} must be an array")
    return value


def _text(value: Any, where: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise DataError(f"{where} must be a string")
    if not allow_empty and not value.strip():
        raise DataError(f"{where} must not be empty")
    return value


def _integer(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DataError(f"{where} must be an integer")
    return value


def _string_list(value: Any, where: str) -> tuple[str, ...]:
    items = _array(value, where)
    return tuple(
        _text(item, f"{where}[{index}]") for index, item in enumerate(items)
    )


def _load_etymology(
    raw: Mapping[str, Any],
) -> tuple[
    Mapping[str, Element],
    Mapping[str, tuple[SplitPart, ...]],
    Mapping[str, WholeName],
    tuple[str, ...],
]:
    for key in _ETYMOLOGY_REQUIRED:
        if key not in raw:
            raise DataError(f"etymology: missing key {key!r}")

    themes = _string_list(raw["themes"], "etymology.themes")
    if not themes:
        raise DataError("etymology.themes must not be empty")
    if len(set(themes)) != len(themes):
        raise DataError("etymology.themes contains duplicates")
    theme_set = set(themes)

    elements: dict[str, Element] = {}
    for element_id, entry in _object(
        raw["elements"], "etymology.elements"
    ).items():
        where = f"element {element_id!r}"
        element_id = _text(element_id, "element id")
        entry = _object(entry, where)
        for key in _ELEMENT_REQUIRED:
            if key not in entry:
                raise DataError(f"{where}: missing key {key!r}")
        theme = _text(entry["theme"], f"{where}.theme")
        if theme not in theme_set:
            raise DataError(f"{where}.theme {theme!r} is not in etymology.themes")
        forms = _string_list(entry["forms"], f"{where}.forms")
        if not forms:
            raise DataError(f"{where}.forms must not be empty")
        elements[element_id] = Element(
            element_id=element_id,
            en=_text(entry["en"], f"{where}.en"),
            he=_text(entry["he"], f"{where}.he"),
            origin=_text(entry["origin"], f"{where}.origin"),
            theme=theme,
            display=_text(entry["display"], f"{where}.display"),
            forms=forms,
        )
    if not elements:
        raise DataError("etymology.elements must not be empty")

    splits: dict[str, tuple[SplitPart, ...]] = {}
    for word, raw_parts in _object(
        raw["splits"], "etymology.splits"
    ).items():
        word = _text(word, "split word")
        parts_raw = _array(raw_parts, f"split {word!r}")
        if not parts_raw:
            raise DataError(f"split {word!r} must not be empty")
        parts: list[SplitPart] = []
        for index, part in enumerate(parts_raw):
            where = f"split {word!r}[{index}]"
            if not isinstance(part, list) or len(part) != 2:
                raise DataError(f"{where} must be [surface, element_id]")
            surface = _text(part[0], f"{where}.surface")
            element_id = _text(part[1], f"{where}.element_id")
            if element_id not in elements:
                raise DataError(
                    f"{where}: unknown element id {element_id!r}"
                )
            parts.append(SplitPart(surface=surface, element_id=element_id))
        joined = "".join(part.surface for part in parts)
        if joined.lower() != word.lower():
            raise DataError(
                f"split {word!r} reassembles to {joined!r}, not {word!r}"
            )
        splits[word] = tuple(parts)
    if not splits:
        raise DataError("etymology.splits must not be empty")

    whole_names: dict[str, WholeName] = {}
    for word, entry in _object(
        raw["whole_names"], "etymology.whole_names"
    ).items():
        word = _text(word, "whole-name word")
        where = f"whole name {word!r}"
        entry = _object(entry, where)
        for key in _WHOLE_NAME_REQUIRED:
            if key not in entry:
                raise DataError(f"{where}: missing key {key!r}")
        whole_names[word] = WholeName(
            en=_text(entry["en"], f"{where}.en"),
            he=_text(entry["he"], f"{where}.he"),
            source=_text(entry["source"], f"{where}.source"),
        )

    return (
        MappingProxyType(elements),
        MappingProxyType(splits),
        MappingProxyType(whole_names),
        themes,
    )


def _build_bird(
    record: Any,
    splits: Mapping[str, tuple[SplitPart, ...]],
    index: int,
) -> Bird:
    where = f"species[{index}]"
    record = _object(record, where)
    for key in _SPECIES_REQUIRED:
        if key not in record:
            raise DataError(f"{where}: missing key {key!r}")

    latin = _text(record["latin"], f"{where}.latin")
    genus = _text(record["genus"], f"{where}.genus")
    epithet = _text(record["epithet"], f"{where}.epithet")
    if not (genus.isascii() and genus.isalpha()):
        raise DataError(f"{where}.genus must be ASCII letters")
    if not (epithet.isascii() and epithet.isalpha()):
        raise DataError(f"{where}.epithet must be ASCII letters")
    if latin != f"{genus} {epithet}":
        raise DataError(
            f"{where}.latin {latin!r} does not match "
            f"{genus!r} + {epithet!r}"
        )

    hebrew = _text(record["hebrew"], f"{where}.hebrew", allow_empty=True)
    family_he = _text(
        record["family_he"], f"{where}.family_he", allow_empty=True
    )
    status = _text(record["status"], f"{where}.status", allow_empty=True)
    if status not in STATUS_CATEGORIES:
        raise DataError(f"{where}.status {status!r} is not a known status")

    flags = _string_list(record["flags"], f"{where}.flags")
    if len(set(flags)) != len(flags):
        raise DataError(f"{where}.flags contains duplicates")
    if ("no-hebrew" in flags) != (not hebrew):
        raise DataError(
            f"{where}: 'no-hebrew' flag must be present exactly when "
            "hebrew is empty"
        )
    if ("no-family-hebrew" in flags) != (not family_he):
        raise DataError(
            f"{where}: 'no-family-hebrew' flag must be present exactly when "
            "family_he is empty"
        )
    if "family-hebrew-unverified" in flags and family_he:
        raise DataError(
            f"{where}: 'family-hebrew-unverified' cannot accompany a "
            "non-empty family_he"
        )

    family_order = _integer(record["family_order"], f"{where}.family_order")
    if family_order <= 0:
        raise DataError(f"{where}.family_order must be positive")

    species_id = f"{genus.lower()}-{epithet.lower()}"
    return Bird(
        species_id=species_id,
        latin=latin,
        genus=genus,
        epithet=epithet,
        english=_text(record["english"], f"{where}.english"),
        hebrew=hebrew,
        family=_text(record["family"], f"{where}.family"),
        family_he=family_he,
        family_order=family_order,
        order=_text(record["order"], f"{where}.order"),
        status=status,
        status_categories=STATUS_CATEGORIES[status],
        flags=flags,
        genus_parts=splits.get(genus, ()),
        epithet_parts=splits.get(epithet, ()),
    )


def _validate_birds(birds: tuple[Bird, ...]) -> None:
    if not birds:
        raise DataError("species data must not be empty")

    seen_ids: set[str] = set()
    seen_latin: set[str] = set()
    family_orders: dict[str, int] = {}
    family_he: dict[str, str] = {}
    family_order_of: dict[str, str] = {}

    for bird in birds:
        if bird.species_id in seen_ids:
            raise DataError(f"duplicate species id {bird.species_id!r}")
        seen_ids.add(bird.species_id)
        if bird.latin in seen_latin:
            raise DataError(f"duplicate Latin name {bird.latin!r}")
        seen_latin.add(bird.latin)

        previous_order = family_orders.setdefault(
            bird.family, bird.family_order
        )
        if previous_order != bird.family_order:
            raise DataError(
                f"family {bird.family!r} has inconsistent family_order"
            )
        previous_he = family_he.setdefault(bird.family, bird.family_he)
        if previous_he != bird.family_he:
            raise DataError(
                f"family {bird.family!r} has inconsistent family_he"
            )
        previous_taxon_order = family_order_of.setdefault(
            bird.family, bird.order
        )
        if previous_taxon_order != bird.order:
            raise DataError(f"family {bird.family!r} has inconsistent order")

    orders = sorted(set(family_orders.values()))
    if orders != list(range(1, len(orders) + 1)):
        raise DataError(
            "family_order values must be contiguous starting at 1"
        )


def _group_by(
    birds: tuple[Bird, ...],
    key: Callable[[Bird], str],
) -> Mapping[str, tuple[Bird, ...]]:
    groups: dict[str, list[Bird]] = defaultdict(list)
    for bird in birds:
        groups[key(bird)].append(bird)
    return MappingProxyType(
        {name: tuple(items) for name, items in groups.items()}
    )


def _group_hebrew(birds: tuple[Bird, ...]) -> Mapping[str, tuple[Bird, ...]]:
    groups: dict[str, list[Bird]] = defaultdict(list)
    for bird in birds:
        if bird.hebrew:
            groups[bird.hebrew].append(bird)
    return MappingProxyType(
        {name: tuple(items) for name, items in groups.items()}
    )


def _group_status(birds: tuple[Bird, ...]) -> Mapping[str, tuple[Bird, ...]]:
    groups: dict[str, list[Bird]] = defaultdict(list)
    for bird in birds:
        for category in bird.status_categories:
            groups[category].append(bird)
    return MappingProxyType(
        {name: tuple(items) for name, items in groups.items()}
    )


def _group_elements_by_form(
    elements: Mapping[str, Element],
) -> Mapping[str, tuple[Element, ...]]:
    groups: dict[str, list[Element]] = defaultdict(list)
    for element in elements.values():
        for form in element.forms:
            key = form.lower()
            if element not in groups[key]:
                groups[key].append(element)
    return MappingProxyType(
        {name: tuple(items) for name, items in groups.items()}
    )


def _data_version(species_raw: Any, etymology_raw: Any) -> str:
    payload = json.dumps(
        [species_raw, etymology_raw],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


__all__ = [
    "Bird",
    "Catalog",
    "Element",
    "SplitPart",
    "STATUS_CATEGORIES",
    "WholeName",
    "load_catalog",
]
