# Birds of Israel — AI context

Durable project context. Read this file first; update the relevant file when a
decision, structure or status changes. Paths are from the repository root.
Superseded drafts are in git history.

## Read in this order

1. `decisions.md` — current choices and why.
2. `repository.md` — layout, data contract, build, status.
3. Trainer: `learn-reference.md` (model), `learn-ui.md` (browser UI),
   `learn-cloudflare.md` (Worker and storage).
4. Domain notes: `book-reference.md`, `whole-words.md`.

Canonical references outside `.ai/`:

- Worker API: `learn/WORKER-API.md`
- CLI usage: `learn/CLI-USAGE.md`
- User manual: `learn/USER-MANUAL.md`
- Public READMEs: `learn/README.md`, `book/README.md`, `data/README.md`
- Actionable work: `TODO.md`

## Working agreement

- Discuss and agree **before** implementing; work in small slices and let the
  user review each one.
- **CMake is the only build interface.** No second manual build path.
- Do not change `data/` or `book/` while working on the trainer unless asked.
- Do not commit unless asked.
- In chat, print Hebrew reversed (the terminal renders RTL backwards); source
  files keep normal Hebrew. The text trainer reverses Hebrew by default and
  accepts `--no-reverse-hebrew`.
- In data models, every field gets an end-of-line comment with a real project
  example; class docstrings say what the class holds.
