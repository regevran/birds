# Text for the pocket edition
#
# This file is the source of every printed word in the pocket book and its
# cover. Edit the value after the colon. For a paragraph, use `key: |` and
# indent the lines below it by four spaces; the layout joins them with spaces
# and wraps them. End a line with a backslash (\) to force a line break. Do not
# rename the keys. Lines beginning with `#` are notes
# for you, not printed.
#
# After editing, rebuild with:  ./render.sh
#
# Hebrew values may contain ASCII punctuation, digits and Latin names: the
# layout draws those from the Latin font and orders the line right to left.
# Use the maqaf (־) and the Hebrew geresh/gershayim (׳ / ״) inside Hebrew words.
#
# Inside a `|` block, a line `כותרת: X` starts a section title (the marker is
# not printed), and a line beginning with `- ` is a bullet. A wrapped bullet
# may continue on the next line. `**x**` marks one bold character.
#
# The interior is Hebrew; the cover is Hebrew and Latin.

## book
# The interior title page (page i) and the cover.

title_he: ציפורי ישראל
subtitle_he: שמות לטיניים ומשמעותם
edition_he: מהדורה שנייה · 2026
author_he: רן רגב
author: Ran Regev
logo_credit: נועה שוורצון רגב

# Cover only.
title_lat: AVES ISRAELIS
subtitle_lat: Nomina Latina eorumque significationes
edition_lat: Editio secunda · MMXXVI

## dedication
# The dedication page (page iii), after the copyright page. Two lines.

line1: לשאול,
line2: שבזכות הגזר בכלל לא צריך את המדריך הזה.

## copyright
# The copyright page (page ii), on the back of the title page.

rights: © 2026 רן רגב. כל הזכויות שמורות.
sources_1: |
    רשימת המינים והשמות העבריים נאספה ממקורות פומביים, ובכללם ויקיפדיה
    באנגלית ובעברית. האטימולוגיות על פי ג׳יימס א׳ ג׳ובלינג, מילון הלם
    לשמות מדעיים של ציפורים (2010).
sources_1_en: |
    Species list and Hebrew names compiled from publicly available sources,
    including the English and Hebrew Wikipedias. Etymologies after James A.
    Jobling, Helm Dictionary of Scientific Bird Names (2010).
sources_2: |
    סדר הסדרות והמשפחות עוקב אחר רשימת הציפורים של העולם של קלמנטס
    (2022), כפי שהיא מוצגת ברשימת הציפורים של ישראל בוויקיפדיה.
sources_2_en: |
    Sequence of orders and families follows the Clements Checklist of Birds
    of the World (2022), as presented in the Wikipedia list of birds of Israel.
disclaimer: |
    זהו עזר לימוד, ולא מדריך לזיהוי בשדה. יש לאמת תצפיות מול הרשימה
    הרשמית של ציפורי ישראל.
printed_he: נדפס בישראל
logo_label: לוגו:
typeset: |
    הורכב בגופנים Noto Sans Mono ו־Droid Sans Hebrew.

## contents
# The contents page (page iv) in the front matter.

heading_he: תוכן
section_list: הרשימה (סדר טקסונומי)
section_hebrew: מפתח שמות עבריים
section_elements: מפתח מרכיבי השמות

## key
# "How to use this book" (page v), the last front-matter page.

heading_he: איך להשתמש בספר
intro_1: |
    כותרת: סדר
    - הרשימה טקסונומית
    - המשפחות מסודרות לפי הסדר הטקסונומי; בתוך כל משפחה, הסוגים ואחר כך
    המינים מסודרים לפי סדר אלפביתי
    - הלטינית משמאל, האנגלית באמצע והעברית מימין
    - המפתחות שבסוף הספר אלפביתיים
intro_2: |
    כותרת: סימונים
    - חלק אפור בשם לטיני מופיע במרכיבי השמות
    - נקודה מוגבהת מסמנת את החיבור
    - במפתח, קו מפריד בתחילה מסמן מרכיב שמסיים שם, וקו מפריד בסוף מסמן מרכיב שמתחיל אותו
markers_heading: סימוני מינים
markers_intro: סימונים מופיעים אחרי השם העברי, בסוגריים:
legend_a: מין שמופיע בישראל לעיתים רחוקות או במקרה
legend_i: |
    מין שהובא לישראל כתוצאה, ישירה או עקיפה, מפעילות האדם
