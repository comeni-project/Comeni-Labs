# Runs board

The artboard behind the across-runs boards — Wiener W1 phase 3, `../../docs/design/wiener.md` §9.4.

**Published as a canvas**: <https://claude.ai/code/artifact/55693858-69a2-49f1-baaf-33e0cf199d92>

The URL is written down because a link that lives only in a chat log is a link that is lost.
This directory had no README until the 2026-09-02 sanitization, which is why its seeded canvas
was the one committed file of its class whose published copy was recorded nowhere.

```bash
python3 board.py            # rebuild the artboard from the tokens
```

| file | what |
|---|---|
| `Main.dc.html` | the four boards — wrong now, breaks, time, capacity |
| `canvas.json` | the page, and the note arguing each board |

`board.py` is a design tool. It borrows `../w2-mockups/build.py`'s chrome rather than restating
it, so it inherits that file's two lint exemptions. Nothing in `packages/` or `frontend/`
imports either.

**The seeded canvas is not committed.** `runs-board.html` was 2.4 MB of editor payload
regenerated from the two files above; it is ignored in `.gitignore` alongside the other two,
and the published Artifact is the copy you open.
