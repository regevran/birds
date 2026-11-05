# Trainer data

This directory holds data owned by the trainer, as opposed to the shared
canonical data in the repository-level `data/` directory.

## `progress/`

User saved progress, one directory per profile. It is intentionally
git-committable: committing and pulling is how progress moves between
machines. The app writes only here.

```text
progress/
  <profile-id>/
    profile.json
    events.jsonl
    sessions/
      <session-id>.json
```

Temporary files (`*.tmp`) and lock files (`.lock`) are ignored. The progress
files themselves are not ignored.
