# Worker API

Reference for the Cloudflare Worker that stores progress and owns the trainer
logic. This is the single API reference; other documents link here instead of
repeating routes or payloads. The design rationale is in
`../.ai/learn-cloudflare.md`.

- Deployed base URL: `https://birds-progress.regevran.workers.dev`
- Local base URL: `http://127.0.0.1:8787` (wrangler's default)
- All `/app` and `/fs` routes require `Authorization: Bearer <token>`.
- `/health` and `/login` are public.

## Run the Worker locally

Local development uses wrangler's local R2 emulation, which is separate from
the deployed bucket. Do not add `--remote` to the local upload.

```sh
cd learn/cloudflare

# Once: local secrets (gitignored). Edit AUTH_SECRET in the new file.
test -f .dev.vars || cp .dev.vars.example .dev.vars

# Once: make the provisioned accounts visible to the local Worker.
npx wrangler r2 object put birds-progress/users.json \
  --file users.json --local

# Start the Worker.
cmake --build ../../build --target learn-worker-dev
```

The server is at `http://127.0.0.1:8787`. If `users.json` does not exist yet,
create an account first:

```sh
python3 ../tools/provision_user.py <username> --scope tests
```

then repeat the local `r2 object put ... --local` command.

The deployed bucket is updated separately, with `--remote`:

```sh
npx wrangler r2 object put birds-progress/users.json \
  --file users.json --content-type application/json --remote
```

## Get a token

Choose the base URL:

```sh
# Local
BASE=http://127.0.0.1:8787

# Or deployed
# BASE=https://birds-progress.regevran.workers.dev
```

Log in and keep the token in a shell variable:

```sh
TOKEN=$(curl -s "$BASE/login" \
  -H 'content-type: application/json' \
  -d '{"username":"ran","password":"YOUR-PASSWORD"}' |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["token"])')
```

`YOUR-PASSWORD` is a placeholder; replace it with the account password. The
token is not printed. If `jq` is installed, the extraction can be
`| jq -r .token` instead.

Response:

```json
{
  "token": "base64url-payload.base64url-signature",
  "username": "ran",
  "scope": "profile",
  "expires_at": "2026-12-22T12:00:00.000Z"
}
```

Use it on every protected request:

```sh
curl -s "$BASE/app/profile" \
  -H "Authorization: Bearer $TOKEN"
```

Tokens are HMAC-SHA256 signed and valid for 30 days by default
(`TOKEN_TTL_SECONDS`). `scope` is `profile` for a normal account and `tests`
for a test account. A `tests`-scoped token only sees the shared `tests/`
prefix. Never commit a token or a `.dev.vars` file.

## Conventions

- Request and response bodies are JSON, except `GET /fs/<path>`, which returns
  raw bytes.
- Request bodies are capped at 1 MB.
- Errors are always:

```json
{
  "error": "some_error_code",
  "message": "human-readable message"
}
```

- `POST /login` and `POST /app/...` require `Content-Type: application/json`
  unless the endpoint says otherwise.
- Revisions are R2 ETags without quotes. Send a revision in `If-Match` for a
  conditional file write.
- `/app` responses are sent with `Cache-Control: no-store`.

Common status codes:

| Status | Meaning |
|---|---|
| 200 | success |
| 201 | session created |
| 204 | deleted, or CORS preflight |
| 400 | malformed request or invalid card answer |
| 401 | missing, invalid or expired token; bad login |
| 403 | request origin is not allowed |
| 404 | file, session or bird not found |
| 405 | wrong method for the route |
| 409 | session state conflict: stale card, bad delete, duplicate name, ambiguous handle |
| 412 | `If-Match` revision conflict |
| 413 | body is too large |
| 422 | session filter has no eligible birds |
| 500 | server or configuration error |

## Endpoint index

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | public liveness check |
| POST | `/login` | exchange username/password for a token |
| GET | `/fs?prefix=&limit=&cursor=` | list files in the token's scope |
| GET | `/fs/<path>` | read a file |
| PUT | `/fs/<path>` | write a file, optionally conditionally |
| DELETE | `/fs/<path>` | delete a file |
| GET | `/app/profile` | profile summary, created on first use |
| GET | `/app/sessions` | list sessions |
| POST | `/app/sessions` | create a session |
| POST | `/app/sessions/resolve` | resolve a name, id or id prefix |
| GET | `/app/sessions/<id>` | read one session view |
| DELETE | `/app/sessions/<id>` | delete a non-default session |
| POST | `/app/sessions/<id>/prepare` | prune passed birds, then return the view |
| POST | `/app/sessions/<id>/rename` | set or clear a session name |
| POST | `/app/sessions/<id>/answer` | grade one session answer |
| POST | `/app/birds` | search birds and etymology element meanings |
| POST | `/app/cards` | build one stateless card view |
| POST | `/app/cards/run` | filter search results for a card run |
| POST | `/app/cards/answer` | grade one stateless card attempt |

## Health

```sh
curl -s "$BASE/health"
```

```json
{
  "ok": true,
  "service": "birds-progress"
}
```

## Login

```sh
curl -s "$BASE/login" \
  -H 'content-type: application/json' \
  -d '{"username":"ran","password":"YOUR-PASSWORD"}'
```

Response:

```json
{
  "token": "base64url-payload.base64url-signature",
  "username": "ran",
  "scope": "profile",
  "expires_at": "2026-12-22T12:00:00.000Z"
}
```

Unknown users and wrong passwords both return `401 invalid_credentials`.
Missing credentials return `400 invalid_request`.

## File API

The file API stores arbitrary logical files under the token's scope. The
client never supplies a username in a path.

- A normal token maps `profile.json` to `users/<username>/profile.json`.
- A `tests` token maps it to `tests/profile.json`.
- Paths are relative, use `/`, and may contain letters, digits, `.`, `_`, `-`.
  Empty segments, `.`, `..`, backslashes and control characters are rejected.

### `GET /fs`

```sh
curl -s "$BASE/fs?prefix=&limit=100" \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "objects": [
    {
      "path": "profile.json",
      "size": 412,
      "revision": "17d8f1c0e0d7a7f2",
      "uploaded": "2026-11-22T12:00:00.000Z"
    }
  ],
  "truncated": false,
  "cursor": null
}
```

- `prefix` lists a subtree; for example `prefix=sessions/` lists sessions only.
- `limit` defaults to 100 and is capped at 1000.
- When `truncated` is true, pass the returned `cursor` to get the next page.

### `GET /fs/<path>`

```sh
curl -i "$BASE/fs/profile.json" \
  -H "Authorization: Bearer $TOKEN"
```

Response headers include:

```text
Content-Type: application/json; charset=utf-8
Content-Length: 412
Cache-Control: no-store
ETag: "17d8f1c0e0d7a7f2"
X-Revision: 17d8f1c0e0d7a7f2
```

The body is the file's raw bytes. JSON files are not reformatted.

### `PUT /fs/<path>`

```sh
curl -s -X PUT "$BASE/fs/probe.json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary '{"n":1}'
```

```json
{
  "path": "probe.json",
  "revision": "f2a4c3d1b8e90765",
  "size": 7
}
```

To prevent overwriting a newer revision, send the revision returned by a
previous read or write:

```sh
curl -s -X PUT "$BASE/fs/probe.json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "If-Match: f2a4c3d1b8e90765" \
  --data-binary '{"n":2}'
```

A stale `If-Match` returns `412 revision_conflict`. Without `If-Match`, the
write creates or replaces the file.

`Content-Type` is inferred from the extension: `.json`, `.txt`, or
`application/octet-stream`.

### `DELETE /fs/<path>`

```sh
curl -s -X DELETE "$BASE/fs/probe.json" \
  -H "Authorization: Bearer $TOKEN" \
  -o /dev/null -w '%{http_code}\n'
```

Returns `204` with no body. Deleting a missing file still succeeds.

## Profile

### `GET /app/profile`

Creates the profile and the protected `default` session on first use.

```sh
curl -s "$BASE/app/profile" \
  -H "Authorization: Bearer $TOKEN"
```

```json
{
  "profile_id": "ran",
  "name": "ran",
  "global_counter": 0,
  "passed_count": 0,
  "settings": {
    "active_cap": 7,
    "lookahead_target": 50,
    "out_of_scope_reviews": true,
    "show_bridge": true
  },
  "created_at": "2026-11-22T12:00:00.000Z",
  "updated_at": "2026-11-22T12:00:00.000Z"
}
```

`passed_count` is the size of the profile-global `passed` table. The table
itself lives in the profile document (keyed by species id, with the per-skill
V level and due counter) but is not exposed as a list and has no endpoint for
removing an entry.

## Sessions

A session is a saved queue of cards. Sessions are independent documents with
no notion of an active one: any number of clients can read and answer any of
their sessions. A protected session with id and name `default` is created
lazily for every profile; it has no filters (all status categories), so it
contains every eligible bird, and it cannot be deleted or renamed. Other
sessions have an optional unique name (trimmed, compared case-insensitively)
and can be deleted at any time.

Which session a client is working on is client state, not Worker state; the
CLI keeps it locally, the way git keeps the checked-out branch. Two clients may
select different sessions, or the same session. In the latter case they see
each other's progress, and a card that another client already consumed is
rejected with `409 stale_card`.

### `GET /app/sessions`

```sh
curl -s "$BASE/app/sessions" \
  -H "Authorization: Bearer $TOKEN"
```

The `default` session is listed first. `name` is `null` for an unnamed session.
`session_card_count` counts completed cards. `percent_completed` is the share of
the session's initial birds that are now passed, rounded down; it reaches 100
only when the queue and pool are empty.

```json
{
  "sessions": [
    {
      "session_id": "default",
      "name": "default",
      "status": "active",
      "session_card_count": 0,
      "percent_completed": 0,
      "initial_pool_size": 551,
      "queue_size": 7,
      "pool_size": 544,
      "created_at": "2026-11-22T18:31:00.000Z",
      "updated_at": "2026-11-22T18:31:00.000Z"
    },
    {
      "session_id": "20261122-1831-3c34",
      "name": "Demo",
      "status": "active",
      "session_card_count": 0,
      "percent_completed": 0,
      "initial_pool_size": 1,
      "queue_size": 5,
      "pool_size": 0,
      "created_at": "2026-11-22T18:31:00.000Z",
      "updated_at": "2026-11-22T18:31:00.000Z"
    }
  ]
}
```

### `POST /app/sessions/resolve`

Resolves a user-facing session handle. Matching is case-insensitive and uses
this order: exact name, exact id, unique id prefix. `by_name` restricts the
lookup to an exact name.

```sh
curl -s -X POST "$BASE/app/sessions/resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"handle":"DEMO"}'
```

```json
{
  "session": {
    "session_id": "20261122-1831-3c34",
    "name": "Demo",
    "status": "active",
    "session_card_count": 0,
    "percent_completed": 0,
    "initial_pool_size": 1,
    "queue_size": 5,
    "pool_size": 0,
    "created_at": "2026-11-22T18:31:00.000Z",
    "updated_at": "2026-11-22T18:31:00.000Z"
  }
}
```

An unknown handle returns `404 session_not_found`. A name or prefix matching
several sessions returns `409 session_ambiguous`; the message lists the
candidates as `id 'name'` lines.

### `POST /app/sessions`

```sh
curl -s "$BASE/app/sessions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Demo",
    "filter": {
      "search": "acrocephalus-agricola",
      "statuses": ["accidental"]
    },
    "settings": {"active_cap": 1},
    "seed": 7
  }'
```

Request fields:

| Field | Meaning |
|---|---|
| `name` | optional display name; omit or use `null` for an unnamed session |
| `filter.families` | family names, AND with the other filters |
| `filter.orders` | order names |
| `filter.genera` | genus names |
| `filter.statuses` | status categories; default regular + introduced |
| `filter.search` | every word must match id/Latin/English/Hebrew/family/order |
| `settings.active_cap` | maximum active birds; default 7 |
| `settings.lookahead_target` | stored target; default 50 |
| `settings.out_of_scope_reviews` | stored flag; default true |
| `settings.show_bridge` | stored flag; default true |
| `seed` | non-negative integer; makes the queue reproducible |

Only birds with Hebrew are eligible, and already-passed birds are excluded.
If no birds match, the response is `422 empty_pool`. A supplied name is
trimmed and must be unique among the profile's sessions; a duplicate returns
`409 session_name_taken`.

Response `201` is a session view:

```json
{
  "session": {
    "session_id": "20261122-1831-3c34",
    "name": "Demo",
    "status": "active",
    "session_card_count": 0,
    "percent_completed": 0,
    "global_counter": 0,
    "initial_pool_size": 1,
    "pool_size": 0,
    "queue_size": 5
  },
  "current": {
    "uid": "c_c5cfa622f7a5",
    "type": "L",
    "attempt": 1,
    "retry": false,
    "revealed": false,
    "card": {
      "card_type": "L",
      "species_id": "acrocephalus-agricola",
      "latin": "Acrocephalus agricola",
      "english": "Paddyfield warbler",
      "hebrew": "קנית אורז",
      "family": "Acrocephalidae",
      "family_he": "קניתיים",
      "order": "Passeriformes",
      "status": "A",
      "status_categories": ["accidental"],
      "parts": [
        {
          "latin": "Acro",
          "element_id": "acro",
          "english": "summit, peak",
          "hebrew": "פסגה",
          "theme": "Shape"
        },
        {
          "latin": "cephalus",
          "element_id": "cephalus",
          "english": "head",
          "hebrew": "ראש",
          "theme": "Body"
        },
        {
          "latin": "agri",
          "element_id": "agri",
          "english": "field",
          "hebrew": "שדה",
          "theme": "Where it lives"
        },
        {
          "latin": "cola",
          "element_id": "cola",
          "english": "dweller",
          "hebrew": "שוכן",
          "theme": "Behaviour"
        }
      ],
      "bridge": [],
      "whole_names": []
    }
  },
  "lookahead": [
    {
      "type": "E",
      "hebrew": "קנית אורז",
      "is_review": false,
      "out_of_scope": false
    },
    {
      "type": "R",
      "hebrew": "קנית אורז",
      "is_review": false,
      "out_of_scope": false
    },
    {
      "type": "C",
      "hebrew": "קנית אורז",
      "is_review": false,
      "out_of_scope": false
    },
    {
      "type": "F",
      "hebrew": "קנית אורז",
      "is_review": false,
      "out_of_scope": false
    }
  ]
}
```

`current` is `null` and `lookahead` is empty when the session is complete.
Creating a session does not change what any client has selected.

### `GET /app/sessions/<id>`

```sh
curl -s "$BASE/app/sessions/20261122-1831-3c34" \
  -H "Authorization: Bearer $TOKEN"
```

Returns the same session view.

### `DELETE /app/sessions/<id>`

```sh
curl -s -X DELETE "$BASE/app/sessions/20261122-1831-3c34" \
  -H "Authorization: Bearer $TOKEN" \
  -o /dev/null -w '%{http_code}\n'
```

Returns `204`. A missing session is `404 session_not_found`. Deleting the
`default` session returns `409 session_default`; every other session can be
deleted, including one a client currently has selected.

### `POST /app/sessions/<id>/prepare`

Drops birds that already passed from the session queue and pool, then returns
the updated session view. A client calls this before practising so a session
that has been idle for a while does not re-ask already-learned birds.

```sh
curl -s -X POST "$BASE/app/sessions/20261122-1831-3c34/prepare" \
  -H "Authorization: Bearer $TOKEN"
```

### `POST /app/sessions/<id>/rename`

Sets the name or clears it with `null`. The session id, queue and progress do
not change.

```sh
curl -s -X POST "$BASE/app/sessions/20261122-1831-3c34/rename" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Evening"}'
```

```sh
curl -s -X POST "$BASE/app/sessions/20261122-1831-3c34/rename" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":null}'
```

The new name is trimmed and must be unique among the other sessions,
case-insensitively. A collision returns `409 session_name_taken` with the
existing session's id and name, for example:

```text
session name 'morning' is taken by: 20261122-1831-3c34 'MoRnInG' (case-insensitive name collision)
```

The `default` session cannot be renamed. The response is a session view.

### `POST /app/sessions/<id>/answer`

Submit the current card. The body depends on the current card type:

```sh
# L: advance without answering
curl -s "$BASE/app/sessions/20261122-1831-3c34/answer" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"card_uid":"c_c5cfa622f7a5","action":"advance"}'
```

```json
{
  "card_uid": "c_c5cfa622f7a5",
  "action": "answer",
  "choices": {
    "acro": "פסגה",
    "cephalus": "ראש",
    "agri": "שדה",
    "cola": "שוכן"
  }
}
```

For R:

```json
{
  "card_uid": "c_c5cfa622f7a5",
  "action": "answer",
  "choice": "acrocephalus-agricola"
}
```

For C/F:

```json
{
  "card_uid": "c_c5cfa622f7a5",
  "action": "answer",
  "response": "Acrocephalus agricola"
}
```

A stale or non-current `card_uid` returns `409 stale_card`; this is also how a
client learns that another client working on the same session consumed the
card first.

Response:

```json
{
  "feedback": null,
  "session": { }
}
```

`feedback` is `null` for L. Otherwise it is one of the feedback forms below.
`session` is the next session view.

#### Session feedback

`elements` — E is graded once; all rows and expected glosses are returned:

```json
{
  "kind": "elements",
  "results": [
    {
      "element_id": "acro",
      "chosen": "פסגה",
      "expected": "פסגה",
      "correct": true
    }
  ],
  "correct": 1,
  "total": 1
}
```

`recognize`:

```json
{
  "kind": "recognize",
  "result": {
    "chosen": {
      "latin": "Acrocephalus agricola",
      "species_id": "acrocephalus-agricola"
    },
    "accepted": ["Acrocephalus agricola"],
    "correct": true
  }
}
```

`latin`:

```json
{
  "kind": "latin",
  "result": {
    "response": "corvus corax",
    "expected": "Acrocephalus agricola",
    "outcome": "wrong",
    "genus_ok": false,
    "epithet_ok": false,
    "distance": 14,
    "words": [
      {
        "expected": "acrocephalus",
        "response": "corvus",
        "status": "wrong",
        "distance": 8
      },
      {
        "expected": "agricola",
        "response": "corax",
        "status": "wrong",
        "distance": 6
      }
    ]
  }
}
```

`retry` — the first wrong R/C/F attempt:

```json
{
  "kind": "retry",
  "response": "corvus corax",
  "message": "wrong; try again"
}
```

For R, the retry form is `{"kind":"retry","chosen":"<Latin name>","message":"wrong; try again"}`.
The expected answer is not included on a retry.

Session rules:

- First wrong R/C/F: retry, card stays current with `attempt: 2`.
- Second wrong or revealed: consume the card and insert the fallback chain.
- Near miss on C/F: consume and move the card plus its chain ahead.
- Correct F: add the bird to `passed` and schedule V1 at `global_counter + 20`.
- L and E advance the queue after their result.

## Stateless cards

These routes do not read or write progress. They use the same card and grading
code as sessions.

### `POST /app/birds`

```sh
curl -s "$BASE/app/birds" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"q":"summit"}'
```

```json
{
  "birds": [
    {
      "species_id": "acrocephalus-agricola",
      "latin": "Acrocephalus agricola",
      "english": "Paddyfield warbler",
      "hebrew": "קנית אורז",
      "family": "Acrocephalidae",
      "family_he": "קניתיים",
      "order": "Passeriformes",
      "status": "A",
      "status_categories": ["accidental"],
      "has_hebrew": true,
      "has_parts": true,
      "matched": [
        {
          "kind": "element",
          "element_id": "acro",
          "texts": [{"field": "en", "text": "summit, peak"}]
        }
      ]
    }
  ],
  "elements": [
    {
      "element_id": "acro",
      "en": "summit, peak",
      "he": "פסגה",
      "theme": "Shape",
      "origin": "Greek",
      "bird_count": 10,
      "matched": [{"field": "en", "text": "summit, peak"}]
    }
  ],
  "count": 10
}
```

`q` is optional. Empty or omitted means every bird, with `elements: []` and
`matched: []`.

Every whitespace-separated term must match, case-insensitively, either an
identity field (id, Latin, English, Hebrew, family, Hebrew family, order) or an
etymology element of the bird's name (`element_id`, `display`, `en`, `he` or a
`forms` variant). Name matches come first and element-only matches follow,
each in family, genus and Latin order.

