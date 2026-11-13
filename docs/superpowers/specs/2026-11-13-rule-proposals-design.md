# Mendel proposes rules from people's answers (#462, part 6 of #463)

## Why

A question the rules cannot settle goes to a person (tier 4). When people keep giving the same
answer on the same facts, that answer is a rule nobody wrote down. This part closes the loop:

1. Mendel notices the pattern.
2. It proposes the rule row, citing the decisions it came from.
3. The engine checks it, and replays it against past builds to show what it would change.
4. A person approves it.
5. The next build settles that question by the rule instead of asking.

## What a person sees

A **Learned rules** page in the registry area lists what Mendel proposes. **Propose** asks the
model again for every target with new answers. Each proposal shows:

- **the row**, in the rule table's own words: when the facts are these, choose this, with the
  model's reason, marked as the model's;
- **its evidence**, every past decision it came from: the pipeline, the facts, the answer and
  who gave it;
- **the engine's check**: whether the rule table it would join loads, with gaps, overlaps,
  constraints and citations checked as for any rule. A proposal that fails says why and cannot be
  approved;
- **the replay**, over every kept pipeline:
  - which decisions the row would have settled;
  - whether its answer agrees with the one recorded;
  - which recorded answers it would have changed, listed first.

The person approves or rejects. An approved rule is listed under **In use**, where it can be
withdrawn. A rejected proposal is not proposed again unless its evidence changes.

## Decisions

1. **The model proposes; the engine checks** (operator, 11-13). A model is more flexible than a
   computed learner: number thresholds, two facts at once, a person's stated reasons turned into
   the row's `because`. Builds stay reproducible either way. A proposal is a suggestion until a
   person approves it, and from then on it is a fixed rule in a file. The model's part stays
   visible: each proposal records its model call, and stays flagged as the model's until approved.
2. **The only source is people's tier-4 answers.**
   - **Not sources or failures.** Proposals from sources (manuals, module code) and failed runs
     use the same model point, and come later.
   - **Not the memory of precedents.** It comes with tuning how much the AI does.
