# Text for the pocket edition
#
# This file is the source of every printed word in the pocket book and its
# cover. Edit the value after the colon. For a paragraph, use `key: |` and
# indent the lines below it by four spaces; the layout joins them with spaces
# and wraps them. Do not rename the keys. Lines beginning with `#` are notes
# for you, not printed.
#
# After editing, rebuild with:  ./book/build.sh
#
# Hebrew values: use Hebrew letters, spaces and the maqaf (־). Avoid ASCII
# punctuation inside Hebrew values; the Hebrew font does not carry it. The
# comma and full stop in the dedication are added by the layout.
#
# If you change the author's name, also update `rights` below.
# `logo_credit` above is used on the copyright page.

## book
# Title page (page i) and the title block on the cover.

title_he: ציפורי ישראל
title_en: BIRDS OF ISRAEL
subtitle_he: שמות לטיניים ומשמעותם
subtitle_en: Latin names and their meanings
edition: First edition · 2026
author: Ran Regev
logo_credit: Noa Shvartsun Regev

## dedication
# The dedication page (page iii), after the copyright page. Two lines.

line1: לשאול,
line2: שבכלל לא צריך את המדריך הזה.

## copyright
# The copyright page (page ii), on the back of the title page.

rights: © 2026 Ran Regev. All rights reserved.
sources_1: |
    Species list and Hebrew names compiled from publicly available sources,
    including the English and Hebrew Wikipedias. Etymologies after James A.
    Jobling, Helm Dictionary of Scientific Bird Names (2010).
sources_2: |
    Sequence of orders and families follows the Clements Checklist of Birds
    of the World (2022), as presented in the Wikipedia list of birds of Israel.
disclaimer: |
    This is a study aid, not a field identification guide. Records should be
    verified against the official checklist of the birds of Israel.
printed_en: Printed in Israel
printed_he: נדפס בישראל
typeset: Typeset in Noto Sans Mono and Droid Sans Hebrew.

## contents
# The contents page (page iv) in the front matter.

heading_en: Contents
heading_he: תוכן
section_list: The list (taxonomic order)
section_hebrew: Hebrew name index
section_elements: Index of word elements
column_family: FAMILY (A–Z)
column_page: PAGE

## key
# "How to use this book" (page v), the last front-matter page.

heading_en: How to use this book
heading_he: איך להשתמש בספר
intro_1: |
    Families are listed in taxonomic order; within a family, genera and then
    species are alphabetical. Latin is on the left, English in the middle,
    Hebrew on the right.
intro_2: |
    A grey part of a Latin name has an entry in the index of word elements at
    the back; a raised dot marks the joint. In the index, a leading dash marks
    an element that ends a name, and a trailing dash one that begins it. In
    Chroico·cephalus, chroico- begins the name and -cephalus ends it.
example_latin: Erithacus rubecula
example_gloss: rubec = red      -ula = little
markers_intro: Markers follow a Hebrew name, in parentheses:
legend_a: Accidental — a species that rarely or accidentally occurs in Israel
legend_i: |
    Introduced — a species introduced to Israel as a consequence, direct or
    indirect, of human actions
legend_ex: |
    Extirpated — a species that no longer occurs in Israel although
    populations exist elsewhere
legend_x: Extinct — a species or subspecies that no longer exists
legend_none: No marker: a commonly occurring native species
markers_note: |
    Markers flag exceptions only; an unmarked species is simply one that falls
    into none of these categories. Season and abundance are not encoded here.
    In the Hebrew name index, the number is the page in the list.
order_heading_en: A note on the order of birds
order_heading_he: הערה על מיון הציפורים בספר
order_note_1: |
    The list follows the taxonomic sequence of the Clements Checklist (2022).
    Orders and families sit in the order used by field guides and checklists,
    so related groups are together.
order_note_2: |
    For searching, the contents lists every family A–Z, the Hebrew name index
    lists every species, and the word-element index is alphabetical within
    each theme.

## hebrew_index
# Header of the Hebrew name index (pages 47–54).

heading_en: Hebrew name index
heading_he: מפתח שמות עבריים
subtitle: |
    Alphabetical by Hebrew letter; numbers are pages in the list.
column_page: PAGE
column_name: שם עברי

## element_index
# Header of the index of word elements (pages 55–65).

heading_en: Index of word elements
heading_he: מפתח מרכיבי השמות
subtitle: |
    Grey in the book marks an element listed here; a hyphen shows where it
    attaches. 
column_element: ELEMENT
column_english: ENGLISH
column_hebrew: HEBREW

## notes
# The ruled notes page (page 66) at the end of the book.

heading_en: Notes
heading_he: רשימות

## labels
# Small recurring labels.

continued: continued

## cover
# The cover, front and back. The example blocks are enclosed in a light cream
# frame with an ochre border on both panels; all example information — family,
# names, word elements — is inside the frame. The birds — the robin on the
# front, the Namaqua dove and Eurasian nightjar on the back — are drawn from
# the species data and the etymology; their word elements form a separate
# left-aligned list inside the frame. This section carries the blurb and the
# footer. The counts in front_footer need updating if the species list changes.

front_footer: 565 species · 84 families · 13 word themes
back_subtitle: A pocket companion for bird lovers
back_para_1: |
    565 species in 84 families, with Latin, English and Hebrew names, and the
    meaning of every Latin part.
back_para_2: |
    Grey marks the parts you can look up in the index of word elements. 
    Hebrew index for bird names is included.
