# 2026-09-17 — Labs in the hybrid identity: the design the screens move to

**A design session, and a guide for the update that follows it.** No file under `packages/` or
`frontend/` changed. The output is a canvas that redraws Labs' key screens in the identity
Comeni Code was designed in on 2026-09-16, plus the decisions below. **The canvas is the spec for
the visual update; this entry is the argument and the order of work.**

**It does not replace the build handoff.** [`2026-09-13-the-living-pipeline-built-not-walked.md`](2026-09-13-the-living-pipeline-built-not-walked.md)
is still where the code stands, and its Task 14 — a real model, the real stack, a person in a
browser — is still unrun. Read that entry for the code; read this one before touching how a
screen looks.

## Where things stand

- **The canvas**: <https://claude.ai/artifact/K4PDRcfbUC6U1jmJmwqvTM>. It has one page of
  thirteen artboards, and each has a note above it saying where it is reached from and what it
  must do.
- **The source**: `.design/hybrid/`. `build_hybrid.mjs` generates every artboard and
  `canvas.json` from one fixture, so a count on Home and the row it counts cannot disagree.
  `_identity.mjs` holds the tokens, **copied** from `Comeni-Code/.design/_identity.mjs`.
  Rebuild with `node .design/hybrid/build_hybrid.mjs`, then re-seed with the `design` skill's
  `seed-canvas.mjs` into `.design/hybrid/comeni-labs-hybrid.html`, which is gitignored.
  Republish that seed to the URL above with contract `0.1.31`.
- **Nobody has looked at these boards rendered.** `_prev.py` needs `google-chrome-stable`, and
  the machine this was drawn on has only Firefox. They were checked by arithmetic on the layout,
  not by eye. The operator's instruction was to send screenshots of anything wrong. **Render them
  before building against one** (see *Traps*).
- **The current screens are Observatory**, dark by default since 2026-08-30. `tokens.css`
  mirrors `docs/design/dashboard.md` §2, which it calls authoritative. Nothing there changed
  today.

| Artboard | Screen | Replaces or extends |
|---|---|---|
| `Main` | Home: what needs you, what is running, what went wrong, then the lab's pipelines | `home/Home.tsx`, `Overview.dc.html` |
| `Describe` | a sentence → *what was understood*, line by line → step by step or all at once | `home/First.tsx` (a page rather than a panel) |
| `Build` | canvas + a vertical step line + the current step's choices + composer | `build/living/`, `living-pipeline/LivingBuild` |
| `Question` | an open value: every legal answer, a reason, or *measure it instead* | the tier-4 card |
| `PipelineFile` | every setting with how it was decided and why, beside `pipeline.yml` | `BuilderArtifact`, `ArtifactPreview.tsx` |
| `RunSheet` | files, reference, where it runs, limits | `RunSheet.tsx`, `BuilderRun` |
| `Runs` | saved views, filters with counts, a dense table, reserved vs used | `runs/Board.tsx` |
| `Run` | four panels, timeline with CPUs asked vs used, steps, tasks | `runs/Run.tsx`, `RunView` |
| `RunFailed` | the same page after a failure, drawn **dark** | `RunFailed` |
| `Registry`, `WorkQueue`, `Adaptation` | the registry section: overview, queue, one tool under review | `forge/registry/*`, `Forge*.dc.html` |
| `Colours` | one meaning per colour | `dashboard.md` §2's tier colours |

## What changed this session

- `.design/hybrid/`: the generator, the token copy, thirteen `.dc.html` artboards and
  `canvas.json`. They are committed with this entry.
- `.design/README.md` has a row for the canvas, and `.gitignore` has a line for its seed.
- This entry is now the entry point in `notes/journal/README.md`. `CLAUDE.md`'s pointer
  mentions it but still names 2026-09-13 as the build handoff.

## Decisions made, and why

**1. Labs takes the hybrid identity, the same one as Comeni Code.** It was decided by the
operator across 2026-09-16 and 2026-09-17, after comparing five themes and a Labs page drawn in
each.
- **What the hybrid is:** Friendly's legibility (Lexend, rounded controls, a raised main button,
  light-first, following the system theme) combined with Observatory's precision (Geist Mono for
  data, right-angled wires, dense tables, a quiet grid).
- **Why one identity for both:** the two products hand people to each other. The "Learn in Code"
  link in Labs and the Labs pipeline at the end of a Code route should not feel like two brands.
- **What is shared:** the identity, not code. The token file is a copy, and the two repositories
  share no packages.

**2. One meaning per colour, and settled spends none.** This carries over from Observatory and
from `dashboard.md`, and it gets stricter.
- **Settled** (structural or convention): no colour.
- **Measured:** amber. Model answers still awaiting review are also amber.
- **Needs you** (open, or went wrong): red.
- **Selected / now** (running, proposed, inputs): blue.
- **Valid / done** (a valid pipeline, finished stages, the main button): teal-green.

**The last two retire tokens.** `--running` (purple) becomes blue, and `--link` (blue) stops
being a colour of its own. That changes `tokens.css`'s own argument, so `dashboard.md` §2 must
be edited in the same change that edits the tokens. It must not drift behind them.

**3. Metro lines are the family resemblance.** A route in Code is a metro line, so in Labs so
are:
- the build steps (`Build`);
- the registry flow (`Registry`);
- the stages of an adaptation (`Adaptation`).

**Graphs you edit stay right-angled** (the canvas). That is the same split Code makes between
what a learner sees and what an editor edits.

