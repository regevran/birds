# Browser UI design

Status: design only; last updated 2026-11-24. Nothing implemented; login,
hosting and client implementation are open. Authoritative for the browser
layout, regions and search interaction; card design stays in
`learn-reference.md`. Direction B is chosen; mocks are in `learn/design/`.

Related: `learn-reference.md`, `learn/CLI-USAGE.md`, `decisions.md`.

## Scope

- Desktop only.
- Search is first-class: a permanent region whose results stay on screen;
  never disabled, including for the bird being practised.
- Sessions and card runs (`card X <text>`) are first-class and present
  identically; both are series instances (`learn-reference.md`).
- The bird illustration is in v1 on every card; the reader uses pre-generated
  clips (Latin must; English and Hebrew later).
- Deferred: V, hints, element-list actions, manual list building, English
  directions.

## Principles

- Related controls stay visually close; don't spread them because the row has
  space.
- Nothing shown or spoken that isn't already visible.
- The Latin name is the target; Hebrew and the picture are both accepted
  prompts.

## Shell

- Two permanent regions, learning area and search region; one split: search on
  any side (bottom default), draggable with minimum sizes, direction and ratio
  persisted per browser; the split line is 4px. The learning area is
  self-contained.
- Session bar packed at the left: the selected session (or `default`) and the
  drawer trigger. An overlay drawer (covers; resizable to the right) lists
  Sessions; at most one row is open, the current one on opening. Opening a row
  observes it without switching: created from, created, last visited, active
  cap, counts. `created from` is the Worker-formatted search/criteria,
  read-only; CLI-only filters appear there; `default` has none. The open row
  carries `Switch to`, `Rename`, `Delete`; the current
  row is marked and has no `Switch to`. `default` is protected; deleting the
  selected session falls back to `default` and says so. As the drawer widens,
  the facts reflow from one per line to one line.
- Progress is always visible, in the context line at its right end.

## Card face

- One fixed face on every card: bilingual title (Hebrew start, English end,
  equal size), family row (Hebrew family start, English family end, large;
  order and status small, centred), body, feedback slot, answer surface.
- Names: Hebrew and English equal size on one line; the Latin name is the
  largest object, speaker to its right.
- Illustration: always visible, F included; the body's right column (~285px).
  The CC BY credit is a single linked line in the persistent page footer, not
  repeated under each plate. Picture→Latin is accepted.
- Speakers follow visible names (Latin now; English and Hebrew later); nothing
  invisible is spoken.
- Full card names; L/E/R/C/F is CLI and internal shorthand. L is the read-only
  reference; its only action is `Next`, at the card's right edge with an arrow.
- L's name explanation is a decomposition: one group per Latin word, each part
  a column of fragment, English meaning, Hebrew gloss and theme in parentheses,
  in the name's serif and Latin order. The bridge is not drawn in the browser
  (the CLI keeps it).
- A session and a run present identically; only the context line (name vs
  `C run · 14 birds · acro`) and the ending differ.
- Look-ahead: seven upcoming Hebrew names, type-coloured, packed
  left-to-right with arrows from the card's left; the strip fits its content
  and a nest closes the queue. The binocular is the only control, no label;
  collapsible; never Latin, English, family or ids.

## Progress

- A percentage, always in the context line: session share of initial birds
  with no pending or queued cards left (Worker rule); run share of its matches.
  No lifetime counters.

## Sessions

- `default` always exists and is protected. Creating from a search scope makes
  a new session; duplicate criteria under different names (or unnamed) are
  allowed, while names stay unique. A match with no eligible birds returns an
  empty pool and the UI explains it.
  Create-or-switch is deferred to the open questions.
- Independent; the selected session is browser-local. Switching goes straight
  to the current card. Two clients on one session see each other's progress; a
  409 reloads.
- Active cap = the session's `settings.active_cap` (default 7, positive):
  birds kept in flight, whose chains the queue interleaves. Set at creation;
  shown, not editable. The Worker formats `created_from` at creation and
  returns it with `active_cap` in the summary/view; old sessions format their
  stored filter; `default` has no origin.
- Sort: two controls, name and last visited, each toggling asc/desc;
  browser-local. Last visited is `updated_at`, refreshed by `prepare` and by
  rename; unnamed rows show a short id and sort after named rows; `default`
  stays pinned first.
- Completed terminal panel: name, 100%, birds learned of initial, completed
  cards, last visited; switch, delete, search a new scope.

## Search semantics

- The CLI's: case-insensitive substring; every term must match a name field
  (id, Latin, English, Hebrew, family, family_he, order) or an element field
  (id, display, glosses, forms); name matches rank first; `warbler` is text.
- Two action levels, six actions by full name. Query: `L/E/R/C/F` =
  `card X <query>`, Session = `session new --search <query>`. Token: every
  whitespace token plus element parts where the etymology splits a word; the
  token text is the query.
