# The consultant's words, fast and cheap — substep 14.7.4

**Substep 14.7.4 (#180)** of Task 14 (#119). Brainstormed with the operator on 2026-09-28/29 in
three rounds; every decision below is also commented on its issue.
**Issues:** #182 #191 (what we keep and show of each model call), #183 #184 #185 (prompt structure
and the model server), #167 #176 #186 (the consultant's words).
**Builds on:** [the consultant spec](2026-09-28-the-consultant-design.md) (gathering, §6) and
[the authoring protocol](../../design/authoring-protocol.md).

---

## 1. Why

The 14.7.3 walk made gathering work, and showed three things the consultant still lacks:

- **Nobody can see what a model said.** `ai_invocation` records that a call happened — digest,
  state, tokens — and never the reply. Every model finding in the walk (#179 above all) was
  diagnosed by re-calling the model by hand.
- **Calls are slow and uncached.** gemma3:12b re-reads the same ~3,300-token prompt on every call
  (11 s), the JSON schema sits after the person's words so no provider can cache the fixed part,
  and the model server unloads after five idle minutes.
- **The words are the engine's ids, and the model's prose invents.** Questions read *This analysis
  needs fastq.reads* (#167); the first-call summary said *normalised* and the typed goal gained
  constraints nobody asked for (#176).

## 2. What success looks like

With `ollama_chat/gemma3:12b` locally and the Compose stack:

1. The header shows the session's tokens and calls, ticking up as calls land, with no extra
   requests; opening it lists each call with its reply.
2. An identical fixed prompt part is not re-read: a repeat call's prompt evaluation drops from
   ~11 s towards ~1 s (or #185 records why not), and the counter shows cached tokens on a hosted
   lane.
3. Scenario 1 reads like a person talking: an acknowledgement after the first sentence, questions
   in plain words, a read-back written from the composed goal, invented constraints offered as
   suggestions — and no pipeline value a person did not confirm.
4. **Walk measurements:** confirmation clicks per session, and every model sentence that was wrong
   or leading, written into the walk's record.

## 3. Decisions (operator, 2026-09-28/29)

| Decision | Issue |
|---|---|
| Store the **raw reply** of every call, admitted or refused — a level-0 loosening | #182 |
| A nullable **`session_id`** on `ai_invocation`; every builder call sets it | #191 |
| A header **count** that opens a **call list** (the replies viewer) | #191 |
| **No new polling, nothing chatty:** the count rides the session poll; the list loads on open; every model call is a queued job | #191, all |
| Prompts **split by a divider** into `[system, user]`, **most-shared first**, byte-identical fixed part | #183 |
| **The model server is deployment configuration:** Compose sets keep-alive and one slot, and is upgraded; the app assumes neither | #184, #185 |
| An **acknowledgement** after the first sentence replaces the up-front summary | #167 |
| Each question **phrased by a model when offered**, with `already` pre-filling; engine wording shown at once and **swapped in place** | #167 |
| **Prefetch** the next question's phrasing | #186 |
| A **read-back** written from the composed goal, labelled *in the AI's words* | #176 |
| Model-written **constraints are suggestions** the person keeps or dismisses | #176 |
| The model writes prose; **only the person's click makes a fact** (the rule from #170/#171, extended) | all |

## 4. Global constraints

- **Asynchronous, never chatty** (operator: *build these things async and optimized; don't spam
  calls to the server*). No new polling loop; a model call is always a queued job on the AI
  worker, never made inside a request; a view is fetched only when opened or when its total moves.
- **Nothing a model writes becomes a fact on its own.** Suggestions pre-fill; the click records.
- **A prompt change is a new version file**; retired versions stay loadable (`prompts.RETIRED`).
- **Recorded replies in tests, never a live model** (`test_no_live_model.py`).
- **Migrations run against the throwaway test database** (`alembic upgrade head` there first).
- **The app assumes nothing about the model server's configuration.**

---

## 5. What we keep and show of each model call (#182, #191)

### Stored

- **`ai_invocation.response`** (text, nullable): exactly what the model returned, admitted or
  refused; empty for a call that never reached a provider. The transport already holds the text
  (`Client.respond`); it stops discarding it.
- **`ai_invocation.session_id`** (nullable, indexed): set on every builder call — goal, chat, gap
  reply, phrasing, read-back, and a Spawn build's tier-4 answers; null on forge rows.
- **`ai_invocation.cached_tokens`** (integer, nullable): LiteLLM's
  `prompt_tokens_details.cached_tokens`, so the payoff of §6 is visible.
- One migration adds all three.

**Recorded loosening (level 0).** A reply can echo the person's words, so `response` is a new
free-text store. The protection table in `docs/design/authoring-protocol.md` gains a row: stored at
level 0; each future level decides. `tests/guards/test_egress.py` gains a note beside
`FREE_TEXT_FIELDS` that `response` is stored, never sent (it crosses no door).

### Shown

- **The session view** gains `usage: {input, output, cached, calls, in_flight}`, summed in the
  query that already builds it. The page's existing poll carries it; the poll still stops when
  nothing is pending.
- **`GET /pipeline/authoring/{id}/calls`** lists the session's calls: purpose in plain words
  (*reading your request*, *phrasing a question*, *reading your reply*, *writing the read-back*,
  *choosing between tools*), model, tokens in/out/cached, duration, state, and the reply.
- **The header strip** shows *12.4k tokens · 7 calls* (and *thinking…* while `in_flight`).
  Clicking opens a panel with the call list, fetched on open and again only when `calls` changes;
  each reply is collapsed until opened.

## 6. Prompts, caching, and the model server (#183, #184, #185)

### The split

Every builder prompt gets a new version carrying a divider line, `<!-- then, per call -->`.
Everything above it is the **system message**; everything below, the **user message**. The client
sends `[system, user]` and appends the reply schema to the **system** part.

**Ordered most-shared first,** so different calls share a cached prefix:

1. the builder's invariant block (already identical at the top of every builder prompt);
2. the vocabulary, in prompts that use it;
3. the prompt's own instructions, then the schema;
4. — divider — the conversation, the request, the gap being asked.

**Cache markers** where the provider honours them (Anthropic: after the vocabulary and after the
instructions, as `cache_control` on system content blocks); OpenAI and Ollama cache an identical
prefix themselves.

**New versions:** `builder.goal.v5`, `builder.chat.v2`, `builder.gap.v2`, `builder.tier4.v2`, and
the new `builder.ask.v1` and `builder.readback.v1` born split. v4, v1, v1, v1 join `RETIRED`.

**Transport.** `comeni_ai.Client` gains a two-part send (`generate(system=…, user=…, shape)`);
the one-string path stays for the forge, whose prompts are out of scope. The recorded
`prompt_digest` is over both parts, as sent.

**The rule that makes it pay:** a test renders each prompt's system part for two different
sessions and asserts they are byte-identical — no timestamp, id, or unordered set above the
divider.

### The model server (Docker)

- Compose sets `OLLAMA_KEEP_ALIVE=1h` and `OLLAMA_NUM_PARALLEL=1` on the Ollama service, and the
  image moves from 0.6.5 to the current release.
- **This is the Docker stack's choice, documented as such.** A Kubernetes deployment sets its own;
  the app sends no `keep_alive` and assumes no single-slot server. A short *the model server* note
  in the deployment docs says so.
- **The spike (#185):** re-run the timing probe — an identical prompt twice; two prompts sharing
  the fixed part — after the upgrade and after the split. Its numbers go into #185 whether or not
  prompt evaluation drops.

## 7. The consultant's words (#167, #176, #186)

**The rule:** the model writes the prose; the engine owns what is typed; anything the model adds
to the typed goal is a suggestion the person confirms.

### The first reply

`builder.goal.v5` returns `want`, `stated`, `questions`, and **`ack`**: one short sentence
acknowledging the request (*Gene counts from paired-end RNA-seq — got it. A few questions
first.*), shown as the model's turn. The `summary` field goes. Its `constraints` are stored as
**suggested constraints** beside `stated`, never in the goal.

### Each question: `builder.ask.v1`

- **Given:** the gap's subject and kind, why it is asked, its fixed option ids and labels, the
  declared description, the person's first sentence, and the facts so far.
- **Returns:** `asks` (the question in the person's register) and `already` (an option id or
  value the person already gave, or null).
- **Admission:** `already` is held to the offered ids (MI0205) and the declaration (MI0208) and
  becomes a pre-fill through the existing suggestion mechanism; a failed `already` is dropped and
  `asks` still used. `asks` is prose: bounded length, never parsed.
- **When:** a queued job when a gap is offered, and a **prefetch** for the next gap while the
  current one is answered (#186). The next gap is predictable: each answer removes one gap; a
  stop wastes one call.
- **Shown:** the card appears at once in the engine's wording; when `asks` lands it replaces the
  question text **in place** with a small *phrased for you* note; options never move. A result for
  a gap already answered is dropped. A refusal or failure keeps the engine's wording.
- **Replaces nothing that exists:** `builder.gap` still reads typed replies (§6's `gap.v2`).

### The read-back: `builder.readback.v1`

A queued job when the goal card is offered, given the **composed goal** (inputs, facts with
sources, want, kept constraints). It returns one or two plain sentences; the card shows the
engine's sentence first and swaps in the model's, labelled *in the AI's words*. The chips beside
it are the truth.

### Suggested constraints

The card gains a *suggested* row: each model-written constraint as a chip with its reason (*you
asked for gene-level?*), kept or dismissed. Only kept ones enter the goal, through the card's
edited-goal path, held to the vocabulary (MI0204). Nothing kept → nothing added.

### The protocol

`ask` is the AI's (it was drawn so and was the engine's); a `readback` node joins the card; the
`suggest` node gains constraints. The generated diagram follows.

**Recorded loosening:** phrasing and read-back are prose inside the authoring AI point — they
author no value — so no new `AiPoint` is declared. Written into the protocol page's loosenings for
the operator to reject.

## 8. Errors

- A phrasing or read-back call that fails, is refused, or arrives stale changes nothing visible
  beyond keeping the engine's wording; it is recorded (`ai_invocation`, with its reply) and counted.
- The call list of a session with no calls is empty, not an error.
- A migration run against a database with rows leaves `response`, `session_id` and
  `cached_tokens` null on old rows: true, not a placeholder.

## 9. Testing

- **Stored:** a recorded call writes its reply and session; a refused one writes its reply too.
- **Counter:** two recorded calls move `usage` in the session view; the page shows it without a
  second request (the poll count is asserted).
- **Split:** every builder prompt's system part is byte-identical across two sessions; the digest
  covers both parts; recorded transports keep working.
- **Phrasing:** `already` admitted like `chose`; a stale phrasing dropped; a refused one keeps the
  engine's wording; the prefetch job is enqueued once per gap (job id keyed on the proposal), not
  per poll.
- **Read-back and constraints:** the read-back is given the composed goal; an unkept suggested
  constraint never reaches the goal.
- **Frontend:** the count and panel (fetched on open only); the in-place swap keeps the options
  and their order; the suggested-constraint row.
- **The walk:** scenario 1 again, with the two measurements (§2.4) recorded.

## 10. Build order

1. **What we keep and show** (§5): migration, stored reply and session, `usage`, the call list,
   the header count and panel. Everything after is measured by it.
2. **The model server** (§6, Docker): keep-alive, one slot, the upgrade, the first timing run.
3. **The split** (§6): transport, new prompt versions, the identical-prefix test; the second
   timing run.
4. **The consultant's words** (§7): `goal.v5` with `ack` and suggested constraints, `ask.v1` with
   prefetch and the in-place swap, `readback.v1`, the card, the protocol.
5. **The walk:** scenario 1, both measurements, findings filed.

## 11. Open questions

- Cost in money (LiteLLM `completion_cost`) and its currency — the settings menu (14.7.5).
- Whether the call panel should also exist in the manual builder (it has no conversation today).
- Retention of `response` beyond the session — none decided; a line for the protection table
  before level 1.