**4. Words a person recognises, not engine words.** The boards use:
- "needs you", not tier 4;
- "measured", not tier 3;
- "with the model", not the AI lane;
- "found / drafted / ready for review / in the registry", not discovered / scaffold / review.

This is the rule `CLAUDE.md` already states for docs, applied to screens. The glossary (`?`)
stays for the words that remain.

**5. Labs stays on FastAPI.** Asked on 2026-09-17: should Labs migrate to Django, now that Code
is Django? **No.**
- **Code needed Django for things Labs doesn't need:** accounts, roles, an admin and editorial
  workflow in a content system.
- **Labs' value is in the pure packages**, which don't care what serves them. A migration would
  rewrite only `mendel-api` and `wiener-api`.
- **Labs is async and streaming:** run events over WebSockets, OTel export, arq.
- **The frontend's client is generated** from the current OpenAPI schema.
- **Every guard** (purity, egress, construction, replay) was watched failing against the current
  code and would have to be re-proved.
- **The rejected argument for moving** was one stack across both repositories. It is real and
  small: both already use Python, Postgres, Redis, React and Compose.

**6. What Django would have brought is accounts, and those arrive another way.** The redesign
shows a lab, people's names on runs, and "approved by a person". Today there is one shared token
(`WIENER_API_TOKEN`) and no users.

**The direction** is one sign-in shared by Code and Labs through OpenID Connect. Either Code (via
django-allauth with ORCID, GitHub and email, plus `django-oauth-toolkit`) is the provider and
Labs trusts it, or both trust a separate identity service (authentik, Keycloak). That shares a
sign-in, not code.

**Which of the two is not decided** (see *Open questions*).

## What to do next, in order

1. **Render and review the boards.** Install Chrome, or change `_prev.py` to fall back to
   `firefox --headless --screenshot`, and look at all thirteen at 1400 and 900. Fix the generator
   before anyone builds against a board.
2. **Walk Task 14 first, on the screens as they are**, unless the operator says otherwise. A walk
   finds defects in flow, and the redesign should absorb those rather than be built beside them.
   Task 14 needs a machine that can run a model; the design update does not.
3. **Then the update, part by part.** Each part gets a short spec and plan, test-first, and is
   compared against its board in one viewport (`_compare.html`) before it is called done:
   1. **Tokens and type:** `tokens.css`, `dashboard.md` §2, `tokens.test.ts`, and loading
      Lexend. Light-first, following the system theme, with the dark palette kept. The arc field
      goes.
   2. **The shell:** logo (goes home) · Build · Runs · Registry · a search box that also takes a
      description · Learn in Code · help · lab.
   3. **Home**, then **Describe**. They share `useBegin`.
   4. **Build** and **Question**, on the living builder. The manual builder follows the same
      tokens and gets no new board.
   5. **Pipeline file**, **Run sheet**.
   6. **Runs**, **Run**, **the failure panel**.
   7. **Registry**, **Work queue**, **Adaptation**.

**Why this order:** tokens first, because every later part is compared against boards drawn in
them. The shell next, because every page sits in it. After that, the loop's own order:
describe → build → run → watch, with the registry last.

## Open questions

- **Relaunching a failed run with more memory.** `RunFailed` shows "Relaunch with 96 GB for
  this step", and Wiener's only verb is cancel. Is it the next verb, or does the board lose the
  button?
- **Describe as a page.** The boards make the first-run panel a whole page, with a "what was
  understood" list. That list needs the goal to expose which lines came from the sentence, which
  from convention, and which are open. Check `AuthoringRequest`'s reply before promising it.
- **Shared sign-in:** Code as the provider, or a separate identity service. It also belongs in
  Code's architecture spec, R8.
- **Tokens, copied or published?** A copy is what "no shared code" allows, but a copy drifts.
  Either a check compares the two files, or the operator accepts drift and one repository is
  named as the source.
- **Dark mode's character.** The hybrid dark palette is not Observatory: it has no arcs, no
  translucent panels and no scan texture. Is that loss accepted, or does dark keep some of it?

## Traps

- **The boards were not seen.** The 2026-09-01 lesson applies in full: *reading finds wrong
  strings; it does not find wrong pictures.* Treat an overlap or a clipped label as the board's
  fault, not the implementation's.
- **The fixture is invented.**
  - The mouse-liver sentence, the MultiQC sixth step, `b71e04d2`, compute figures, source counts
    other than nf-core's 2,062, and the "Learn in Code" topics and times are all placeholders.
  - `SUBREAD_FEATURECOUNTS`'s pin (`@2.0.6`) and settings such as `featureType` were not read
    from the registry.
  - Read names and values from `registry/`, never from a board (the same rule `CLAUDE.md` gives
    for plans).
- **"Learn in Code" points at nothing yet.** Comeni Code is designed and not built. The link is
  a placeholder slot, and shipping it live would be a link going nowhere, which `Shell.tsx`
  already refuses.
- **The generator is JavaScript (Node).** The other canvases here are generated from Python
  (`build_boards.py`, `build_forge.py`, `build_living.py`); this one matches Code's generator,
  because the tokens are Code's file. `ruff` does not see it.
- **`dashboard.md` §2 is still authoritative** until the tokens part edits it. A token changed
  without that edit contradicts the file `tokens.css` says is right.
- **"Settled spends no colour" is already a rule in the code.** A shade that looks harmless in
  a new component breaks it. `tokens.test.ts` is where to guard it.
