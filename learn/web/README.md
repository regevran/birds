# Browser client

Static HTML/CSS/JS. It talks to the Worker and to nothing else: local or remote
by configuration, no offline mode, no sample data.

## Local run

1. Local Worker: `cmake --build build --target learn-worker-dev` (or
   `cd learn/cloudflare && npx wrangler dev`). It listens on `:8787`, uses the
   local `.dev.vars`, and reads `users.json` from the local R2 emulation; stage
   it with `cmake --build build --target learn-worker-users-upload`.
2. Token: `cmake --build build --target learn-web-token`. It signs a local
   token with `.dev.vars` (`AUTH_SECRET`, no password needed) and writes
   `build/web/dev-login.html`; open `http://localhost:8001/dev-login.html` to
   store it under `localStorage['birds.token']` and enter the app. The page is
   a development credential: never deploy it. The manual login flow is in
   `../WORKER-API.md#get-a-token`.
3. Serve: `cmake --build build --target learn-web-serve`; it stages `build/web`
   and serves `http://localhost:8001` with `Cache-Control: no-store`, so a
   reload always picks up restaged files.
4. API base: the `meta[name="birds-api"]` tag in `index.html` (default
   `http://localhost:8787`). The local Worker's `ALLOWED_ORIGINS` must include
   `http://localhost:8001` (see `.dev.vars.example`).
5. Illustrations: `cmake --build build --target learn-web-illustrations` then
   `cmake --build build --target learn-web-illustrations-upload-local`. The
   client loads them from `<birds-api>/media/illustrations/<version>/...`; the
   `meta[name="birds-media-version"]` tag must match `asset_version` in
   `illustrations.json`.

## Scope

Now: session bar and context, the L card, the fixed-centre look-ahead timeline
(three completed cards, the focused card largest, three planned cards, text
and box sizes stepping down with distance at 20 · 15 · 11 · 9 px; fixed step
arrows; collapse to the monocular icon), search results (empty until typed;
the × button or Esc clears them), the selected-row panel, and thin functional
E/R/C/F answer forms that submit the real Worker answer shapes (unstyled,
design pass pending).
Illustrations load from the Worker's public media route; a persistent footer
carries the CC BY credit. The timeline chevrons browse completed cards and
return to the live frontier; history pages in on demand, and the main card
follows the lens. Redo answers work through the same thin faces. The create
buttons and the session actions are displayed but inert. The drawer, face
design and client tests follow.
