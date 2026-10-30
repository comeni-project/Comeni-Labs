---
title: Walk the forge live
description: Take one tool from the catalogue to a registry release on a real stack, with a real model, Wiener and GitHub.
---

# Walk the forge live

The forge's tests use fake model, Wiener and GitHub clients, so this walk is the first time its
parts meet the real ones. Issue 412 tracks it. Record what breaks there, as you find it; do not
paper over a failure to reach the next step.

## Before you start

You need Docker with about 16 GB free for containers, the `registry/` submodule, and:

- **A model.** Use an API key or a local model, set under **Settings → Models → Adapting tools**.
  Walk with both if you can: the question is how far a local model gets compared with an API one.
- **A test repository.** Fork `comeni-project/comeni-registry`, with its Actions enabled. Do not
  walk against the real one: publishing writes to it.
- **A fine-grained GitHub token** for that fork only, with read and write on contents and pull
  requests, and read on checks.

In `.env`:

```bash
WIENER_API_TOKEN=<openssl rand -hex 24>
COMENI_FORGE_GITHUB_TOKEN=<the token>
MENDEL_REGISTRY_REPO=<your-account>/comeni-registry
```

`MENDEL_REGISTRY_REPO` points publishing and releases at the fork. Then start the stack with
`make dev`, and restart the workers after any code change: they do not reload.

## The walk

Do each step in the app, at both 1440 and 390 wide, and compare the pages with boards 4 to 6.

1. **Sync.** Choose **Sync now** in **Registry**. Check that `catalogue_sync.test_data_commit` is
   set: without it, assembly refuses a tool with tests.
2. **Follow.** In **Settings → Registry & sources**, *Release in use* should reach the fork's newest
   release within a minute of the worker starting. A fork has no releases until you publish one
   there, so cut `v0.5.0` on it first. Check that `.run/registries/v0.5.0/layer` is read-only.
3. **Forge `quast`.** Draft every piece with the AI, read what it proposes, and use the chat at
   least once. Note each thing you had to correct: that is the measure of the prompts.
4. **Assemble**, then **Run its tests**. Watch the run on **Runs**. This is the first real test run.
5. **Publish.** **Open pull request**, read its description, and wait for the fork's CI.
6. **Approve pull request**, then check that the catalogue says *Merged, not released*.
7. **Release.** Cut one from **Releases** on the fork, and check that the app moves to it within the
   hour, or restart the worker to look at once.
8. **Build.** Build a pipeline that uses `quast`, and check that its file names the release.

## What to watch for

These are the places the fakes could not check:

- **Samplesheets.** A tool with two sample-scoped inputs takes a table: `params_for` writes one row
  with a `sample` column, and Wiener turns it into a CSV.
- **The output check.** Green looks for each pattern under `<process in lowercase>/`, as Nextflow
  publishes it. A nested or differently named output will read as missing.
- **New types.** A type only this tool touches belongs in its `types/` folder, but publishing puts
  it under `vocabulary/types/`, so the local check may refuse it.
- **Test data.** The AI must turn nf-test's paths into paths under the `data/` root of
  `test-datasets`, and the pinned commit must hold them.
- **GitHub.** A fine-grained token needs each scope above. CI that never starts reads as pending.

## Afterwards

Close what the walk proves in issues 365, 366 and 367, and open a new issue for each defect. The ten
existing tools still need tests, written once a real run has shown what a good one looks like.