`matched` says why each bird was returned:

- `{"kind": "name", "texts": [{"field": "english", "text": "..."}]}` — a name
  or taxonomy field matched.
- `{"kind": "element", "element_id": "acro", "texts": [{"field": "en",
  "text": "summit, peak"}]}` — an element of the name matched. `field` is
  `element_id`, `display`, `en`, `he` or `form`.

`elements` lists the dictionary entries whose own fields match every term.
`bird_count` is the number of birds whose name uses that element. These are
search results only; saved-session filters in `/app/sessions` still match
identity fields only, so a session is never filtered by a gloss.


### `POST /app/cards/run`

Searches and filters in one Worker call, returning only birds that can make the
requested card type plus the number skipped and the reason. `L` accepts every
bird; `E` needs split elements; `R`, `C` and `F` need a Hebrew name.

```sh
curl -s "$BASE/app/cards/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"q":"warbler","card_type":"F"}'
```

```json
{
  "birds": [
    {
      "species_id": "acrocephalus-agricola",
      "latin": "Acrocephalus agricola",
      "english": "Paddyfield warbler",
      "hebrew": "קנית אורז",
      "family": "Acrocephalidae",
      "family_he": "קניתיים",
      "order": "Passeriformes",
      "status": "A",
      "status_categories": ["accidental"],
      "has_hebrew": true,
      "has_parts": true,
      "matched": []
    }
  ],
  "skipped": 1,
  "skip_reason": "no Hebrew"
}
```

