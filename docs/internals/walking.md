# Walking it: issues, decisions, rounds

*Serves: **describe and build**. How a driven session with a real model turns into fixes and
decisions without anything getting lost or quietly worked around.*

The system was designed from theory. A walk is where it meets use, and every walk so far has found
defects no test suite could. This page is the loop that turns what a walk finds into changes.

## The rule underneath

**Rules are tuned, never forced.** The product's claim is a balance between flexibility and
restraint. When a rule blocks the walk, the answer is never to make it work anyway: it is to decide,
in the open, whether that rule is too strict (loosen it) or too loose (tighten it). A workaround
hides which rule was wrong, and the rules are the product.

## A round

1. **Walk one scenario** in the browser, with the model the round names (a local model while
   debugging). Note every finding as you go; do not stop to fix.
2. **Open an issue for every finding**, mechanical ones too, before touching code. Use the
   *Walk: mechanical* or *Walk: protocol* template.
3. **Sort it** (below) and take its path.
4. **Re-walk the scenario** once its issues are closed or decided. A round ends when the scenario
   passes or is blocked on a protocol issue that has been decided but not built.

## Sorting a finding

| It is | when fixing it | path |
|---|---|---|
| **mechanical** | makes the code do what we already agreed it does: a wrong join, a missing button, a field the page forgets | fix it |
| **protocol** | changes what the product asks, allows, refuses or promises: a vocabulary a model cannot speak, a question nobody asks, a tier | decide it |

**Unsure means protocol.** That is the side that errs toward asking the operator. A mechanical
issue that turns out to need a decision is relabelled `protocol`, with a comment saying why.

A finding that turns out not to be a defect (the code was read wrong) is closed with a comment
saying what was misread, and labelled `invalid`. It stays on the record.

## The mechanical path

1. A failing test that reproduces the finding. Watch it fail.
2. The fix. Watch it pass; run the suite the change touches.
3. Commit with the issue number in the message.
4. Close the issue with a comment:

   > Fixed in `<sha>`: <one line on what changed>. Test: `<test name>`, watched failing first.

## The protocol path

1. **Brainstorm.** Two or three options, each with what it costs, and whether it **loosens** or
   **tightens** a rule. Say which you recommend and why. Present them as choices, not prose.
2. **The operator chooses.** Nobody picks silently, and "the model will probably manage" is not a
   choice.
3. **Comment the decision on the issue** and add the `decided` label:

   > **Decided (YYYY-MM-DD).** <The option chosen, in one or two sentences.>
   >
   > - **Loosens / tightens:** <which rule, and in which direction; or neither>
   > - **Rejected:** <each other option, and why>
   > - **Recorded in:** <`docs/design/authoring-protocol.md` changelog, a spec, an invariant; or
   >   nowhere, and why>
   > - **Built by:** <the issue or task that implements it, or "this issue">

4. **Implement it** the way all work is done here: **brainstorm the approach, then a spec, then a
   plan**, each seen by the operator before the next, then execute the plan test-first. A decision
   small enough to need no spec says so in the brainstorm, and the operator agrees to skip it.
5. **Close** citing the commit, and remove `decided`.

A loosening of an invariant is written into `docs/design/invariants.md` or the protocol page's
loosenings before it is built, never only in the issue.

`decided` marks the one state that is easy to lose: chosen, not yet built. `gh issue list --label
decided` is the list of promises outstanding.

## Where an issue lives

Every walk issue is a **sub-issue** of the walk round or task that found it, so the task tree
(issue #119: task → steps → substeps → tasks) stays whole. A protocol decision that becomes a whole
piece of work gets its own substep, and the finding points to it.

## Labels

| label | means |
|---|---|
| `walk` | found while walking with a real model |
| `mechanical` | the code is wrong against what was agreed |
| `protocol` | a rule or the protocol needs deciding |
| `decided` | the operator has chosen; not built yet |
| `deferred` | decided to do later; not forgotten |

## Writing the issue

Lead with **what happened** and **what was expected**, then the evidence: the scenario and round,
the model, the phase the session was in, and any diagnostic code, request, or `ai_invocation` row.
For a protocol issue, say which way the rule failed (**too strict**, **too loose**, or
**unclear**) and which rule or stage of the protocol it touches. Read the code before claiming what
it does: one issue in round 1 was filed about a prompt nobody had read.
