# Wiener mockups

The artboards behind `../../docs/design/wiener.md` §9.5, published as a design canvas.

**`tokens.shared.css` is the one place colour is defined here**, and `build.py` generates every
`.dc.html` from it. That is checkable rather than promised: no hex literal appears in any artboard
outside the token block, and `python3 build.py` regenerates them all.

```bash
python3 build.py            # rebuild every MVP artboard from the tokens
```

| file | what |
|---|---|
| `Board.dc.html` | the runs list |
| `Main.dc.html` | a run going well, dashboard collapsed |
| `Failure.dc.html` | a run failing — console view, dashboard expanded |
| `Graph.dc.html` | the same run — graph view |
| `DirectionA–D.dc.html` | the four visual directions put up on 2026-08-23. **C was chosen** |
| `canvas.json` | the canvas layout: two pages, and the notes arguing each direction |

**The four directions are kept rather than deleted.** Three were rejected and the argument for each
is in `canvas.json`'s annotations — a rejected option whose reasoning lives only in a chat log gets
re-proposed six months later.

`build.py` is a design tool. It is not part of the product build and nothing in `packages/` or
`frontend/` imports it.