`skip_reason` is empty when nothing was skipped. The birds keep search order.

### `POST /app/cards`

```sh
curl -s "$BASE/app/cards" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"species_id":"acrocephalus-agricola","card_type":"F","seed":7}'
```

```json
{
  "card": {
    "card_type": "F",
    "species_id": "acrocephalus-agricola",
    "family": "Acrocephalidae",
    "hebrew": "קנית אורז"
  }
}
```

`card_type` is `L`, `E`, `R`, `C` or `F` and is case-insensitive. `seed`
defaults to 0 and controls the option order for E/R.

Card payload shapes:

| Type | Fields |
|---|---|
| L | `species_id`, `latin`, `english`, `hebrew`, `family`, `family_he`, `order`, `status`, `status_categories`, `parts[]`, `bridge[]`, `whole_names[]` |
| E | `species_id`, `family`, `latin`, `rows[]`; each row has `element_id`, `latin_forms[]`, `theme`, `options[]` |
| R | `species_id`, `family`, `hebrew`, `options[]`; each option has `latin`, `species_id` |
| C | `species_id`, `family`, `hebrew`, `genus_parts[]`, `epithet_parts[]`; each part has `hebrew`, `first_letter`, `length` |
| F | `species_id`, `family`, `hebrew` |

Card views never contain an explicit correct-answer field. L is a learning
card and intentionally shows the full name. R options and E choices contain
the correct value among distractors, but do not mark it.

