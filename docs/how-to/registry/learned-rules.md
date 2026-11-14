---
title: Learn rules from your answers
description: Turn a question people keep answering the same way into a rule, proposed by a model, checked by the engine, approved by you.
---

# Learn rules from your answers

When the rules cannot settle a choice, Mendel asks a person. If people in your lab keep giving
the same answer on the same facts, that answer is a rule nobody wrote down. **Registry → Learned
rules** turns it into one. A model proposes the rule, the engine checks it, and you decide.
**Nothing is used until you approve it.**

## Propose

1. Keep the pipelines whose questions you answered. Only kept pipelines are read.
2. Open **Registry → Learned rules** and choose **Propose**.

Mendel looks at every question a person answered in a kept pipeline, where there were two or more
options to choose from. A question answered in **three** kept pipelines is sent to the model. The
model sees the facts each pipeline was built on (an organism, a read length), the answer, and any
reason you typed with it. It never sees sample names, file names or your data.

The model uses the forge's model setting, **Settings → Models → Adapting tools**. With no model
set, the page says so and **Propose** is disabled.

## Read a proposal

Each proposal shows:

- **the rule**, as *When paired is yes and read length is not known → HISAT2*, with the model's
  reason marked as the model's;
- **where it was learned from**: each kept pipeline, the answer and your reason;
- **the engine's check**: *Checks pass*, or what the registry refuses, with its code;
- **what it would change**: past decisions it would have answered differently come first, then
  how many it would have answered the same way.

The engine refuses a rule that contradicts any of your answers, or that reaches none of them. The
model gets one more try with the problem; if that fails too, the question is listed under **Not
proposed** with why. A new rule's rows go after the rows already in the registry, so they only
answer where those rows could not.

## Approve, reject, withdraw

- **Approve** writes the rule to your installation's own registry layer, in
  `<workspace>/layer/rules/learned/`. It is stacked above the release, so the next build answers
  that question by the rule, at tier 3 where the rule tests a fact. Its citation names the kept
  pipelines it was learned from, and the file's opening comment says who approved it and which
  model call proposed it. A proposal cannot be approved after people have answered the question
  again; choose **Propose** to ask about the new answers.
- **Reject** sets it aside. The question is not proposed again until people answer it again.
- **Withdraw**, under **In use**, removes the file. The question is asked again in the next build.

The file holds the whole table for that question: the release's rows first, then the learned
ones. **In use** marks each row as learned or from the release. The file replaces the release's
table, so a later release that changes those rows stays hidden behind it. After you update the
release, withdraw the rule if the release's new rows should apply. It is proposed again once
people answer the question again.

The layer is an ordinary registry layer: review, edit or version it like
[your lab's own layer](add-layer.md). Set `MENDEL_OWN_LAYER` to put it somewhere else.
