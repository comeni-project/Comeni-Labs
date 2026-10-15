# Maintain the documentation

<!--
Serves: all four steps.
-->

Organize pages around the reader's need using [Diátaxis](https://diataxis.fr/).
The documentation has four paths, each containing multiple pages:

| Form | Purpose | Comeni example |
|---|---|---|
| Tutorial | Teach through a guided experience with a concrete outcome. | Build and run a first pipeline. |
| How-to guide | Help someone who knows their task complete it. | Configure a model or write a registry rule. |
| Reference | Describe interfaces precisely and consistently. | CLI flags, schemas and diagnostics. |
| Explanation | Develop understanding of concepts and design choices. | Decision tiers and construction boundaries. |

A tutorial may briefly explain a concept, then link to its fuller explanation.
A how-to guide may show the necessary settings, then link to their complete reference.
Give each maintained subject one home; other pages should introduce it only as needed.
The four paths do not require every file to be moved into four directories.

## Plan a page or related group

Identify the intended reader, the question or task, and the useful facts already present.
Check relevant source, commands, configuration and tests before repeating a behavior claim.
Separate implemented behavior from a proposal and state limitations beside the affected task.

When a page mixes forms, decide which sections to retain, move or combine before rewriting.
Record destinations for moved content. Keep plans and journals identifiable as historical
records; they are not authoritative instructions for the current product.

## Rewrite while preserving information

Use `redocument-file` when available to edit one page, section or related group.
Before editing, inventory purpose, behavior, interfaces, prerequisites, defaults, side effects,
constraints, useful examples and rationale. Compare the result against that inventory.

Preserve information or move it to a linked home. Remove duplicated explanations, empty
framing and incidental statements about when work was done. Release history belongs in
`CHANGELOG.md`; session records belong in working notes. Keep a concise reason when it
explains a current constraint. Report meaningful omissions and their reasons.

Write purpose and behavior first. Use task-based headings for instructions and terminology
appropriate to the reader. User tutorials start from the browser workflow; developer and
CLI tasks can start from commands. Explain internal package names when they help developers
understand ownership, rather than requiring product users to learn them.

Use the RNA-seq counts example across user guides where it fits. Introduce concrete examples
before linking to full schemas. Derive volatile counts from source or commands.

## Show the interface where it matters

Use screenshots where readers need to recognize a screen and diagrams where they need to
understand boundaries or flow. Assets live in `docs/assets/screenshots/`; replace placeholders
with current captures and check that existing captures still match the documented workflow.
Do not present a placeholder as evidence that the interface was verified.

Describe current alpha behavior directly. Identify expected changes separately, and retain
stable concepts where they help the reader understand a moving interface. A page should make
clear what can be done today and what prerequisites that requires.

## Verify a documentation change

Run the affected documentation checks:

```bash
make docs docs-status links doc-paths doc-sizes
make wiki
```

`make wiki` generates the tool catalogue and builds the site strictly.
After changing navigation, inspect the rendered paths and confirm every maintained page
remains reachable. Existing URLs should remain stable unless a move has a clear benefit and
all incoming links have been updated.

Checks detect selected kinds of drift; they do not verify every behavioral claim or establish
that a tutorial can be completed. Review the reader's route separately. Document any steps
that were checked only against source and those exercised in the running app.

## Stage badge and offline use

Set `extra.stage` in `mkdocs.yml` to change the header badge. The theme hook generates
`assets/stage.css` from that value; avoid duplicating the label in authored CSS.

The built site supports reading and search through `file://` without network access.
The search worker shim is bundled under `docs/assets/vendor/iframe-worker/`, with its license
and version recorded beside it. Keep `extra.polyfills` pointed at that local copy.
Custom Geist fonts use a CDN and fall back to installed sans-serif and monospace fonts offline.
Local-file browsing displays Mermaid diagrams as readable source, keeping search usable without
the external renderer. Use a local HTTP server with network access to view rendered diagrams.

After changing the theme or offline plugin, build the site and open `site/index.html` with a
fresh browser profile and network access disabled. Verify readable content, the configured
badge and a search that returns known pages. Repeat from a nested page to check relative
asset paths. A warm browser cache can conceal missing bundled dependencies.
