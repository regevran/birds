# Browser UI

Status (2026-11-26): implemented — shell, L card, search results and panel,
fixed-centre look-ahead timeline, history/redo, thin E/R/C/F forms. Pending —
E/R/C/F face design, session drawer and create flows, settings, help, reader.
Desktop only.

Visual direction B (specimen sheet); palette in `learn/design/palette.css`;
mocks in `learn/design/`. Type colours are provisional.

## Principles

- Related controls stay close.
- Search is permanent; results stay on screen.
- The illustration is always visible. The Latin name is the target; Hebrew and
  the picture are accepted prompts.

## Shell

- Learning area and search region; one draggable split, direction and ratio
  browser-local. The learning area is self-contained.
- Session bar: the selected session and the drawer trigger. Progress is in the
  context line at its right end.
- Drawer (pending): at most one row open; an open row observes before
  switching; the current row is marked. `default` is protected; deleting the
  selected session falls back to it.

## Card face

- One face: bilingual title, family row, body, feedback, answer surface.
- Names: Hebrew and English equal; Latin largest; speaker to its right.
- Illustration on the right (~285 px) on every card, F included. One linked
  CC BY line in the page footer.
- Full card names in the UI; L/E/R/C/F is internal and CLI shorthand.
- L is the decomposition: one column per Latin word (fragment, English
  meaning, Hebrew gloss, theme). The CLI bridge is not drawn.
- A session and a card run look the same; only the context line and ending
  differ.

## Look-ahead timeline

- Fixed-centre timeline: three completed cards left, three planned cards
  right. Cards show `(type) Hebrew`; never Latin, English, family or ids.
- Completed cards dim text and border only; boxes stay opaque so the
  connector line never reads as a strike-through.
- The focused card is largest; text and boxes size 20 · 15 · 11 · 9 px with
  distance. The centre slot is fixed at 210 px, so the step arrows never move;
  the few longest Hebrew names ellipsize in the centre.
- Arrows are pinned to the connector line; cards paint above them, the focused
  card topmost. Cards do not capture clicks.
- Clicking the centre collapses the timeline to a monocular icon. Chevrons
  step through history and up to the live frontier; cards are not clickable.
- History pages in on demand. Completion slides the row one place under the
  centre; 300 ms; reduced-motion jumps. The main card follows the focus.
- A history card is redoable. A correct/advance redo leaves the future; a wrong
  redo resets the cards after it.

## Progress

- Context line percentage: session birds with no pending or queued cards; a
  card run's share of its matches. No lifetime counters.

## Sessions

- Created from a search scope; names are unique, duplicate criteria allowed.
- `default` always exists and is protected.
- The selected session is browser-local; switching goes to the current card.
- Active cap comes from the session (default 7); shown, not editable.
- Drawer sort: name and last visited, each toggling direction; `default` first.
- Completed panel (pending): name, 100%, birds learned, completed cards, last
  visited; switch, delete, new search.

## Search

- One input; six actions by full name: Learn, Elements, Recognize, Construct,
  Produce, Session.
- Results table: Latin, Order, Family, English, Hebrew; held left; column
  order movable and browser-local.
- The selected row fills a 380–460 px panel: names, part chips, the 3×2 create
  grid pinned at the bottom, full-height illustration at the right. No panel
  scroll; parts wrap.
- Query actions bind to the executed query; token actions bind to the selected
  token. Session filters are identity-only; a meaning-only search can run
  cards but not create a session.
- Card runs use the card-run filter (E split parts; R/C/F Hebrew), show
  skipped birds and the reason, and never change session state.

## Landing

Valid token → the selected session's current card. A card run is not restored
after reload or tab close.

## Open

- E/R/C/F faces; session drawer; create-or-switch; settings and help; error
  surfaces; reader; manual list building; live search vs Enter.
