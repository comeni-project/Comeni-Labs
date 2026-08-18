# Plan 3 — the interface, in three parts

**3A the Forge · 3B the landing page · 3C Mendel.** Named by the operator on 2026-08-18. This
spec details **3A** and states what B and C are for; each gets its own spec, written against the
code the previous one lands.

**Status:** design spec, written 2026-08-18 with the operator, against the code that exists,
the interface that was designed, and the conventions in `../../Cladewright` and
`../../portfolio`.

**Precedence:** where this spec and the code disagree, the code is right and this file has
drifted.

**It replaces `2026-08-18-plan-3.md`'s slicing, not its content.** That spec's §4 — what must
exist underneath — still holds and is referenced rather than repeated. What it got wrong was
the decomposition, and §3 below is the correction.

**Read first:** [`docs/design/forge-review.md`](../../docs/design/forge-review.md) is the
specification for every forge screen; [`docs/design/dashboard.md`](../../docs/design/dashboard.md)
§2 is the token, type and spacing system governing both halves.

---

## 1. What exists, honestly

Nine commits on `plan-3-slice-1` built a **working backend and a viewer that does nothing**.

**Works, and was verified against real data rather than fixtures:**

- `mendel-api` mounts the forge's eleven routes; `GET /questions` reads a real workspace and
  collapses 13 questions into 7 rows; `GET /health/registry` reads the registry and the database.
- Postgres + Alembic, migration applied from scratch. One table.
- An ARQ worker that ran a real job over Redis and wrote a row.
- React rendering live data, with a TypeScript client **generated** from `openapi.json` and
  Tailwind's `@theme` mirroring the tokens.
- 28 tests; `make verify` exits 0 at 1203.

**Does not exist:**

- **Any write path.** Three GETs, no POST. **Zero event handlers, six dead `href="#"` links, one
  button with no handler.** Nothing you click does anything.
- Routing. The app is one hardcoded screen.
- A landing page — none was ever designed.
- Error, loading and empty states beyond a bare string.
- The build path, the canvas, drift screens, contracts, proposals, sources.

**The failure worth naming**, because it shapes this spec: slice 1 was reported at its checkpoint
as *"the queue on screen"* without saying that nothing on that screen worked. The sequencing
error was recoverable; the reporting error is what cost three rounds of questions. **Every phase
below states what you can and cannot do at the end of it.**

---

## 2. Decisions taken

Recorded with their arguments so they are not re-litigated.

| | Decision |
|---|---|
| **Landing** | *"What needs you today"* across **both** halves — drift, blocked proposals, questions, pipelines needing review. You pick work, not a workspace. |
| **Auth** | Still deferred. `--by` reads `git config user.name`; nothing gates on identity. Provenance survives because every answer still records who settled it. |
| **Branch** | Keep `plan-3-slice-1` and build on it. The backend works and the environment fixes — TypeScript pinning, the rolldown binding, happy-dom — cost real time to find. |
| **FastAPI** | Idiomatic. Routers, `Depends`, Pydantic schemas, service functions. No Django glossary in the code. |
| **Compose** | Follow the house pattern: `docker-compose.dev.yml` for db + api + worker with live mounts; the Vite frontend stays on the host so HMR works; **plus** `docker-compose.prod.yml` where the frontend is built and served. `make dev` is the one command. |

### 2.1 Foundation first — and why the objection was wrong

The operator chose **foundation before routes**, over building route-by-route.

**The argument for it that decided the matter:** emergent architecture is right when you do not
know what is coming. Here the route list *is* known — the design specifies ten screens. Deriving
a shell from one example is then strictly worse, because one example does not reveal the
variation: a shell shaped by a read-only list would be bent by answering, by drift resolution and
by the canvas in turn.

Concretely it avoids a mutation pattern retrofitted after the first POST, error handling invented
twice, and route state that starts as `useState` and becomes a router concern.

**The guardrail, because a foundation phase can be confidently wrong in ways you cannot see until
route three:** phase 0 does not end on *the shell compiles*. It ends on **one real action working
end to end** — a click, a mutation, an API write, a query invalidation, a UI update. That is the
cheapest test of every pattern at once.

---

## 3. The phases

Each states what you can do at the end. **A phase that ends with something you cannot use says
so in its own heading.**

### 3A — the Forge. This spec.

| # | Phase | At the end you can… |
|---|---|---|
| 0 | Foundation | …answer one question through the shell. **Nothing else.** |
| 1 | Queue | …filter, sort, and work the queue as designed. |
| 2 | Answering | …answer one question, or the same question across every draft asking it. |
| 3 | Proposals | …approve, rename or reject a vocabulary proposal. |
| 4 | Contracts & module | …browse what has landed and read one contract against its source. |
| 5 | Drift | …see what moved and take the source's value. |
| 6 | Sources & drafting | …discover a tool and draft it, without the CLI. |
| 7 | Compose & prod | …bring the whole thing up with one command. |

