# Surface form vs index entry: search mismatches

## The problem

The book prints a grey segment; the reader looks for that segment in the index.
If the index entry is filed under a differently-spelled form, the alphabetical
search fails. This is most serious when the **first letter differs**, because
the entry is then in a completely different part of the index.

Sweep: for every segment of every split, compare the printed surface with the
element's display form and measure the common prefix.

## What the sweep found (before the fix)

### Blocking — different first letter

| Index entry | Printed in book | Example |
|---|---|---|
| `aetus` (eagle) | `eetus` | Halia**eetus** |
| `cephalus` (head) | `phala` | Buce**phala** |
| `cephalus` (head) | `phalus` | Poice**phalus** |
| `hiera` (hawk) | `erax` | Meli**erax** |
| `hinus` (nose) | `rhis` | mono**rhis** |
| `netta` (duck) | `itta` | Melan**itta** |
| `pterus` (wing) | `opterus` | percn**opterus** |
| `pus` (foot) | `opus` | Haemat**opus**, Himant**opus**, Phalar**opus** |

### Hard — same first letter, different second

| Index entry | Printed | Example | Cause |
|---|---|---|---|
| `cola` (dweller) | `cula` | hiati**cula** | o → u |
| `limno` (marsh) | `Lymno` | **Lymno**cryptes | Greek y transliteration |
| `phaeus` (dusky) | `Poice` | **Poice**phalus | phaios contracts to poice- |
| `pus` (foot) | `pes` | alaudi**pes**, brevi**pes** | Latin *pes* and Greek *pous* are different roots |
| `rhynchos` (bill) | `Rynch` | **Rynch**ops | rhynchos vs rynchos |

### Nearby — same first two letters

`atri`/`atro`/`atra` under `ater`; `ata` under `atus`; `Bur` under `buce`;
`Chlidon` under `chelidon`; `ura`/`uros` under `urus`.

## Resolution

The index now has **one row per surface form**, alphabetically placed, with the
same gloss. A form that is not the display form is no longer hidden inside
another entry:

```
-pes    foot        alaudipes, brevipes, carneipes, flavipes
-pus    foot        Chloropus, Oxyura ...
-opus   foot        Haematopus, Himantopus, Phalaropus
-phalus head        Poicephalus
-phala  head        Bucephala
-cephalus head      Acrocephalus, Chroicocephalus ...
-rhis   nose        monorhis
-hinus  nose        Burhinus
-itta   duck        Melanitta
-netta  duck        Marmaronetta, Netta
-eetus  eagle       Haliaeetus
-aetus  eagle       Circaetus, Gypaetus, Hieraaetus ...
poice-  dusky       Poicephalus
-phaeus dusky       Leucophaeus
phaeo-  dusky       phaeopus
lymno-  marsh       Lymnocryptes
limno-  marsh       Limnodromus
rynch-  bill        Rynchops
-rhynchos bill      erythrorhyncha, megarhynchos
```

This raised the index from 308 element rows (3 pages) to 380 form rows (4
pages). Both editions were rebuilt:

- `out/israel_birds_by_family_etymology.pdf` — 22 pages
- `out/israel_birds_by_family_regular_etymology.pdf` — 19 pages