3. **What counts as evidence:**
   - **Where it comes from:** a decision in a kept pipeline (`pipeline.yml`'s `decisions`). It
     must be tier 4, answered by a person (`human_override` set), and chosen among two or more
     candidates.
   - **What it covers:** a tool choice (`producer`) or a setting's value (`param`). A model's
     answer is never evidence, and neither is a tool drawn when it had no alternative.
   - **Facts:** those the pipeline was built on (`facts.measurements`), study-wide values only. A
     per-sample list is left out.
   - **Grouping:** cases are grouped by what they decide.
     - A tool choice decides `{effect: implementation, of: <role>}`. The role is the one every
       candidate fills; a choice whose candidates share no single role is skipped.
     - A setting decides `{effect: param, of: <role>, name: <param>, when_implementation:
       [<contract>]}`.
   - **When the model is asked:** a target with at least **3** person answers. This threshold is
     the first knob for how much the AI does.
4. **What the model is given and gives back.** It is asked once per target that has enough
   evidence and new answers.
   - **Its input** is a declared payload (`rule_proposal`):
     - the target in words;
     - the existing table's rows, if any;
     - the facts it may test, with their kinds and allowed values;
     - the legal answers (the candidate tools, or the setting's domain);
     - the cases: facts, answer, and the reason the person gave where one was recorded.
   - **Its reply** is rows (`when`, `then`, `because`) or none, with why.
5. **The engine checks every proposal.** A reply that fails is sent back once with its problems,
   as the forge does. A second failure is recorded, and nothing is proposed. A proposal is held
   to all of these:
   - **It is a row the registry accepts.** It is a valid `DecisionRow`, and every fact it tests
     is declared.
   - **It is appended.** The new rows go after the existing table's rows (`hit: first`), so they
     only fire where the existing rows all missed, which is when the question was asked.
   - **It agrees with the evidence.** For every case, the first matching row of the whole table
     gives the answer the person gave. A row that would contradict a recorded answer is refused,
     and the problem names the case.
   - **It is supported.** Every new row matches at least one case. The model cannot invent a row
     the evidence does not reach.
   - **The table loads.** It is written into a candidate copy of the installation's layer, and the
     stack is loaded. Whatever the loader refuses is the finding, with its diagnostic code: gaps,
     overlaps, a value outside a setting's domain, or a tool that does not fill the role.
   - **Its `cite`** is set by the engine, not the model: `kept pipelines <ids>, decision <key>`.
6. **The replay evaluates; it does not rebuild.** For each kept pipeline that decided the same
   target, the proposed table is evaluated against its recorded facts and compared with the
   answer recorded. Answers it would change are listed first; for model or rule answers this is
   information, not a refusal. Builds and their artifacts are not touched.
7. **Proposals are stored, not recomputed.** Each is a row in `rule_proposal`:
   - the target and rows;
   - the evidence digest;
   - its model call (`ai_invocation`);
   - its status: proposed, approved, rejected, withdrawn or superseded.

   The page's **Propose** button asks again for each target whose evidence digest has changed
   since its last proposal. It runs as a background job, like a forge draft. A rejected proposal
   returns only when the evidence changes. With no model configured, the page says so and
   proposes nothing.
8. **Approved rules live in the installation's own layer.**
   - **Where:** a registry layer at `<workspace>/layer` (`MENDEL_OWN_LAYER`), stacked above the
     registry release. Every place the installation reads the registry to build reads the stack.
   - **What is written:** an approved proposal writes its whole table to
     `rules/learned/<target>.yml`. It displaces the release's table for that target, and the
     displacement is recorded as for any layer. The file's leading comment says who approved it,
     when, the model call, and the evidence.
   - **Pinning:** a pipeline built afterwards pins that layer by digest.
   - **Withdrawing** removes the file.
   - **Upstream:** proposing the rule to comeni-registry comes later.
9. **The model setting is the forge's.** It is registry work, so it uses Settings → Models →
   *Adapting tools* (agent `forge`, purpose `analysis`). There is no new setting.

## A tool now, a core server later

Comeni is a tool a lab installs, not a platform. This part learns from one installation's own past
pipelines. Later, a core server might gather cases from many installations and propose rules
upstream to comeni-registry.

The design keeps that open without building it. The work is split into three parts, so a server
can replace either end without touching the middle:

- **The evidence and the checks are pure.** They live in `mendel-resolver` and make no I/O. Their
  input is a list of `Case` records:
  - what was decided;
  - the study facts;
  - the answer;
  - who answered (a person);
  - a reference to the pipeline and decision.

  They do not know where the cases came from, and the model's payload is built from the same
  records.
- **The source is an adapter.** Here it reads this installation's kept pipelines. A core server
  would read cases that installations submit.
- **The sink is an adapter.** Here an approved rule goes to the installation's own layer. A core
  server would open a registry pull request.

A `Case` holds only decisions and study facts, never sample names, keys, references or file
names. It can later become a declared egress payload without changing shape. Sending cases
anywhere needs its own design and the operator's decision, and is not built here.

## Constraints

- **Only decisions and facts reach the model,** through the declared `rule_proposal` payload: the
  study facts, the answers and the reasons people typed with them. A fact can name an organism or
  a read length. No sample names, keys, references, file names or sample data are sent. The egress
  guards hold the payload to that, as they do every door.
- **Recorded.** Each model call is an `ai_invocation` with its prompt digest and reply. A proposal
  names it, and an approved file's comment does too. Payload collections are sorted.
- **Sample names never enter a proposal.** A proposal cites pipeline ids and decision keys; sample
  names, keys and references are not in decisions or study facts.
- **Scale.** 400–500 kept pipelines must list in well under a second. Reading is one pass over
  their `pipeline.yml` files, cached on the set of kept digests.

## Not in this part

- Proposals from sources and from failed runs.
- The memory of precedents for the model at tier 4.
- Publishing a learned rule to comeni-registry.
- Learning `source` decisions (which upstream output feeds a port).

## Done when

- Three kept pipelines in which a person chose the same aligner produce, from a recorded model
  reply, one proposal with its evidence, a clean check and a replay.
- A reply whose row contradicts a recorded answer is sent back once, then refused, naming the case.
- Approving it makes the next build of the same goal choose that aligner at tier 3, citing the
  learned rule, with the installation layer in the pipeline's registry provenance.
- Withdrawing it makes the question come back.
