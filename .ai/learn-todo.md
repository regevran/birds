- F is implemented: Hebrew prompt, type the Latin unaided. The hint request
  will be an input at the `Latin:` prompt (for example `Latin:?`); the shared
  ladder for C/F/V remains to be designed/implemented.
- V cards, hints and the web UI remain design-only.
- The Cloudflare progress Worker is implemented and tested. It is at
  `https://birds-progress.regevran.workers.dev`; the stateless card/search
  routes still need a deployment. The Python client is a thin Worker client:
  `CloudFiles`/`CloudApp`, credentials, `login`/`logout`/`whoami`, search,
  `card L|E|R|C|F`, and
  `session new|list|open|status|run|rename|delete` are implemented. Sessions
  are independent Worker documents with no active one; each client locally
  selects its session, and a protected `default` always exists. Next: the
  browser client. See `learn-cloudflare.md`.
- Browser UI illustrations: https://github.com/alchaincyf/huashu-bird-sticker
  contains illustrations of all birds under CC BY 4.0; usable with attribution,
  not yet integrated.
- Gate 2: profile/session persistence, search, cards and grading live in the
  Worker, and the text client resumes saved sessions. The browser client is
  still to come. R2's ETag is the revision; there is no event log.
- Global search (future): grouped, read-only search over families, completed
  birds, elements and cards; see `learn-implementation.md` section 14. Do not
  build yet; keep the Worker's search and card views session-independent.
