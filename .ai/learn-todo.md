- F is implemented: Hebrew prompt, type the Latin unaided. The hint request
  will be an input at the `Latin:` prompt (for example `Latin:?`); the shared
  ladder for C/F/V remains to be designed/implemented.
- V cards, scheduling, lifecycle and the web UI remain design-only.
- Browser UI illustrations: https://github.com/alchaincyf/huashu-bird-sticker
  contains illustrations of all birds under CC BY 4.0; usable with attribution,
  not yet integrated.
- Gate 2: profile/session store with atomic saves, saved queue and position,
  and the event log, so the text and browser clients can resume the same
  state. No scheduling semantics yet.
- Global search (future): grouped, read-only search over families, completed
  birds, elements and cards; see `learn-implementation.md` section 14. Do not
  build yet; keep dataset indexes and card views session-independent.
