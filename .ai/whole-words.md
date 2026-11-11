# Whole-word etymology coverage

Status: open TODO. Not implemented.

## The issue

`data/in/etymology.md:635` marks `olivetorum` as a whole word:

```text
olivetorum = olivetorum
```

Jobling gives it a lexical meaning: “L. olivetorum of the olive groves
{olivetum olive grove}”. Because there is no split and no
`whole_names` entry, the L card and the book show no meaning for it. The
learner can see the “olive” connection but has nowhere to confirm it.

This is probably not one missing entry. The source currently has:

- 769 word entries;
- 475 entries with no `·` split;
- 294 split entries;
- 16 entries in `whole_names`.

So 459 whole-word entries have no whole-name note. Not all of them have a
lexical meaning worth showing — many are eponyms, unanalysable names or
deliberate “no useful gloss” cases — but the group is large enough to audit.

## Model distinction

- A **split** is for a word made of meaning-bearing elements, e.g.
  `Acro·cephalus`. Every segment must exist in the Elements table.
- A **whole-name note** is for a non-decomposed word with a known lexical
  meaning, e.g. `syriacus` = “Syrian”. It is displayed separately and does not
  add grey parts or element-index entries.
- `olivetorum` is genitive plural of `olivetum` (“olive grove”). Splitting it
  as `olivet·orum` would treat the inflectional ending `-orum` as a meaning
  element, which the current model avoids. It belongs in `whole_names`, not in
  `splits`.

## Next steps

1. Enumerate every whole-word entry (`word = word`) in
   `data/in/etymology.md`.
2. Check each against Jobling and record the lexical meaning, or mark it as
   having no useful gloss.
3. Add whole-name notes for the meaningful ones:
   ```text
   olivetorum | of the olive groves | <Hebrew gloss> | Jobling 2010
   ```
4. Rebuild `data/out/etymology.json` and verify the L card whole-name section
   and the book whole-name index.
5. Decide whether the audit also covers transparent compounds currently left
   whole, such as `dumetorum` and `maldivarum`.

## Files

- `data/in/etymology.md` — authoritative word splits and whole names.
- `data/src/pipeline/build_etymology.py` — validation and JSON output.
- `data/out/etymology.json` — installed `splits` and `whole_names`.
- `learn/src/trainer/cards/views.py` — `_whole_names()` builds the L-card notes.
- `book/src/make_pocket.py` — whole-name index.
