# Design canvases

Every design canvas in the repository, in one place. Artboards are `.dc.html`, a generator
beside them rebuilds them from shared tokens, and `canvas.json` carries the pages and the note
arguing each decision.

**The current canvas is flat at the root of this directory; a superseded one lives in a named
subdirectory.** That asymmetry is deliberate rather than untidy: `packages/wiener-core` cites
`.design/canvas.json` page 5 by path as the authority for the timeline rules, and nine in-flight
Plan 4 and Plan 6 documents point at these paths. Moving the live canvas to tidy the shape would
rot references that are still being read.

| where | what | published |
|---|---|---|
| `./` (flat) | the 2026-08-29 redesign — builder, overview, runs. **Current** | [4f65e748](https://claude.ai/code/artifact/4f65e748-9758-4f06-9b87-1a8dc5a34b34) |
| [`w2-mockups/`](w2-mockups/) | W2, reading a run | [b36d76fb](https://claude.ai/code/artifact/b36d76fb-0025-4a6a-9f10-400bcc10de10) |
| [`wiener-mockups/`](wiener-mockups/) | the visual direction picked on 2026-08-23 — A–D, C chosen | **gone** — see below |
| [`runs-board/`](runs-board/) | the across-runs boards | [55693858](https://claude.ai/code/artifact/55693858-69a2-49f1-baaf-33e0cf199d92) |

**One of those four is already gone, which is the argument for the rest of this file.**
`notes/journal/2026-08-23-wiener-designed.md` records the wiener-mockups canvas at artifact
`6518257f-b5e3-4f13-808d-abab64a60f6b`; that URL no longer resolves. The artboards in
`wiener-mockups/` are now the only surviving copy of the four directions and the argument for
choosing C — which is exactly what a published link cannot be relied on to hold, and why the
`.dc.html` sources are the artifact and the seed is a build output.

**The seeded canvas HTML is never committed.** Each is megabytes of editor payload rebuilt from
the `.dc.html` sources and `canvas.json` beside it; `.gitignore` names all three, one line each,
and the published Artifact above is the copy you open. **A new canvas adds a line there** — the
patterns are anchored and literal on purpose, because `*.html` here would also swallow the
artboards and the `_*.html` partials.

**Why this is not under `docs/`.** These moved out of `docs/design/` on 2026-09-02. That
directory is the design *record* — prose written to be argued with — and it had accumulated
5.5 MB of generated payload and three executable generators, which is why `ruff.toml` carried a
per-file lint exemption pointing into the documentation tree. It now holds markdown and one
self-contained mockup (`dashboard.html`, 58 KB, cited by path from five source files).

**Links in `notes/` to the old `docs/design/*-mockups/` paths were left as they were.** They
were correct when written, `make links` deliberately does not check `notes/`, and a record gets
left alone.