**`/` redirects to `/forge/queue` for the whole of 3A**, and that is temporary rather than a
design position. The landing page is 3B; a placeholder home built now would be thrown away.

### 3B — the landing page

*"What needs you today"* across both halves. It comes **after** 3A rather than before it for one
reason: a landing page is a projection of work that exists elsewhere, and until the forge's
routes are real there is nothing true to project. Building it first means inventing its content.

It gains Mendel's items in 3C without changing shape — which is the test of whether §5's
`/attention` endpoint was designed correctly.

### 3C — Mendel

The pipeline builder: canvas, provenance bar, settings cards, review rail. **The half a biologist
uses**, and the one that moves the v1 criterion.

It is last because it is the only part with prerequisites that are not interface work: the
orchestration extraction (`resolve_verbs.run` is argparse-shaped, so no API can call it) and DAG
layout — [`2026-08-18-plan-3.md`](2026-08-18-plan-3.md) §4.1 and §4.8.

**Two things make it cheaper than it looks.** The registry already routes: `mendel build --goal
examples/rnaseq-goal.yml` produces a five-module spine today, so the data a canvas renders exists
without the forge having grown anything. And `docs/design/dashboard.html` is 922 lines of working
pan, zoom, drag and orthogonal wire routing — a React port has something to follow rather than
invent.

**AI is not in 3C either.** #69 first, then the tier-4 resolver; both are after the builder can
show a pipeline it already resolves deterministically.

---

## 4. Phase 0 — the foundation

### 4.1 Routing

`react-router` with a nested layout: one `Shell` route wrapping everything, so nav state and the
registry panel survive navigation.

```
/                        redirect to /forge/queue for the whole of 3A; the landing is 3B
/forge/queue             the queue
/forge/queue/:subject    one question           ← the panel opens beside it
/forge/proposals         proposals
/forge/proposals/:id     one proposal
/forge/contracts         what has landed
/forge/contracts/:id     one module, read only
/forge/contracts/:id/drift   resolve drift
/forge/sources           what can be read
```

**Deep links are a requirement, not a nicety.** A curator who finds a bad answer must be able to
send someone the URL of the question, which means the question's identity lives in the path.

### 4.2 The mutation pattern

Every write goes through one hook shape, established once:

- `useMutation` with the generated client
- On success, invalidate the queries the write affects — never hand-patch the cache. The forge's
  answers change `remaining` on a draft and the queue's aggregation, and reproducing that
  arithmetic client-side is a second implementation of `aggregate()`.
- On failure, surface the API's own message. `mendel_forge.http` returns **422** with the coded
  refusal in `detail` — `MF0002`, `MF0003`, `MD…`. **The UI shows that code and text**; inventing
  friendlier copy would hide the one string that tells a user what to do, and `forge explain
  <code>` exists precisely to expand it.

### 4.3 States, once, for every route

Loading, empty, and error are three components, not three ad-hoc branches. The empty state is
**content**, not an apology — *"Nothing open. Draft a module to give the queue work."*

### 4.4 Keyboard

The design promises `J`/`K`/`A`/`E`. A single key-binding hook, registered per route, so the map
is declared in one place rather than scattered through components.

### 4.5 Who is answering

No accounts, so `by` is read once from `git config user.name` by the API and offered as the
default, overridable in a field. It is attached to every answer and reaches
`FilledValue.by` → `Provenance.drafted_by`.

### 4.6 The exit criterion

**Answer one question from the UI.** `POST /questions/answer` → `ops.fill` → the workspace changes
→ the queue refetches → the row disappears. If that works, every pattern above is proven.

---

## 5. The API surface

Idiomatic FastAPI: `APIRouter` per resource, `Depends` for settings and session, Pydantic schemas
in and out, service functions holding the logic so routes stay three lines.

| Method | Path | Over |
|---|---|---|
| `GET` | `/attention` | the landing page — everything needing a human, both halves |
| `GET` | `/questions` | exists |
| `POST` | `/questions/answer` | `ops.fill`, one draft |
| `POST` | `/questions/answer-all` | **new** — one answer across every draft asking it |
| `GET`/`POST` | `/proposals`, `/proposals/{id}/decide` | the vocabulary queue |
| `GET` | `/contracts`, `/contracts/{id}` | the registry, and one module |
| `GET`/`POST` | `/contracts/{id}/drift`, `/drift/accept` | `ops.check`, `ops.update` |
| `GET` | `/registry/types/{id}` | the lookup panel |
| `GET` | `/health`, `/health/registry` | exists |
| mount | `/forge/*` | the forge's own eleven routes |

