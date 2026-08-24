# W2 mockups

The artboards behind the W2 design, published as a design canvas. The decisions they draw are
[`../../../notes/specs/2026-08-24-w2-reading-a-run.md`](../../../notes/specs/2026-08-24-w2-reading-a-run.md)
— the spec, which absorbed the interim D1–D11 decisions file.

**These are separate from [`../wiener-mockups/`](../wiener-mockups/) on purpose.** That canvas is
the record of how the *visual direction* was picked on 2026-08-23, and a record gets left alone.
This one is the record of what W2 builds.

```bash
python3 build.py            # rebuild every artboard from the tokens
```

| file | what |
|---|---|
| `Main.dc.html` | 1 · the overview — a run going well |
| `Expanded.dc.html` | 2 · a process row expanded to its tasks |
| `Failure.dc.html` | 3 · a run that failed — banner, then the overview |
| `Tasks.dc.html` | 4 · the Tasks tab, across the whole run |
| `Console.dc.html` | 5 · the console, filtered, and no longer the front door |
| `Graph.dc.html` | 6 · the graph — `dag-core`'s layout, coloured |
| `Walk.dc.html` | 7 · the builder — draw, keep, gate, run as one rail |
| `canvas.json` | two pages, and the note arguing each decision |

**Colour still has one source.** `build.py` reads `../wiener-mockups/tokens.shared.css` and adds
one labelled block of *derived* tokens — `--hover`, `--t`, `--ring`. No hex literal appears in any
artboard outside the token block, which is checkable rather than promised:

```bash
python3 - <<'PY'
import re, pathlib
for f in sorted(pathlib.Path('.').glob('*.dc.html')):
    body = f.read_text().split('@media (prefers-color-scheme: dark)', 1)[1].split('}\n}', 1)[1]
    print(f.name, len(re.findall(r'(?<![&\w])#[0-9A-Fa-f]{3,8}\b', body)))
PY
```

**The artboards are live, so they hover.** The interaction pass is real CSS rather than a painted
state — one timing (`--t`, 140ms, what `transition-colors` already resolves to), a light row tint,
a lift on controls, a shared focus ring, and `prefers-reduced-motion` removing the transition and
never the feedback.

`build.py` is a design tool. Nothing in `packages/` or `frontend/` imports it.