legend_ex: |
    מין שאינו מופיע עוד בישראל, אף שאוכלוסיות שלו קיימות במקומות אחרים
legend_x: מין או תת־מין שאינו קיים עוד
markers_note: |
    הסימונים מציינים חריגים בלבד; מין ללא סימון הוא מין שאינו נמנה
    עם אף אחת מהקטגוריות האלה.

    כותרת: רשימת חלופות
    בפרק מרכיבי השמות לפי קבוצות, השורה שמתחת למרכיב מונה צורות אחרות של
    אותו מרכיב.


index_heading_he: מפתחות
index_intro: |
    במפתחות השמות והמשפחות, המספר הוא העמוד ברשימה.
    בסוף הספר שישה מפתחות אלפביתיים. האות היוונית שבשפת כל עמוד היא
    תג המפתח; מתחתיה מופיעות האות הראשונה והאחרונה באותו עמוד.
index_hebrew_species: שמות עבריים (אלפא — **א**לף־בית)
index_english_species: שמות אנגליים (אתא — **א**נגלית)
index_latin_families: משפחות לטיניות (פי — **f**amily)
index_hebrew_families: משפחות עבריות (מו — **מ**שפחה)
index_latin_species: שמות לטיניים (למבדא — **ל**טיני)
index_elements: מרכיבי שמות (רו — **ר**כיבים)

## hebrew_index
# Header of the Hebrew name index.

heading_he: מפתח שמות עבריים

## english_index
# Header of the English name index; no explanatory line.

heading_he: מפתח שמות אנגליים

## latin_family_index
# Header of the Latin family-name index; no explanatory line.

heading_he: מפתח משפחות לטיניות

## hebrew_family_index
# Header of the Hebrew family-name index; no explanatory line.

heading_he: מפתח משפחות עבריות

## latin_species_index
# Header of the Latin species index; no explanatory line.

heading_he: מפתח שמות לטיניים

## element_data
# Header of the thematic word-element data pages (not an index).

heading_he: מרכיבי השמות לפי קבוצות
column_element: מרכיב
column_english: אנגלית
column_hebrew: עברית

## element_index
# Header of the alphabetical index of word elements.

heading_he: מפתח מרכיבי השמות
column_latin: מרכיב
column_page: עמוד
column_meaning: משמעות
column_group: קבוצה
column_refs: עמודי רשימה

## themes
# Theme headings for the element index, keyed by the English names in
# data/etymology.json.

Word-building: בניית מילים
Food: מזון
Shape: צורה
Colour: צבע
Birds: ציפורים
Where it lives: מקום מחיה
Mammals: יונקים
Size: גודל
Other animals: בעלי חיים אחרים
Behaviour: התנהגות
Body: גוף
Qualities: תכונות
Places: מקומות

## theme_short
# Short group labels for the alphabetical element index.

Word-building: בנייה
Food: מזון
Shape: צורה
Colour: צבע
Birds: ציפורים
Where it lives: מקום
Mammals: יונקים
Size: גודל
Other animals: חיות
Behaviour: התנהגות
Body: גוף
Qualities: תכונות
Places: מקומות

## notes
# The ruled notes page (page 66) at the end of the book.

heading_he: רשימות

## labels
# Small recurring labels.

continued: המשך

## cover
# The cover, front and back. The example blocks are enclosed in a light cream
# frame with an ochre border on both panels; all example information — family,
# names, word elements — is inside the frame. The birds — the robin on the
# front, the Namaqua dove and Eurasian nightjar on the back — are drawn from
# the species data and the etymology; their word elements form a separate
# left-aligned list inside the frame. This section carries the Latin blurb and
# footer. The counts in front_footer need updating if the species list changes.

front_footer: 565 species · 84 familiae · 13 themata verborum
back_subtitle: Comes portabilis amatoribus avium
back_subtitle_he: בן לוויה לכיס לחובבי ציפורים
back_para_1: |
    565 species in 84 familiis, cum nominibus Latinis, Anglicis
    Hebraicisque, et significatione cuiusque partis Latinae.
back_para_1_he: |
    565 מינים ב־84 משפחות, \
    עם שמות לטיניים, אנגליים ועבריים, ומשמעות כל מרכיב לטיני.
