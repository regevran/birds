# Birds of Israel — AI context

Durable project context. Read this file first; update the relevant file when a
decision, structure or status changes. Paths are from the repository root. Git
history holds superseded drafts.

## Read in this order

1. `decisions.md` — agreed choices and their reasons.
2. `repository.md` — layout, data contract, build and current status.
3. For trainer work: `learn-reference.md` (design), `learn-ui.md`
   (browser UI design) and `learn-cloudflare.md` (Worker and progress).
4. Domain notes: `book-reference.md`, `whole-words.md`.

Canonical references outside `.ai/`:

- Worker API: `learn/WORKER-API.md`
- CLI usage: `learn/CLI-USAGE.md`
- Public READMEs: `learn/README.md`, `book/README.md`, `book/PRINT.md`,
  `data/README.md`
- Actionable work: root `TODO.md`

## Working agreement

- Discuss, summarize and agree **before** implementing; work in small slices
  and let the user review each one.
- **CMake is the only build interface.** No second manual build path.
- Do not change `data/` or `book/` while working on the trainer unless asked.
- Do not commit unless asked.
- In chat, print Hebrew reversed (the terminal renders RTL backwards); source
  files keep normal Hebrew. The text trainer reverses Hebrew by default and
  accepts `--no-reverse-hebrew`.
- In data models, every field gets an end-of-line comment with a real project
  example; class docstrings say what the class holds.
