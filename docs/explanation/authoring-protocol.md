# How the authoring protocol works

Mendel authoring is one conversation beside one editable pipeline canvas. The conversation and
canvas are two ways to change the same goal and reviewed draft; neither is a second source of
truth. A declarative protocol defines how a session moves from a description to a buildable,
reviewed pipeline.

For the complete current flow, see the
[generated protocol diagram](diagrams/authoring-protocol.md). For operating the builder, use
[Build and inspect a pipeline](../how-to/pipelines/build.md). Control names and status signals are
listed in the [builder interface reference](../reference/pipelines/builder-interface.md).

## One declaration, three uses

`mendel_authoring.protocol.PROTOCOL` declares stages, nodes, and arrows.

- The diagram generator renders the declaration.
- The state module derives legal phase transitions and retry targets from built event arrows.
- The interpreter follows built arrows until the session reaches a node where it must rest.

This makes a flow change an executable code change. Protocol construction rejects undeclared
nodes or stages, contradictory transitions, illegal within-request events, ambiguous outgoing
arrows, and incomplete forks before a session can use the protocol.

Planned nodes and edges remain in the declaration and diagram as dashed shapes, but the state
machine and interpreter ignore them. They communicate design direction without pretending the
path is available.

## Pure core, effectful shell

The authoring package owns decisions that must agree across every transport:

- which commands may leave a resting node;
- how forks choose a path from a snapshot;
- how selected decisions compose a goal;
- how a resolved pipeline becomes a blueprint and reviewed draft;
- whether proposal settlement is current, conflicting, stale, accepted, or rejected;
- how canvas edits become explicit structural intent.

It does not open database rows, enqueue jobs, call a model, inspect files, or read a clock.
`mendel-api` performs those effects and submits typed commands or handler outcomes to this core.
Keeping the boundary here prevents HTTP, worker, and service callers from implementing slightly
different transition or settlement rules.

## From a description to a goal

The protocol first turns the person's words into proposed changes. A model may phrase a question
or return a typed interpretation, but the engine decides what is missing and validates every
identifier and value against declared data.

A change quoted from the person's own words can be recorded as heard; an unquoted model change is
a suggestion awaiting confirmation. The quote remains attached because finding the words does not
prove the interpretation was correct.

Selected input, wanted-output, fact, producer, parameter, absent-role, exclusion, and source
decisions compose the goal. Measurement declarations validate the profile. Evidence retains its
origin:

| Origin | Meaning |
|---|---|
| measured | A declared inspector or profiler obtained the value. |
| person said | The person asserted the value. |
| model read | A model read the value from admitted evidence. |
| open | No accepted value is available. |

An open fact is not silently defaulted. A rule that needs it cannot apply, and the affected
decision remains reviewable.

## Why samples are a section

Reading a sample contains several safety and validation steps: protection policy, bounded head
handling, format claims, optional model admission, measurement, and value admission. These steps
are drawn as a within-request section.

The section makes the work visible without turning each internal step into a persisted session
transition. Its entry handler performs the request and returns one named outcome; the protocol
then follows the matching exit.

## The blueprint decides; the walk reviews

Once a goal is confirmed, deterministic resolution produces a complete pipeline. Authoring stores
that pipeline as a `Blueprint` with a stable reveal order, layout positions, and the routing sites
where producer choices were made.

The walk does not build an unrelated graph one card at a time. It reviews the resolved blueprint:

- settled steps may be placed quietly, depending on pacing;
- tier-3 steps retain the fact and rule evidence that settled them;
- tier-4 choices stop for a person;
- registry gaps can be shown as development concerns;
- compatible tool alternatives are resolved as complete amended pipelines, so their cards can
  state which steps are added, removed, swapped, or updated.

Accepting a step projects it into the draft with its decision provenance. A wire appears only when
both endpoints are present. The draft is recomputed from the current blueprint and applicable
reviews, so a re-resolution cannot leave obsolete steps or edges behind.

## Canvas edits become durable intent

A canvas gesture describes mechanics: add a step, remove one, swap a tool, or change a wire. The
engine compares the before and after graphs and reads the likely intent as one of these goal
changes:

- want or stop wanting an output;
- switch a role off;
- pin or exclude a producer at a routing site;
- pin the producer feeding a specific input port.

The reading is shown for confirmation before it changes the goal. Once confirmed, the structural
intent survives later re-resolution instead of being preserved as unexplained graph residue.

## Reviews follow meaning

A review fingerprints the step's contract, settings, wiring, reasons, and evidence. When a new
blueprint changes that meaning, the review no longer applies. Review invalidation also cascades to
consumers whose upstream meaning changed.

This is why review state is not keyed only by node identifier: a familiar identifier can now mean
a different tool, input, value, or justification.

## Proposal settlement and retries

Proposal settlement compares three pieces of state in a deliberate order:

1. A proposal already accepted or rejected cannot take effect twice.
2. A client looking at an old draft revision must refresh before deciding.
3. A proposal created for an older draft becomes stale and is not applied.

Only a current acceptance changes the draft revision. Rejections settle the proposal without
changing the pipeline.

Failures enter the failed phase with the phase that failed recorded separately. A retry may resume
only at a target named by a protocol return edge. If that context is absent, retry falls back to
understanding, which may repeat work but cannot skip an unconfirmed goal.

## Determinism and model boundaries

Models do not control protocol paths directly. They return typed outcomes from acting nodes. Forks
read declared snapshot values, and the interpreter selects the corresponding validated case.

Given the same protocol, node, command, handler outcomes, and snapshot, the interpreter follows the
same path. Given the same selected decisions and declarations, goal composition produces the same
goal. Given the same blueprint and applicable reviews, draft projection produces the same graph and
provenance.
