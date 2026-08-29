# The loop a user should walk — and the one they walk today

Written 2026-08-29, after walking the loop end to end
([journal](../journal/2026-08-29-walking-the-loop.md)). Input to the frontend rework.

**Method.** State the loop as *intentions* — what a person is trying to do, with no reference to
our machinery. Then count the actions the product actually costs for each one. An **action** is
one discrete act: a click, a double-click, a drag, a typed value, a context-menu selection (two:
open, choose).

The measurement is not "how many clicks". It is **how many of them are decisions.**

---

## 1. The loop, as it should be

Six moves. Each is something a researcher wants; none mentions a draft, a gate or an artifact.

| # | The intention | What the product owes them |
|---|---|---|
| 1 | *"I want counts from these RNA-seq reads"* | somewhere to start that is **theirs** — a goal or a template, not somebody else's pipeline already on the canvas |
| 2 | *"This is my data"* | pick it from a place they registered once. The product works out samples, pairs and structure |
| 3 | *"Show me what you'd run"* | the pipeline, with **what it could not decide** marked and answerable in place |
| 4 | *"Go"* | **one** action. Saving, validating and handing over are the machine's filing, not theirs |
| 5 | *"Is it working?"* | they are already watching it; they did not have to ask |
| 6 | *"Where are my results?"* | named outputs, reachable, per sample |

**The rule this produces:** *every action a user takes should be a decision.* Anything else is the
machine asking a human to do its clerical work. Steps 1, 2 and 3 are decisions. Steps 4, 5 and 6
should cost one action, zero and one.

**Target: about five actions plus however many real decisions the pipeline genuinely poses.**

---

## 2. The loop as it is

Measured today, building the smallest honest pipeline — TRIMGALORE into FASTQC — from
`/build` to a run you can watch.

**Before the product can be opened at all**, in a terminal:

- know that data must sit inside a directory Wiener bind-mounts
- copy the reads there
- know the absolute path, exactly
- know that `{1,2}` is what pairs the two files

**None of that is possible inside the product.** The loop does not start in the product.

Then, in the browser:

| # | Action | Decision? |
|---|---|---|
| 1–10 | delete the five preloaded spine steps — select + `Delete`, five times | no |
| 11 | switch the palette to *All modules* | no |
| 12 | double-click `trimgalore` | **yes** |
| 13 | double-click `fastqc` | **yes** |
| 14 | drag `fastqc` off `trimgalore` — they land on identical coordinates, so until you do this you have two steps and see one | no |
| 15 | drag the wire | **yes** |
| 16 | click *Keep* | no |
| 17 | click *Lint*, wait ~10s | no |
| 18 | scroll the rail to reach *Run* | no |
| 19 | click *Send to Wiener* — twice, the first is a decoy button that does nothing | no |
| 20 | focus the input field | no |
| 21 | type the 84-character absolute path | **yes**, but only in the sense that a filing clerk decides |
| 22 | click *Start run* | no |
| 23 | click *Watch it* | no |

**24 observed actions** (23 plus the wasted decoy click). **Four are decisions.** Twenty are the
machine's filing.

And then: the run succeeds, FastQC writes two HTML reports, and they are in
`work/59/9e45e2e5b072aae856e9c95afa7a31/`. **No `publishDir` is emitted anywhere in the
compiler** — grep the golden spine, there is none. The results exist and the product will never
show them to you. **Step 6 does not exist.**

---

## 3. Where the actions go, outcome by outcome

| Outcome | Today | Should be | The gap is |
|---|---|---|---|
| start from nothing | **10** acts of deletion | **0** — open empty, or choose a template | the canvas opens with someone else's pipeline on it |
| add two steps | **4** (two adds, one rescue drag, one reposition) | **2** | every step is placed at the same coordinates |
| connect them | 1 drag | 0–1 — connect on drop when only one port matches | fine as is |
| save it | **1** explicit *Keep* | **0** | drafts already autosave every 5s. *Keep* is the artifact write, an implementation detail wearing a button |
| check it is valid | **1** + 10s wait | **0** | lint takes 1.6s and should run inside *Go*, surfacing only on failure |
| hand it to the runner | **2** (+1 decoy) | **0** | *Send to Wiener* is our architecture leaking; the user did not ask for two systems |
| say which data | shell work, then **2**, exact path typed | **2**, picked | there is no concept of a dataset |
| start it | 1 | 1 | correct |
| watch it | **1** | **0** | starting a run should take you to it |
| get the results | **impossible** | **1** | nothing is published out of `work/` |

**Six of ten outcomes should cost zero actions and cost between one and ten.**

---

## 4. What this says, beyond the counts

**a. `draw → keep → gate → run` is our build pipeline, printed on the screen.** Those are four
things *we* do: hold a graph, write an artifact, validate it, submit it. A user has one
intention — *run this* — and we have made them drive four of our verbs in order, with each
gated on the last. The rail even numbers them. **Collapse to one action**: *Go* keeps, lints,
submits and navigates; it stops and explains only when something fails.

This costs nothing architecturally. `execution-boundary.md` §3 keeps *gate* and *run* apart
because a gate proves an artifact on public data and a run touches a lab's own — that
distinction is real and must survive. It is a distinction between **two things the machine
does**, not two buttons a person presses.

**b. Ten actions to reach an empty canvas.** The builder opens with the RNA-seq spine loaded.
For a demo that is right; for the first thing a user ever does it means the product's opening
move is *destroy the example*. An empty canvas with a template picker costs zero.

**c. The one action that is a decision is also the one that is impossible.** Choosing your data
is the single most important input a user gives, and it is the step that requires a terminal,
exact knowledge of a host path, and glob syntax. Everything cheap is easy and the only expensive
thing is the thing that matters.

**d. Nothing is published.** Six of the six moves have an owner in the code except the last. A
pipeline that runs and leaves its results in a hash directory has not finished; it has stopped.
`publishDir` is one line per process in the emitted config and an *Outputs* tab is one endpoint —
this is the cheapest large win available.

---

## 5. The rules to design against

1. **Every action is a decision.** If the machine can work it out, it works it out.
2. **One intention, one action.** *Go* is one button. So is *pick my data*.
3. **Never make a user name a location.** They select; we resolve.
4. **The loop ends at results**, not at a green tick.
5. **Our nouns are not their nouns.** Draft, artifact, gate, bundle, digest, tier — none of these
   belong on a screen unless the user's own task requires the word.
6. **Explain on failure, not in advance.** The Gate panel spends four lines saying what a gate is
   to somebody who has not asked. Say nothing; say it when it fails.
