# How the builder agent works

The builder is one conversation beside one editable pipeline canvas. The person talks to an
agent; the agent reads the registry, chooses, builds and explains, and the canvas shows the
pipeline as it stands. The person can change anything on the canvas directly at any time. Both
change the same recorded decisions; neither is a second source of truth.

The agent acts and tells. It does not ask permission for each step, and nothing it does is
hidden: every choice it makes is recorded as the AI's, with its reason, and flagged for review.
Review never blocks building or running. For operating the builder, use
[Build and inspect a pipeline](../how-to/pipelines/build.md). The design and its alternatives
are in `docs/superpowers/specs/2026-11-14-builder-agent-design.md`.

## The engine and the agent

The split is the boundary Comeni is built around: a model's contribution stays visible and
reviewable.

| The engine | The agent |
|---|---|
| Validates every identifier and value against declared data. | Decides what to ask for, which tool to use and which values to set. |
| Routes, wires the steps and emits Nextflow. | Explains each choice in its own words. |
| Applies registry rules, and tells the agent when one fires. | May choose otherwise, giving its reason. |
| Records who made each decision and why. | Asks the person when it needs something only they know. |

The agent never writes pipeline code or a graph. It calls tools, and a tool either changes a
decision through the same writer the person's own clicks use or reads an engine view. A refused
call comes back to the agent as a coded refusal it can read and recover from; it never reaches
the person as an error.

## Tools

The tools live in `mendel_api.agent` and are the agent's whole reach:

- **Read**: the registry's types and measurements by their exact ids, the goal, the pipeline,
  one step, the tools around a type, the rules for a role, the facts about the person's data, and
  what is still needed.
- **Change**: want or have a type, set a fact, choose or exclude a tool, switch a role or an
  input, set a value, keep a tool whole, and undo a decision. It also gives the analysis a working
  name, which is not a decision and which the person can change.
- **Build**: resolve the decisions into a pipeline, and compile it to Nextflow.
- **Ask**: put a question to the person, with the shape of answer it takes. The turn ends there,
  and the person's answer starts the next one.

A writing tool states the decision revision it was made against. If the person changed the
pipeline in the meantime, the write is refused (`MI0201`) and the agent reads again. The same
tools are served to other agents over MCP, behind a bearer token: see
[Build a pipeline from another agent](../how-to/pipelines/build-from-another-agent.md).

A turn is bounded by a step limit and a token limit (`agent_max_steps`, `agent_max_tokens`).
At either limit the turn ends with a notice rather than running on. With no model configured,
the turn ends with `MI0106` and calls nothing.

## Rules are advice

Registry rules still decide tier-3 choices when the agent leaves them alone. When a rule fires,
its decision, its rows as sentences and its citation reach the agent as context. The agent may
override a rule; the override is recorded beside the rule it displaced (`Overrode` on the step's
`why`), resolved at tier 4 with the model as its source, and flagged for review. A contract's
`does:` line gives the agent one sentence on what a tool is for; it is context for the agent, not
text pasted into the chat.

## Who made each decision

Every decision carries its author: the person, the resolver, or the builder agent. A choice the
agent made carries `because`, its reason. A kept `pipeline.yml` lists the agent's choices under
`ai_choices`, each marked reviewed or not; keeping never waits on a review. A reviewed choice
counts as the person's answer when rules are learned from kept pipelines; an unreviewed one
does not. The person's direct actions — a change, a corrected
fact, a released tool, a canvas edit — are the person's, and the pipeline is built
again so the canvas follows at once.

Facts keep their origin:

| Origin | Meaning |
|---|---|
| measured | A declared measurer obtained the value from the analysis's data. Derived at every read, never logged: change the data and it changes. |
| person said | The person asserted the value. |
| model read | A model read the value from admitted evidence. |
| open | No accepted value is available. |
| varies | The samples differ, or the person said so. Each sample keeps its own value. |

An open fact is not silently defaulted. A rule that needs it cannot apply, and the affected
decision remains open for the agent or the person to settle. A person's word stands over a
measurement: new data never overwrites a fact the person stated.

## Canvas edits become durable intent

A canvas gesture describes mechanics: add a step, remove one, swap a tool, change a wire, type a
value. The engine compares the before and after graphs and reads the intent as goal changes:

- want or stop wanting an output;
- switch a role off;
- pin or exclude a producer at a routing site;
- pin the producer feeding a specific input port;
- set or clear a value.

Each reading is applied as the person's change, and the pipeline is built again from the
decisions. The structural intent survives later re-resolution instead of being kept as
unexplained graph residue. A move is layout and changes nothing.

## Reviews follow meaning

A review fingerprints a step's contract, settings, wiring, reasons and evidence. When a later
build changes that meaning, the review no longer applies, and the invalidation cascades to
consumers whose upstream meaning changed. A familiar node identifier can now mean a different
tool, input, value or justification, so review state is not keyed by identifier alone.

## Where each measurer runs

Every measurer declares where it runs (`runs: [server, pipeline]`), and a format states whether it
can run on this server. That location determines what is read where.

| Measurer | Reads | Runs on | What is kept |
|---|---|---|---|
| **Measurer, `server`** | The first 4 MB of each file of one sample, read in place from a ticked folder. | **this server**, in a constrained child process. | The measured facts, on the analysis's data. Nothing is copied. |
| **Measurer, `pipeline`** | All of the data, as a step in the run: our measure code, or a tool and a parser of its output. | **the lab's machine**, inside the pipeline. | The run's own record. Reading its facts back is planned (#465). |

Changing a measurer's `runs` declaration requires a matching runner and an update to this table.

## What the agent's model sees

What reaches the agent's model is declared on one door, `builder_agent`: the conversation (the
person's words and the agent's own) and one typed result per tool call. A result may carry the
names of the person's samples, so the agent can talk about them; never a path or a file's
contents. Sample names are kept with the analysis's data and deleted with it; they never enter a
goal, a pipeline or a log. See
[the invariants](invariants.md) for the rule and its guards.

## Determinism

The agent's choices are recorded decisions, and replays use them. Given the same declarations
and the same recorded decisions, resolution produces the same pipeline and emission the same
Nextflow; nothing the model does at replay time can change the output. Given the same blueprint
and applicable reviews, the draft projection produces the same graph and provenance.
