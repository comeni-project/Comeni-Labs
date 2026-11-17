# Frontend redesign board (2026-11-15)

These files are the source of the agreed redesign board. The written design and every revision are in
issue #511 and its comments; read those first, then these files for exact layout, copy and tokens.

Each `*.dc.html` file is one screen of a design board. The markup is HTML with a small template syntax:
`<sc-if value="{{x}}">` shows its children when `x` is true, and `<sc-for list="{{xs}}" as="x">` repeats them.
The `{{…}}` values come from the screen's `renderValsBase` function in the script at the bottom of the file,
which also holds the sample data and click handlers. Colours are `var(--c-*)` tokens; `Tokens.dc.html`
maps each to its light and dark values and to `frontend/src/tokens.css`.

| File | Screen |
|---|---|
| `Welcome.dc.html` | First launch |
| `Home.dc.html` | Home |
| `Main.dc.html` | Data: Overview · Samples · References · Files, assistant overlay |
| `Build.dc.html` | Build: canvas, step form, assistant |
| `Run.dc.html` | Run: Overview · Steps (Graph / Timeline) · Outputs · Console |
| `Settings.dc.html` | Settings |
| `ForgeHome.dc.html`, `Forging.dc.html` | Forge home; forging Tool · Tests · Publish |
| `Registry.dc.html` | Registry |
| `Tokens.dc.html` | Theme tokens, light and dark |

Migration order: plan 1 covers Welcome, Home, Data, Build and Run; plan 2 covers Settings, Forge and Registry.
Cloud storage is not in the MVP; the Data rail keeps a placeholder for it.
