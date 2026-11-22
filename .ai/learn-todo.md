- F is implemented: Hebrew prompt, type the Latin unaided. The hint request
  will be an input at the `Latin:` prompt (for example `Latin:?`); the shared
  ladder for C/F/V remains to be designed/implemented.
- V cards, scheduling, lifecycle and the web UI remain design-only.
- The Cloudflare progress Worker is implemented, tested and deployed at
  `https://birds-progress.regevran.workers.dev`; the live login smoke test
  passed. The Python `CloudFiles` client, credential storage and CLI
  `login`/`logout`/`whoami` are implemented. Next: the scheduler on top of the
  file API. See `learn-cloudflare.md`.
- Browser UI illustrations: https://github.com/alchaincyf/huashu-bird-sticker
  contains illustrations of all birds under CC BY 4.0; usable with attribution,
  not yet integrated.
- Gate 2: profile/session persistence over the Worker file API, so the text
  and browser clients resume the same state. R2's ETag is the revision; there
  is no event log and no scheduling semantics yet.
- Global search (future): grouped, read-only search over families, completed
  birds, elements and cards; see `learn-implementation.md` section 14. Do not
  build yet; keep dataset indexes and card views session-independent.
