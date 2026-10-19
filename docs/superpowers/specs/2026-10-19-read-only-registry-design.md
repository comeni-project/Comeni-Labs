# The app reads the registry; it never writes it — design

**Status: superseded (2026-10-19) by [the forge MVP design](2026-10-19-forge-mvp-design.md)** — the forge publishes to the registry by pull request, and the app reads it by release. Kept for its reasoning. Choices marked *(operator)* were made in chat on
2026-10-18/19; choices marked *(spec)* are this document's own.

## Why

Plan B made each saved `pipeline.yml` say where its registry layers can be fetched (#359). In the
web app that statement is always "nowhere": `make dev` serves the registry from a writable copy,
`.run/registry`, cloned from the local `registry/` folder, so its git remote is a path on the
developer's disk, and accepted forge changes are committed there on a local `comeni-local` branch
that exists nowhere else. Every web-built file therefore warns MD0231, which is true and useless.

The cause is one folder doing two jobs: the shared, published registry and a lab's private
workspace. **The MVP is for people building and running pipelines, not for curating the
registry** *(operator)*, so the second job goes: the app reads the shared registry exactly as
published and writes nothing into it. Adding a lab's own tools becomes a documented idea for
later, not a feature *(operator)*.

## What a person sees

- Every pipeline kept or previewed in the app names `source:
  https://github.com/comeni-project/comeni-registry` and the commit the `registry/` submodule pins.
  No MD0231/MD0232 on a normal stack.
- The forge still finds, drafts and reviews tools, and stops there: there is no *Approve and
  publish* and no *accept drift*. Nothing is exported: a maintainer takes a finished candidate
  to `comeni-registry` from its candidate page *(spec: the MVP's users do not curate the
  registry, so an export waits for the lab layer)*. Where those were, the page says that adding a tool to the
  registry is done outside the app, and links the guide.
- Changing the registry is a maintainer's job in git: land the change in a checkout of
  `comeni-registry`, open a pull request there, then move the submodule pin (as `CLAUDE.md`
  already says).

## Goals

- The app's registry is the pinned `registry/` submodule, mounted **read-only**.
- No code path reachable from the app writes registry files or commits to the registry.
- The locator works inside the containers, so files name the real source and commit.
- Documentation says how the registry changes, and describes the lab layer as a planned idea.

## Non-goals

- A lab layer, in the app or the CLI, or any variable for extra layers *(operator: none for the
  MVP)*. The CLI's existing `--registry` stacking stays as it is: it is how tests build overlays,
  and removing it is not asked for.
- Removing the forge's discovery, drafting, review chat, catalogue sync or the `mendel-forge` CLI.
  The CLI's own `land` stays for maintainers working in a registry checkout.
- Keeping `comeni-local` work: there are no users before v0.1.0, so nothing on it is migrated
  *(operator's rule, 2026-10-18)*.

## Anti-goals

- Hiding the warning. MD0231/MD0232 stay exactly as they are; they simply stop being true.
- A second copy of the registry anywhere in the stack.

## The design

1. **No writable copy.** `tools/dev_services.py` no longer clones `registry/` into
   `.run/registry`; `refresh_registry` and the `comeni-local` branch go. `make dev` checks that
   `registry/` is initialised (`git submodule update --init`) and says so if not.
2. **Mounted read-only, with its git metadata.** In `docker-compose.yml` (and the production file,
   if it mounts the registry) the Mendel services mount `./registry:/app/registry:ro` and
   `./.git/modules/registry:/app/.git/modules/registry:ro`, so `registry/.git`'s pointer
   (`gitdir: ../.git/modules/registry`) resolves inside the container and `git` reports the
   GitHub remote and the pinned commit *(spec)*.
3. **Locator reads without writing.** `mendel_compiler.locate` runs git with
   `--no-optional-locks`, so `git status` on a read-only mount does not try to refresh the index
   *(spec)*. If the container's user differs from the files' owner, git refuses ("dubious
   ownership"); the builder checks this and, if it bites, passes `-c safe.directory=<layer>` for
   that one call rather than changing global config *(spec)*.
4. **The app's two write paths go.** Forge approval (`POST /forge/adaptations/{id}/approve`, the
   publish job, `forge_jobs._land`) and drift acceptance (`drift.accept` and its route) are
   removed with their UI (*Approval*, the accept controls in *Drift*). *Decide* stays: it approves
   a vocabulary proposal into the forge's own workspace, never the registry, and without it a
   draft needing a new term could never complete *(builder check)*. *NothingFits* only changes
   wording if it promises the registry will change. The adaptation states, fields and diagnostics that exist only for
   approval and publishing go too, or are left for the builder to judge if other code reads
   them (see *Left to the builder*).
5. **Docs.** `docs/how-to/registry/add-tool.md` and `add-layer.md` say the registry changes by
   pull request to `comeni-registry`, then a pin move here. A short section in
   `docs/explanation/registry-layers.md` describes the lab layer as **planned, not built**: a
   lab's own git repository, stacked on the shared registry, named by a variable, usable in the
   app and the CLI, with its own remote so its files can say where it is fetched.

## Constraints

- `CLAUDE.md`: registry proposals require human approval; the app now performs none, which keeps
  this true trivially. Pure packages stay pure; the egress and purity guards stay green.
- `make dev` must still work on a fresh clone after `git submodule update --init`.
- A git worktree shares the main checkout's `.git/modules`; the stack is run from the main
  checkout, as today.

## Left to the builder

- Which forge models, columns, states and diagnostics are approval-only, and whether removing them
  needs a migration (shape versions apply to JSON columns; the dev database may be reset).
- The exact wording on the forge page where approval was.
- Whether the production compose file mounts the registry at all.

## Testing

- A guard that no app route or worker job calls `land` or `ops.accept`.
- `tools/dev_services.py`: `prepare` creates no `.run/registry`, and refuses clearly when
  `registry/` is not initialised.
- The locator on a read-only layer (a `chmod -R a-w` copy of a repository) reports commit and
  `dirty: false` without error.
- Live: `make dev`, keep a pipeline in the browser, and its `pipeline.yml` names the GitHub source
  and pinned commit with no MD0231 in the preview.
