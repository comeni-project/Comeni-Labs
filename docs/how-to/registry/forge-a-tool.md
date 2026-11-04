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
**Parameters**, **Vocabulary**, **Rules**, **Tests**.

For each piece, choose:

- **Draft with the AI**: the AI reads the module's `main.nf` and `meta.yml` and proposes each
  item with its reason. It runs in the background; the page shows *drafting…* until it lands.
- **Write it myself**: choose what to add, then fill in its fields. Channel names come from the
  module; content types, jobs and tools can be picked from the registry. What you write counts
  as your decision. A refusal keeps your entries and explains what needs fixing; a successful
  save names the item.

A question is answered, not approved: choose one of its options, or give an answer of your own.
The AI may mark the option it suggests; only your choice counts. After answering, the question
stays visible and your chosen option is marked. Each question shows what the
answer decides, relevant module lines and upstream descriptions, and the registry's explanations
and existing uses. An output can name its content, such as `qc.report::assembly`, separately from
its file format, such as `tsv`. A new content state needs an approved vocabulary proposal before
assembly. Approved answers marked as new also permit a contract draft to reference a new type
or job before the Vocabulary piece. They do not declare it: Vocabulary still needs the separate
entry before Assembly will load it. A process-only contract stays unfinished; approve at least
one input or output port as well.

To get a second model's advice, choose **Settings → Models → Reviewing tool drafts**. This is
**Off** until you choose a model, even when a default model is configured. The reviewer runs after
a piece is drafted and adds a comment to each item. It cannot change or approve items. Quotes
appear only when found verbatim in the named module file; comments disappear when their item
revision changes. A failed review leaves the piece available for you to decide.

Then, for each other item:

- **Approve** it, so it counts.
- **Change** it: the same form opens with its current fields. Your saved value counts as your decision.
- **Reject** it: the chat opens on that item. Tell the AI what is wrong and it proposes a
  revision, or write the value yourself. A rejected item holds its piece until it is fixed.

A rejected question still needs an answer, correction or explicit removal. If its premise is
false (for example, `meta` is metadata rather than a file), choose **Remove question** and give
a reason. The question, previous answers and removal reason stay in its history; removal lets
that question's piece advance. Removing an approved answer re-opens dependent approved pieces.

**Approve the rest** approves the items still waiting in the current piece, except questions and
any removal the AI proposes: each of those needs a decision of its own. A piece that needs nothing
is said explicitly, for example *rules: none needed*.

A setting has a kind and an optional typed default. Its preview shows the declared argument
text or destination as you edit; the server checks the setting when you save. Rules, tests and
process wiring have controls for adding and removing their rows and named values. Choose
**Nothing needed** with a reason when a piece requires no entries.

Each piece shows its declared details, including nested rule conditions, process wiring and test
setup. The tracker keeps refused draft attempts visible even when they produced no items. Read
the attempt in the chat, then retry with revised instructions or write the piece yourself.

On a decision rule, **Try this rule** accepts hypothetical facts. When the rule reads read length,
a slider and numeric field set that value. The server runs the displayed revision through the
resolver, in row order, and shows all its effects and reasons. A miss remains unresolved; a
changed rule is refused. The preview changes no items and supplies no measured facts to a build.

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

## Publish it

Once the tests are green, choose **Open pull request**. The forge checks out the registry's `main`,
places the tool in the registry's layout with a changelog entry, and runs the registry's own checks
there. If they refuse, nothing is pushed and the chat says why. Otherwise it opens a pull request
whose description records who decided each item and which runs passed.

One forge pull request is open at a time, so the next tool waits until this one merges. A draft adds
files: if it would change a file other tools share, publishing names that file and stops, and that
change is made by hand in `comeni-registry`.

**Approve pull request** merges it, and is available only while registry CI is green. The forge
reads the checks again before merging, and merges exactly the commit it read. The catalogue shows
the tool as *in review*, then *merged, not released*.

To change a tool in review, change the adaptation, assemble and test it again, and open the pull
request again: the old one closes. A merged adaptation is finished; re-forge the tool to change it.

Publishing needs `COMENI_FORGE_GITHUB_TOKEN`, set in `.env` as a deploy secret and held only by the
worker. Without it the page says so, and forging and tests still work. Give it write access to that
repository's contents and pull requests, and nothing else. `MENDEL_REGISTRY_REPO` points the forge
at a different repository, such as a test one.

## Release it

A merged tool is in `comeni-registry`, not yet in anyone's builder. Under **Registry → Releases** you
can see what is merged and unreleased, and cut a release: the page suggests the next version and
notes from each pull request's changelog entry, and you can change both. A release is cut only when
CI on the registry's `main` is green, and it tags exactly the commit whose checks were read.

By default the app follows the newest release: it looks once an hour, fetches a new release into
a read-only folder and switches only if it loads. To stay on one version, set **Registry release**
in **Settings → Registry & sources** to that version, such as `v0.5.0`, or set
`MENDEL_REGISTRY_RELEASE`. A pinned installation never moves. If GitHub cannot be reached, the app
keeps the newest release it has, and with no release yet it uses `MENDEL_REGISTRY_ROOT`. The same
section says what is in use, and why, if that is not what you asked for.

A pipeline built from a release names it, and a kept pipeline is not changed by a newer release.

## Declare a new type family

In **Vocabulary → Write it myself**, choose **Family** and enter its ID and short description.
The family is the first segment of a type ID: `assembly.fasta` belongs to `assembly`. Reuse an
existing family when it fits. A new family needs its own declaration alongside the new type;
approving the type alone cannot make the layer load. AI proposals require your approval.
Assembly writes the approved declarations and checks them together with the registry loader.

## Forge tools that build on each other

Once an adaptation is assembled, later adaptations may use its new types, families and roles before they
reach the registry; they are marked as *pending*. If the earlier adaptation changes or is
abandoned, the later one says so and re-opens the items that used them.

## Choose the model

Forging uses the model set for **Adapting tools** in **Settings → Models**: an API model or a
local one. See [Model configuration](../development/configure-model.md).


## Follow progress

**Registry → Forging** lists current adaptations with approval progress, excluding removed items.
Filter by **Needs you**, **Working**, or **In review or merged**. The author is shown when recorded.
The tool page draws its declared inputs and outputs; pick a pin to reach the port details.
Assembly shows the steps through tests, pull request and merge. Published registry versions remain
on **Registry → Releases**, along with merged changes awaiting a release.
