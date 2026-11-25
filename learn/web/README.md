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
   and serves `http://localhost:8001`.
4. API base: the `meta[name="birds-api"]` tag in `index.html` (default
   `http://localhost:8787`). The local Worker's `ALLOWED_ORIGINS` must include
   `http://localhost:8001` (see `.dev.vars.example`).
5. Illustrations: `cmake --build build --target learn-web-illustrations` then
   `cmake --build build --target learn-web-illustrations-upload-local`. The
   client loads them from `<birds-api>/media/illustrations/<version>/...`; the
   `meta[name="birds-media-version"]` tag must match `asset_version` in
   `illustrations.json`.

## Scope

Now: session bar and context, the L card, the look-ahead (7 ahead), search
results (empty until typed; the × button or Esc clears them) and the
selected-row panel, and the L Next (other card types show a placeholder).
Illustrations load from the Worker's public media route; a persistent footer
carries the CC BY credit. The Worker now supports history windows and redo (a
card uid is classified live vs redo server-side), but the client navigation UI
is not built yet. The create buttons and the session actions are displayed but
inert. The drawer, the E/R/C/F faces and tests follow.