Unknown birds return `404 bird_not_found`; unsupported card types return
`400 unsupported_card`; an E card for a bird without split elements, or an
R/C/F card for a bird without Hebrew, returns `400 no_split_elements` or
`400 no_hebrew`.

### `POST /app/cards/answer`

Grade one attempt against a stateless card. `attempt` is the client's retry
counter: `1` for the first attempt, `2` for the second. It defaults to `1`.

```sh
curl -s "$BASE/app/cards/answer" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "species_id": "acrocephalus-agricola",
    "card_type": "F",
    "seed": 7,
    "attempt": 1,
    "response": "Corvus corax"
  }'
```

First wrong attempt:

```json
{
  "feedback": {
    "kind": "retry",
    "response": "corvus corax",
    "message": "wrong; try again"
  }
}
```

Same request with `"attempt": 2`:

```json
{
  "feedback": {
    "kind": "latin",
    "result": {
      "response": "corvus corax",
      "expected": "Acrocephalus agricola",
      "outcome": "wrong",
      "genus_ok": false,
      "epithet_ok": false,
      "distance": 14,
      "words": [
        {
          "expected": "acrocephalus",
          "response": "corvus",
          "status": "wrong",
          "distance": 8
        },
        {
          "expected": "agricola",
          "response": "corax",
          "status": "wrong",
          "distance": 6
        }
      ]
    }
  }
}
```