**`answer-all` is the one genuinely new operation.** `ops.fill` settles one field on one draft;
answering across three drafts is a loop that must record provenance **per value** — the same
`by` and `why` on each — or the batch path becomes the one that loses the reasons. It is not a
wrapper; it needs its own refusal semantics for partial failure, and **it must be atomic per
draft**: a draft is either answered or untouched, never half.

**What the landing page needs that does not exist** is in
[`2026-08-18-plan-3.md`](2026-08-18-plan-3.md) §4.4–4.7: a consumers index, which pipelines pin a
contract, and whether a drift changes routing. Phase 1 builds the first; the other two land with
phases 5 and 6.

---

## 6. The frontend

```
frontend/src/
  api/          GENERATED from openapi.json — never hand-edited
  app/          Shell, router, error boundary, key bindings
  ui/           the three states, and the primitives the design specifies
  forge/        one folder per route
  registry/     the lookup panel, available from anywhere
```

**Tailwind's `@theme` mirrors the tokens and does not redefine them.** Six type roles, nine
spacing steps, from `dashboard.md` §2. A utility that invents a seventh size is the drift the
indirection exists to prevent — the set had seventeen sizes before 2026-08-18 and every one was
picked by eye.

**The design is the specification.** Where this spec and `docs/design/*.md` disagree about a
screen, the design document is right. `forge-review.md` §8 is what is firm and what is provisional.

**Invariant 15 has a UI face**: no input accepts a sample sheet, a filename or a path.

---

## 7. Docker Compose

Follows `../../Cladewright` and `../../portfolio`, which is why the shapes below are theirs.

**`docker-compose.dev.yml`** — `db`, `redis`, `api`, `worker`. Healthchecks at 2s/2s/30,
`depends_on: condition: service_healthy`, live code mounts, `container_name` overridable through
`${…}`, a named volume for pgdata, and migrations applied in the API's start command.

**The frontend is NOT in the dev compose**, matching both repos: HMR through a container
bind-mount is slower and flakier on Linux. `make dev` brings up compose and starts Vite on the
host with a pidfile and a log, then prints the URLs.

**`docker-compose.prod.yml`** — the same services plus the frontend **built and served**, which is
where "all in compose" is literally true.

**One difference from those repos, and it is deliberate:** they install from `requirements.txt`;
this workspace uses `uv` with five packages, so the API image installs with `uv sync --frozen`.
The `.env.example` is committed and `.env` is ignored, as there.

---

## 8. Testing

- **API**: pytest, one file per router. Service functions tested without HTTP — that separation is
  what the no-logic-in-handlers rule buys.
- **Frontend**: vitest + Testing Library, **happy-dom** (jsdom cannot start a worker on Node 22 —
  it pulls `@asamuzakjp/css-color`, which `require()`s an ES module).
- **Every mutation gets a test that it invalidates**, because a write whose list does not refresh
  looks broken in exactly the way a passing unit test cannot see.
- **`make verify` stays the gate**, and the frontend job runs `tsc --noEmit`, `vitest run` and
  `vite build`.

---

## 9. Out of scope

- **The landing page (3B) and Mendel (3C)** — each its own spec, written against the code the
  previous part lands. §3 says what they are and why they sit in that order.
- **Auth** — deferred; adding it later changes one field's source.
- **The prompt door** — plain language → `Goal`, after Plan 3.
- **The rule drafter** — behind Plan 3.
- **Protection profiles** — [#71](https://github.com/comeni-project/Comeni-Labs/issues/71).
- **Upstream version checking** — [#64](https://github.com/comeni-project/Comeni-Labs/issues/64).
  Its absence bounds what the drift screens may claim: nothing here knows a newer version exists,
  and the UI must not imply it.

---

## 10. Estimate

**Phase 0 is the one that matters** — it is where being wrong is expensive, and its exit criterion
exists to make being wrong visible immediately. Phases 1–7 should each be short, because the
foundation is the point of doing it first.

Stated in sessions rather than weeks, per the operator's correction on 2026-08-18 that my
estimates run an order of magnitude long: **phase 0 one session, phases 1–7 roughly one each**,
and the ones most likely to break that are phase 2 (`answer-all` needs real refusal semantics)
and phase 4 (the module page is dense and needs two indexes that do not exist).

**3B is short.** **3C is the big one**, and it is the only part whose cost is dominated by
something other than interface work — DAG layout.