- Token scopes: species id → one bird; Latin word → that word; element part →
  element matches; English or Hebrew word → that name; family, family_he,
  order → that value.
- Actions bind to the executed query, not the live input; an empty query has
  none. Session filters are identity-only: a meaning-only query can run cards
  but not create a session (`Session` disabled with the reason). Card runs use
  the card-run filter (E split parts; R/C/F Hebrew), show skipped birds and the
  reason, and never change session state.

## Search region

- One input at the left; the six query actions sit immediately beside it as
  "this search".
- Results are an LTR table held left in the remaining width, only as wide as
  the longest line plus headroom: Latin, Order, Family, English, Hebrew. Drag
  grips reorder the columns; the order is browser-local.
- Selecting a row highlights it and fills the right panel (380–460px wide) with
  two columns. The left column holds the names, then the selectable parts, then
  the create controls; the illustration fills a full-height box on the right.
  The parts are every creatable token — whole names, words, etymology parts,
  family, order — as chips that wrap onto as many lines as needed.
- The panel has a fixed height (the search row) and no internal scrolling. The
  constant 3×2 create grid is pinned to the bottom of the left column, aligned
  to its widest label. Three steps: row → element → button. The illustration is
  the selected row's bird; the footer carries the credit. Layout is verified
  for every bird; the densest panels still fit without a scrollbar.
- Both scopes stay: "this search" for the whole result set, the panel's buttons
  for the selected element.

## Landing

- Expired token → auth gate (login UX undecided). Valid token → the selected
  session's current card. A run is not restored after reload or tab close.

## Visual direction

- B (specimen sheet) is chosen; A (paper page) and C (evening ink) are
  references. The palette is carried from `../personal_portfolio` and defined
  as the trainer's own tokens in `learn/design/palette.css`; type colours are
  provisional until the colour-template task. The page and L are
  `learn/design/main-b.html` (`out/main-b.png`); the drawer is
  `main-b-drawer.html` (`out/main-b-drawer.png`; wide state
  `main-b-drawer-wide.png`); card-specific passes for E/R/C/F come later.

## Rejected / considered

- Two search boxes: one box is script-agnostic; a second duplicates state.
- Hiding the illustration on F: the Latin is the target, not the prompt source.
- L/E/R/C/F shorthand in the UI: full names instead.
- Progress in the session bar: the context line owns it; the bar is identity.
- Related controls spread across a row (session bar, search actions,
  parts/create): kept together.
- Per-word colour-dot columns for create: too many dots; selectable chips plus
  constant labelled buttons.
- Hover popups on result words: the selected-row panel carries the token
  actions.
- Look-ahead spread with `space-between`: packed, fit-content, nest at the end.
- A search table stretched across the row: held left; the right is the selection
  panel.
- Illustration centred or left: right column on every card.
- Bridge on the browser L face: the decomposition carries the glosses.
- Fixed column order: moveable and browser-local.
- Coloured tones on the name's parts: looked like a mistake; dropped.
- Small panel illustration or reveal-only: superseded by a large always-on
  panel picture.
- Several session rows open at once: at most one.
- A row body that switches with no visible action: observing and switching are
  separate; the open row carries `Switch to`.
- Four sort chips (name and visited, each direction): two controls, each with
  both arrows attached.
- A fixed-width drawer: resizable to the right; the facts reflow.
- A raw filter for the clients to format: the Worker emits the formatted
  `created_from`; the string also serves a future custom series.

## Open questions

- Empty session state; an actively practised `default` joining the sort.
- Create-or-switch for sessions: whether to offer it; whether the user chooses
  create or switch; how a duplicate is detected (the name collision vs the
  same criteria, including a renamed session); the visual if kept.
- Drawer: rename inline, delete confirmation and the selected-delete notice;
  width bounds and the facts' intermediate wrap.
- Live search vs Enter.
- Manual list building; element-list actions.
- Settings home (bridge, active cap, future V); help/keys overlay.
- Error surfaces: stale card (409), save failed (412), server down.
- Reader: pronunciation convention, voice, clip generation.
- Per-card layout passes.

## Card-run persistence (ephemeral in v1)

A run is a cursor `(query, card type, position)`; the bird list is derivable.
Chosen: ephemeral, re-launch is the query plus one click. Fallback: a
browser-local resume pointer — client-only, no API/Worker/CLI change; add only
if tab-close loss bites. Out of scope: a Worker document or session mode,
resumable with the sessions' concurrency; revisit when a second persistent
series is designed as a group.

## History and redo

The timeline is linear. The client keeps a browsing cursor over completed
history plus the frontier; the Worker serves history windows and the frontier.
A card in history is not read-only: answering it is a redo (the Worker
classifies the submitted card uid, so the client never declares the mode).
A correct/advance redo records only and leaves the future unchanged; a wrong
redo invalidates everything after that card and the client returns to the new
frontier. Placeholder E/R/C/F cards need an explicit Skip (a live advance)
until their faces exist. Phase-4 UI work.