Request fields by card type:

| Type | Body |
|---|---|
| E | `{"species_id":"...","card_type":"E","seed":7,"attempt":1,"choices":{"acro":"...","cephalus":"..."}}` |
| R | `{"species_id":"...","card_type":"R","seed":7,"attempt":1,"choice":"acrocephalus-agricola"}` |
| C/F | `{"species_id":"...","card_type":"C","seed":7,"attempt":1,"response":"Acrocephalus agricola"}` |

Behavior:

- E is graded in one pass and always returns all rows.
- R/C/F return a sanitized `retry` on attempt 1 and the full result on attempt 2.
- A near miss on C/F returns the full result immediately.
- A correct answer returns the full result.
- L returns `400 not_answerable`.
- `attempt` must be `1` or `2`; missing values default to `1`.
- An invalid seed returns `400 invalid_request`.

## Complete example flow

```sh
BASE=http://127.0.0.1:8787

TOKEN=$(curl -s "$BASE/login" \
  -H 'content-type: application/json' \
  -d '{"username":"ran","password":"YOUR-PASSWORD"}' |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["token"])')

# 1. Find the bird.
curl -s "$BASE/app/birds" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"q":"paddyfield warbler"}'

# 2. Build an F card.
curl -s "$BASE/app/cards" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"species_id":"acrocephalus-agricola","card_type":"F","seed":7}'

# 3. First wrong attempt: sanitized retry.
curl -s "$BASE/app/cards/answer" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"species_id":"acrocephalus-agricola","card_type":"F","seed":7,
       "attempt":1,"response":"Corvus corax"}'

# 4. Second wrong attempt: expected answer included.
curl -s "$BASE/app/cards/answer" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"species_id":"acrocephalus-agricola","card_type":"F","seed":7,
       "attempt":2,"response":"Corvus corax"}'

# 5. Create a saved session.
curl -s "$BASE/app/sessions" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Demo","filter":{"search":"paddyfield"},
       "settings":{"active_cap":1},"seed":7}'

# 6. Use the returned session_id and current.uid, then advance the L card.
curl -s "$BASE/app/sessions/20261122-1831-3c34/answer" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"card_uid":"c_c5cfa622f7a5","action":"advance"}'
```

