# 2026-10-12 — 14.7.8.3d Part G: canvas and walk agreement

Part G is implemented locally on `stage-four-the-consultant-build`, `883675fb` through
`ff941e08`.

- **The canvas is the server's frame.** `session.read` returns `canvas`: the visible graph,
  including a compatible pending step, its recorded step metadata and its true entry channels. It
  is built from rows the read already loaded, with no added SQL and no re-resolve. The live page
  no longer calls `/pipeline/draw`; the run sheet calls it once, for the saved draft, when it opens.
- **A frame never makes a session unreadable.** If the registry has moved under a recorded
  contract or port, `canvas` and `progress` are absent and the rest of the session still reads.
- **Progress is counted against the plan.** `progress_of` gives *Step 4 of 5* or *Review step 4
  of 5 again*. Each offer stamps where it stood; older offers show no invented ordinal.
- **What a run needs and what the registry lacks are separate.** A setting with candidates
  `[None]` is a gap, never something to provide. With Dev mode off, no gap paths reach the API;
  a card still names unresolved settings in plain words.
- **A complete alternative preview** is saved when the offer is made and read once per offer and
  context. Hover and focus look at it, Preview pins it, Escape and Close return focus, and a failed
  read waits for Retry. The build canvas stays mounted and inert underneath.
- Walk-found defects fixed: a ghost the frame did not hold, a footer that wrapped, and React's
  border shorthand warning.

Open: seven review minors (see the execution note), the Python 3.14 gzip cases (#303), and
the baked images, which are not rebuilt. Next: Part H (#292).
