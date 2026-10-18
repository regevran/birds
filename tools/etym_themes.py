#!/usr/bin/env python3
"""SUPERSEDED: data/etymology.md is the authoritative source now.
This file is kept only as migration history; the builder no longer reads it.

Theme assignment for the word-element index.

Every element used by a split must appear in exactly one group below; the
builder checks coverage.  Order here is the order the groups print in, and
entries are sorted alphabetically inside each group.
"""

THEME_ORDER = [
    "Colour",
    "Body",
    "Size and shape",
    "Where it lives",
    "Food and behaviour",
    "Birds, beasts and people",
    "Word-building",
]

THEMES = {
    "Colour": [
        "aerugo", "albus", "argentum", "argus", "ater", "brunneus", "chloros",
        "chroa", "chrysos", "cinctus", "color", "cyanos", "erythros", "flavus",
        "fuligo", "fuscus", "glaucus", "griseus", "ignis", "leucos", "macula",
        "marmaros", "melas", "niger", "ochros", "percnos", "phaios", "phoenix",
        "polios", "pyrrhos", "rhodon", "roseus", "ruber", "rufus", "scotos",
        "spilos", "spodos", "xanthos",
    ],
    "Body": [
        "bombyx", "capillus", "cauda", "cephalus", "ceps", "cercos", "chlamys",
        "cilla", "cirrus", "cneme", "collare", "collis", "crumen", "dactylos",
        "dasy", "frons", "gaster", "gena", "gnathos", "gula", "haima", "lophos",
        "nota", "noton", "oideo", "onyx", "ophthalmos", "ops", "ous", "pechys",
        "phalacros", "phrys", "phthalmos", "pogon", "pous", "prymna", "pteron",
        "ptilon", "pyge", "ramphos", "rhis", "rhynchos", "rostrum", "squama",
        "stoma", "streptos", "tarsos", "thorax", "thrix", "torquatus", "ura",
    ],
    "Size and shape": [
        "acro", "acumen", "acutus", "angustus", "brachys", "brevis", "crassus",
        "curvus", "dicr", "eurys", "himas", "kalos", "leptos", "longus",
        "macros", "megas", "micros", "minutus", "oxys", "platys", "prion",
        "ptyon", "pycnos", "recurvus", "rhipis", "serra", "stenos", "tenuis",
    ],
    "Where it lives": [
        "ager", "ammos", "arena", "arundo", "arvum", "atilis", "boreas", "cola",
        "dendron", "eremos", "glarea", "hals", "helos", "hydor", "limne",
        "montis", "oceanus", "patria", "phyllon", "pratum", "rubus", "rus",
        "saxum", "schoinos", "teichos", "thalassa", "trogle",
    ],
    "Food and behaviour": [
        "acris", "apis", "baenus", "bapto", "bates", "capio", "caro", "carpos",
        "coccos", "copos", "coris", "cursor", "dacos", "dromos", "dytes", "edo",
        "ficus", "frux", "gelao", "hio", "ichthys", "kryptos", "lego", "locusta",
        "manes", "melis", "melos", "mota", "mulgus", "musca", "myia", "nektris",
        "nyx", "ostreum", "philos", "psaltes", "scopus", "tachys", "theres",
        "thraustes", "vorus",
    ],
    "Birds, beasts and people": [
        "aetos", "alauda", "alopex", "anser", "anthropos", "ardea", "bous",
        "buteo", "butio", "calandra", "capra", "carbo", "chelidon", "chen",
        "circos", "coccyx", "colius", "coloeus", "corax", "coryphos", "cygnus",
        "frater", "fringilla", "gallina", "gyps", "hierax", "lagos", "luscinia",
        "mergus", "naias", "netta", "otis", "parus", "peleia", "perdix",
        "phalaris", "progne", "psitta", "rodia", "spiza", "sterna",
    ],
    "Word-building": [
        "aceus", "ago", "aria", "arche", "aster", "atus", "bi", "cles", "con",
        "e", "ella", "ellus", "ensis", "eu", "fer", "ger", "hyper", "hypo",
        "ias", "ides", "ites", "ius", "monos", "nomos", "oides", "ola", "opsis",
        "osus", "panu", "peri", "semi", "sub", "tri", "ula",
    ],
}


def theme_of():
    out = {}
    for theme in THEME_ORDER:
        for eid in THEMES[theme]:
            if eid in out:
                raise SystemExit(f"element {eid} is in two themes "
                                 f"({out[eid]} and {theme})")
            out[eid] = theme
    return out
