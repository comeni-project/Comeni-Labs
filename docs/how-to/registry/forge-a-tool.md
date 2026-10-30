---
title: Forge a tool
description: Turn an nf-core module the registry does not hold into approved registry files, with the AI or by hand.
---

# Forge a tool

Forging turns an nf-core module the registry does not hold into the files the registry needs:
its contract (what it reads and makes, and how it is wired), its settings, any new vocabulary
and rules. The AI can draft each piece, or you can write it yourself. **Nothing the AI proposes
counts until you approve it.**

## Start

1. In **Registry → Catalogue**, pick a module that is *not imported*.
2. Choose **Forge \<name\>**. The adaptation opens; it is also listed under **Forging**.

To change a tool the registry already holds, open its page and choose **Re-forge**: the
registry's current contract becomes the starting proposals.

## Work through the pieces

The pieces go in order, each once the one before it is approved: **Questions**, **Contract**,
**Parameters**, **Vocabulary**, **Rules**.

For each piece, choose:

- **Draft with the AI**: the AI reads the module's `main.nf` and `meta.yml` and proposes each
  item with its reason. It runs in the background; the page shows *drafting…* until it lands.
- **Write it myself**: enter an item and its value. What you write counts as your decision.

A question is answered, not approved: choose one of its options, or give an answer of your own.
The AI may mark the option it suggests; only your choice counts.

Then, for each other item:

- **Approve** it, so it counts.
- **Change** it: your value counts as your decision.
- **Reject** it: the chat opens on that item. Tell the AI what is wrong and it proposes a
  revision, or write the value yourself. A rejected item holds its piece until it is fixed.

**Approve the rest** approves the items still waiting in the current piece, except questions and
any removal the AI proposes: each of those needs a decision of its own. A piece that needs nothing
is said explicitly, for example *rules: none needed*.

Every item keeps its history: what the AI proposed, what you changed, and who approved it.
If two people (or two tabs) act on the same item, the second is refused and asked to reload.

## Talk to the AI

The chat beside the pieces is open the whole time. Ask about the tool, a piece or one item, or
suggest something ("why not a rule for viral genomes?"). The AI may answer with proposals,
shown as cards: a revised value, a new item, or the removal of one. You approve, change or
reject each card. The AI cannot approve anything.

Changing something already approved re-opens what depends on it: a changed port re-opens the
settings wired to it. A re-opened item keeps its value and waits for your approval again.

## Assemble

When every piece is approved, choose **Assemble**. The forge writes the registry files into a
draft layer and checks them with the builder's own code:

- the draft **loads** over the registry, and
- its contract **conforms** to the module's `main.nf`.

If a check fails, the message says why and the piece it blames re-opens. Nothing is written
into the registry.

## Run its tests

The last piece, **Tests**, says what a tool runs on and what must come out. The AI drafts it from
nf-core's own test, or you write it. A test's inputs are files in nf-core's public `test-datasets`,
pinned to a commit, and every output is either expected by a file pattern or given a reason it
cannot be. A tool needs at least one test.

Once assembled, choose **Run its tests**. Each test runs in Wiener as a small pipeline of this tool
alone, so it shows on the runs board like any other run. A failed test says what was missing and
links to its run; change what is wrong, assemble again and run them again.

**Green** means each run succeeded and every declared output exists. It shows the tool runs through
Comeni's wiring and settings. It does not show that its results are correct, and it counts only
for the draft it ran on: any later change needs the tests run again.

Without `MENDEL_WIENER_URL` set, the page says tests cannot run, and forging still works up to
assembly.

!!! note "Not built yet"
    Publishing a tool to `comeni-registry` by pull request (issue 366) comes next. Until then, an
    assembled draft stays in the forge's working folder.

## Forge tools that build on each other

Once an adaptation is assembled, later adaptations may use its new types and roles before they
reach the registry; they are marked as *pending*. If the earlier adaptation changes or is
abandoned, the later one says so and re-opens the items that used them.

## Choose the model

Forging uses the model set for **Adapting tools** in **Settings → Models**: an API model or a
local one. See [Model configuration](../development/configure-model.md).
