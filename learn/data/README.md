# Trainer data

This directory is reserved for local trainer data, as opposed to the shared
canonical data in the repository-level `data/` directory.

User progress is **not** stored here. It lives in private Cloudflare R2 behind
the Worker in `learn/cloudflare/`; the Worker is the single source of truth.
See `../cloudflare/README.md` and `.ai/learn-cloudflare.md`.

There is no event log and no local progress directory.