## Errors

| Error | Status | Typical cause |
|---|---|---|
| `invalid_request` | 400 | missing field, wrong type, bad seed/attempt |
| `invalid_json` | 400 | body is not JSON |
| `invalid_action` | 400 | wrong `action` for the current card |
| `invalid_settings` | 400 | invalid session setting |
| `unsupported_card` | 400 | card type is not L/E/R/C/F |
| `not_answerable` | 400 | attempting to answer an L card |
| `no_hebrew` | 400 | R/C/F card for a bird without Hebrew |
| `no_split_elements` | 400 | E card for a bird without split elements |
| `invalid_credentials` | 401 | wrong username or password |
| `unauthorized` | 401 | missing or malformed token |
| `token_expired` | 401 | token past `expires_at` |
| `forbidden_origin` | 403 | browser origin not allowed |
| `not_found` | 404 | unknown route or file |
| `session_not_found` | 404 | unknown session id or handle |
| `session_ambiguous` | 409 | a session handle matches several sessions |
| `bird_not_found` | 404 | unknown species id |
| `method_not_allowed` | 405 | wrong method |
| `stale_card` | 409 | `card_uid` is not current |
| `session_name_taken` | 409 | another session already uses the name |
| `session_default` | 409 | renaming or deleting the default session |
| `no_current_card` | 409 | session queue is empty |
| `revision_conflict` | 412 | stale `If-Match` |
| `payload_too_large` | 413 | body over 1 MB |
| `empty_pool` | 422 | session filter matches no eligible birds |
| `users_missing` | 500 | `users.json` is not provisioned |
| `users_invalid` | 500 | `users.json` is malformed |
| `server_misconfigured` | 500 | `AUTH_SECRET` is missing |
| `internal_error` | 500 | unexpected server error |

## CORS

`ALLOWED_ORIGINS` is a comma-separated list; the default is
`https://regevran.github.io`. Any `localhost` or `127.0.0.1` origin is allowed
for development. Preflight requests return `204` with:

```text
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type, If-Match
Access-Control-Expose-Headers: ETag, X-Revision
Access-Control-Max-Age: 86400
```

Preflight requests are handled before authentication, so browsers can
preflight protected routes.
