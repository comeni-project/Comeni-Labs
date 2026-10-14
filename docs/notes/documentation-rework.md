# Documentation rework: map and preservation record

Working review record for the first Diátaxis pass. This is excluded from the published
site. It records destinations and unresolved work rather than teaching the product.

## Scope and method

The first batch establishes four reader paths without moving existing task and reference
URLs. README introduces the product; docs/index routes readers; CLAUDE contains agent
instructions; contributor procedures have one published home. The architecture introduction
now maps ownership, while detailed construction sections remain for a later section-by-section
pass. No runtime code, dependency declarations or deployment behavior changed. Existing wiki
structure tests were updated to check the four paths, their landing pages, catalogue access
and preserved URLs. The required internal-page scope marker is retained as an HTML comment
so validation metadata does not interrupt the reader.

Use Diátaxis to decide the purpose and destination, then redocument-file to rewrite a page
or related group. Inventory useful information first and compare it after editing. Shorter
prose is not sufficient evidence of a successful edit.

## Content map

These are navigation destinations. Placement does not mean the deeper page has already
been fully rewritten or its procedure walked in the app.

| Existing material | Path / responsibility | Action and remaining review |
|---|---|---|
| README.md | Repository introduction | Rewritten; start commands, naming, contribution routes and licences retained. |
| docs/index.md | Four-path entry point | Rewritten; duplicate loop diagram removed; reader routes retained. |
| CLAUDE.md | Agent instructions | Kept operational instructions; linked contributor and documentation policy. |
| .github/CONTRIBUTING.md | GitHub contribution entry | Links to the full published guide; registry/code split, order and security link retained. |
| docs/internals/contributing.md | How-to: contribute | Receives contributor setup, checks, boundaries, style, diagnostics, release and conduct guidance. |
| ARCHITECTURE.md | Explanation: implementation | Introduction and ownership map rewritten; detailed sections retained. Later split by subject only after verifying the sections. |
| docs/start/index.md | Legacy entry point | Retained URL; routes to installation, tutorial and four paths. |
| docs/handbook/index.md | Legacy pipeline entry point | Retained URL; routes by reader need. |
| docs/internals/index.md | Legacy developer entry point | Retained URL; points to procedures and explanations. |
| handbook/your-first-pipeline.md | Tutorial | Retained sequence, examples and assets; corrected entry label and model prerequisite. Full browser walkthrough still needed. |
| handbook/rnaseq-example.md | Tutorial companion | Kept scientific context; later assess overlap with the walkthrough. |
| start/install-and-open.md | How-to: install | Retained; corrected prerequisites and optional telemetry. |
| handbook/builder.md | How-to: use builder | Retained; later separate screen reference and design explanation from task steps. |
| handbook/reviewing-decisions.md | How-to: review | Retained; later link to the tier explanation rather than repeat it. |
| handbook/running-pipelines.md | How-to: run | Retained app and plain Nextflow paths; verify current input form. |
| handbook/watching-runs.md | How-to: monitor | Retained; later separate interface inventory from investigation tasks. |
| handbook/the-stack.md | How-to: development | Moved in navigation, URL retained; renamed worker and marked telemetry optional. Later separate service reference and model configuration. |
| registry/using-the-forge.md | How-to: draft/review | Retained; verify current review and acceptance sequence. |
| registry/writing-a-contract.md | How-to: add contract | Retained; later separate schema details already owned by reference. |
| registry/making-a-choice-depend-on-your-data.md | How-to: add rule | Retained; later separate validation and design explanations. |
| registry/your-labs-own-layer.md | How-to: add layer | Retained; later separate stacking semantics from procedure. |
| internals/walking.md | How-to: investigate | Retained; separate recorded regression evidence from maintained procedure in a later pass. |
| internals/releasing.md | How-to: release | Retained; preserve versioning constraints and refusals. |
| internals/documentation-style.md | How-to: maintain docs | Rewritten with Diátaxis, evidence and preservation procedure. |
| handbook/reference/{cli,diagnostics,pipeline-schema,goal-schema,glossary}.md | Reference | Retained exact paths and generated-file ownership. |
| registry/reference/{contract-schema,rule-schema,vocabulary-schema,measurement-schema}.md | Reference | Retained; verify generated/reference checks before editing. |
| tools/index.md and generated catalogue/pages | Reference: available tools | Retained generator and catalogue routes; no hand edits to generated pages. |
| status.md | Reference: doc notices | Retained generated file; new entry points describe its limited scope honestly. |
| handbook/product-loop.md | Explanation: lifecycle | Retained; later remove repeated introductions and verify current workflow. |
| handbook/core-words.md | Explanation: concepts | Retained; glossary owns concise definitions, this page should explain relationships. |
| handbook/the-four-tiers.md | Explanation: tiers | Retained; later compare against architecture and make ownership explicit. |
| handbook/how-tools-get-chosen.md | Explanation: selection | Retained; preserve data-change example and connect to tier semantics. |
| handbook/inputs-alpha.md | Explanation: data boundaries | Retained; privacy and retention claims need source verification. |
| registry/index.md | Explanation: registry knowledge | Kept substantive concept/examples; placed in Explanation. |
| design/invariants.md | Explanation: constraints | Retained; inherited stale egress filename described as the former module. Historical and current claims still need separation. |
| design/authoring-protocol.md | Explanation: conversation | Retained; has current design, proposals, loosenings and changelog mixed together. Later separate without losing decision rationale. |
| design/voice.md | Explanation: product language | Retained examples and scope. |
| design/diagrams/*.md | Explanation: protocol diagrams | Kept diagram pages; preserved index URL. |
| notes/ and superpowers/ | Working state and historical records | Kept outside published navigation; no archive pruning or rewriting. |
| deliverables/ | External project material | Preserved; not automatically treated as current product instructions. |
| Package, test and registry READMEs | Local component documentation | Outside this batch; preserve beside the code and review when their reader path is addressed. |

## Preservation decisions

| Source information | Result |
|---|---|
| Product purpose, portable Nextflow and visible model contributions | Retained in README and docs homepage. |
| Name origin and licences | Retained in README; contribution licensing retained in the guide. |
| README claim about MIT/Cambridge research | Removed from product introduction: no cited study or concrete design dependency was supplied. This does not remove implementation rationale. |
| README promise to launch on laptop/HPC/Kubernetes/cloud | Separated portability from app execution: generated profiles are not integrated launch targets. |
| First-run commands and recursive clone | Retained; added Node/npm and Compose prerequisites verified in Makefile. |
| Repeated loop diagrams and claims about how the books are organized | Removed from entry points; lifecycle explanation and tutorial remain linked. |
| Contributor setup and check commands | Moved to internals/contributing.md; corrected database setup and full check scope. |
| Guard table and network/egress/profile boundaries | Retained in published contributor guide; fixed guard locations and removed stale counts. |
| Guard-failure evidence, determinism, module-source authority and generated-file review | Retained; incidental failure anecdotes removed. |
| Test-first work, issue workflow, specs/plans and commit/PR guidance | Retained; corrected plan locations and preserved explicit user authorization. |
| Diagnostic declaration, emission, regeneration, unused-code refusal and stable numbering | Retained; distinguished generator command from make docs, which checks freshness. |
| Versions, review of bumps, security reporting, licensing and conduct | Retained; removed date/story about the retired conduct file. |
| Architecture component table and execution boundary | Retained responsibilities; replaced removed design-page pointers with current docs and source context. |
| Architecture schema details, examples, signatures and lower-section rationale | Retained in place; not claimed to have been fully verified or cleaned yet. |
| Architecture source-path guard explanation | Corrected scope: checks selected package paths, not every named path or behavior. |
| App-first examples, alpha distinctions, screenshots and RNA-seq reuse | Retained in documentation guidance; applies to appropriate reader needs rather than all documentation. |
| Agent instructions and operational cautions | Retained; added links to human documentation and preservation rules. |

## Evidence and remaining work

Setup and check descriptions were read against Makefile and the CI workflow. Home entry
behavior was checked against frontend/src/home/First.tsx and Home.tsx. Worker naming and
optional telemetry were checked against Compose and Makefile. Artifact transfer was checked
against the Wiener upload route. The source inspections do not establish that a new user can
complete the tutorial; no local model or pipeline run was started for this documentation pass.

Next batches should address one complete route at a time: installation and first pipeline;
review and execution; registry contribution; developer architecture. For each, verify current
behavior, separate mixed forms, preserve information and update incoming links before removal.
The tutorial's saved screenshots and steps require a browser walkthrough. Privacy claims need
particular attention because protection-level exceptions and stored replies are documented
inconsistently. Zero future-feature markers on status.md is not proof of feature completeness.

Detailed architecture still contains historical narratives and proposed or stale claims.
Preserving those sections in this first batch prevents useful rationale being discarded before
its destination is known; they remain explicitly pending review.

## Validation of this batch

- Repository tests: 138 passed.
- Generated reference, status, links, source paths and line budgets: passed.
- Ruff on the updated wiki tests and git diff whitespace check: passed.
- Strict MkDocs site build: passed after installing the locked docs dependency group.
- Built HTML: four homepage routes, path landing pages and their local link destinations verified.
- No browser walkthrough, local model call, database migration or real pipeline run performed.

Edits are left uncommitted for review. No documentation skill has been created yet.

## Physical migration and section ownership

Maintained content now lives under tutorials/, how-to/, reference/ and explanation/.
Old addresses are short forwarding pages excluded from navigation and search. They retain
historical references without duplicating maintained content. The tool catalogue remains a
generated tree under tools/; its authored introduction is reference/tools.md. Assets and
external deliverables remain separate. No plans, journals, research records or fixtures changed.

| Mixed material | Instruction destination | Other retained information |
|---|---|---|
| Builder | how-to/pipelines/build.md | Controls/status in reference/pipelines/builder-interface.md; upload procedure in how-to/pipelines/answer-with-sample.md; input direction in explanation/inputs-and-data.md. |
| Local stack | how-to/development/local-stack.md | Model setup in how-to/development/configure-model.md; service ownership in reference/development-services.md. |
| Tool contract | how-to/registry/add-tool.md | Semantic states and before/after examples in explanation/tool-contracts.md. |
| Rule authoring | how-to/registry/write-rule.md | Data-backed choice and reachable-pin explanation in explanation/data-backed-rules.md. |
| Lab layers | how-to/registry/add-layer.md | Stacking policies, extension examples and loader API in explanation/registry-layers.md. |
| Architecture | explanation/architecture.md | Root ARCHITECTURE.md forwards to the full document. |

Corrected claims after source inspection: sole compatible producer is structural; bounded
sample handling can queue text and record model replies; first-run language entry depends on
model configuration; ai-up can pull its server image even though it does not pull model weights.
Removed unsupported prose counts, discovery anecdotes and outdated release-status statements.
Retained schema tables, module signatures, YAML examples, command sequences, migration syntax
constraints, diagnostic identities, sample bounds, review responsibilities and design rationale.

Historical sections embedded in protocol, invariant, architecture and investigation pages
remain preserved for the later records pass. Moving their containing page does not constitute
reviewing or rewriting that history. Deep behavioral verification remains separate from the
source and link checks completed here.

### Canonical locations and compatibility addresses

| Previous address | Maintained destination |
|---|---|
| `ARCHITECTURE.md` | `docs/explanation/architecture.md` |
| `docs/start/install-and-open.md` | `docs/how-to/install.md` |
| `docs/handbook/your-first-pipeline.md` | `docs/tutorials/first-pipeline.md` |
| `docs/handbook/rnaseq-example.md` | `docs/tutorials/rnaseq-example.md` |
| `docs/handbook/builder.md` | `docs/how-to/pipelines/build.md` |
| `docs/handbook/reviewing-decisions.md` | `docs/how-to/pipelines/review.md` |
| `docs/handbook/running-pipelines.md` | `docs/how-to/pipelines/run.md` |
| `docs/handbook/watching-runs.md` | `docs/how-to/pipelines/watch.md` |
| `docs/handbook/the-stack.md` | `docs/how-to/development/local-stack.md` |
| `docs/handbook/product-loop.md` | `docs/explanation/pipeline-lifecycle.md` |
| `docs/handbook/core-words.md` | `docs/explanation/pipeline-concepts.md` |
| `docs/handbook/the-four-tiers.md` | `docs/explanation/decision-tiers.md` |
| `docs/handbook/how-tools-get-chosen.md` | `docs/explanation/tool-selection.md` |
| `docs/handbook/inputs-alpha.md` | `docs/explanation/inputs-and-data.md` |
| `docs/registry/index.md` | `docs/explanation/registry.md` |
| `docs/registry/using-the-forge.md` | `docs/how-to/registry/review-proposals.md` |
| `docs/registry/writing-a-contract.md` | `docs/how-to/registry/add-tool.md` |
| `docs/registry/making-a-choice-depend-on-your-data.md` | `docs/how-to/registry/write-rule.md` |
| `docs/registry/your-labs-own-layer.md` | `docs/how-to/registry/add-layer.md` |
| `docs/internals/contributing.md` | `docs/how-to/development/contribute.md` |
| `docs/internals/documentation-style.md` | `docs/how-to/development/documentation.md` |
| `docs/internals/releasing.md` | `docs/how-to/development/release.md` |
| `docs/internals/walking.md` | `docs/how-to/development/investigate.md` |
| `docs/design/invariants.md` | `docs/explanation/invariants.md` |
| `docs/design/authoring-protocol.md` | `docs/explanation/authoring-protocol.md` |
| `docs/design/voice.md` | `docs/explanation/product-language.md` |
| `docs/design/diagrams/README.md` | `docs/explanation/diagrams/index.md` |
| `docs/design/diagrams/authoring-protocol.md` | `docs/explanation/diagrams/authoring-protocol.md` |
| `docs/tools/index.md` | `docs/reference/tools.md` |
| `docs/status.md` | `docs/reference/status.md` |
| `docs/handbook/reference/cli.md` | `docs/reference/pipelines/cli.md` |
| `docs/handbook/reference/diagnostics.md` | `docs/reference/pipelines/diagnostics.md` |
| `docs/handbook/reference/pipeline-schema.md` | `docs/reference/pipelines/pipeline-schema.md` |
| `docs/handbook/reference/goal-schema.md` | `docs/reference/pipelines/goal-schema.md` |
| `docs/handbook/reference/glossary.md` | `docs/reference/pipelines/glossary.md` |
| `docs/registry/reference/contract-schema.md` | `docs/reference/registry/contract-schema.md` |
| `docs/registry/reference/rule-schema.md` | `docs/reference/registry/rule-schema.md` |
| `docs/registry/reference/vocabulary-schema.md` | `docs/reference/registry/vocabulary-schema.md` |
| `docs/registry/reference/measurement-schema.md` | `docs/reference/registry/measurement-schema.md` |
| `docs/start/index.md` | `docs/how-to/index.md` |
| `docs/handbook/index.md` | `docs/index.md` |
| `docs/internals/index.md` | `docs/how-to/development/contribute.md` |

### Migration validation

Repository tests: 138 passed. Full Ruff check, generated references and diagrams, status,
Markdown links, named source paths, line budgets and strict MkDocs build passed. All local
link destinations in 50 canonical rendered pages exist. Legacy forwarding pages are excluded
from the search index. A comparison against HEAD accounts for all 58 original YAML, Python
and shell example blocks across the canonical destinations (command comments excluded from
the comparison). This is example-preservation evidence, not proof that every instruction was
executed. Existing status notes, journals, research, plans, specs and fixtures have no diff.
No browser walkthrough, local model call, database migration or real pipeline run was performed.
Changes remain uncommitted for review.

## Source-tree cleanup

Removed design/, handbook/, internals/, registry/, start/, tools/ and status.md from the docs
source tree after confirming they contained forwarding pages or generated tools. Generated
catalogue pages now live in reference/tools/; the authored introduction remains reference/tools.md.
Makefile, ignore rules, catalogue generation, navigation and generated-link checks use that path.

Old site addresses are generated in memory by tools/documentation_locations.py using the explicit
location map. They do not recreate source folders and are excluded from search. Historical path
checks accept a mapped old address only while its canonical destination exists. Development-guide
scope checks now follow how-to/development/ instead of the retired internals/ directory.

Validation: 146 repository tests passed; lint, generated references, status, links, source paths,
line budgets and strict site build passed. Built HTML links, including legacy forwarding pages,
resolve locally. After rebuilding, docs/ contains exactly the four paths, assets/, deliverables/,
notes/, superpowers/ and index.md. Existing status notes, journals, research, plans, specs and fixtures
remain unchanged. Changes remain uncommitted.
