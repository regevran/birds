- C is the next card: Hebrew prompt, per-part scaffold, typed full Latin.
- F/V cards, scheduling, lifecycle and the web UI remain design-only.
- Gate 2: profile/session store with atomic saves, saved queue and position,
  and the event log, so the text and browser clients can resume the same
  state. No scheduling semantics yet.
- Global search (future): grouped, read-only search over families, completed
  birds, elements and cards; see `learn-implementation.md` section 14. Do not
  build yet; keep dataset indexes and card views session-independent.
