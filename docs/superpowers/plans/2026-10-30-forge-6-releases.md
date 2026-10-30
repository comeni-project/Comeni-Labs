# Forge MVP 6: releases — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a person cuts a registry release from the app, and the app follows releases.

**Architecture:** an `active_registry()` seam every reader goes through; a `ReleaseSource` reading
public GitHub data; `follow()`, a worker cron that fetches, loads and switches; `forge_release` for
cutting, through `RegistryPublisher`.

**Tech Stack:** Python 3.12, httpx, ARQ, SQLAlchemy + Alembic, React + TanStack Query.

**Spec:** `docs/superpowers/specs/2026-10-30-forge-6-releases-design.md`

**Execution:** native, inline. The whole suite once at the end, and `make verify` is the operator's
to run, since it needs Docker and Nextflow.

## Global Constraints

- A release is used only after it loads. One that fails is never switched to.
- Pinned never moves, offline keeps the newest it has, and with no release the configured root runs.
- A release is cut only on a green `main`, naming the commit whose checks were read.
- A pipeline's `release` is additive and omitted when unknown.
- No live GitHub in tests.

## Review Focus

1. GitHub unreachable during `follow`: the current release stays, and the reason is reported.
2. A release that fails to load: skipped, and `latest` falls back to the newest usable one.
3. A tarball with a `..` member, or the wrong commit: refused, and nothing is switched.
4. A pinned version that does not exist: nothing changes, and the setting says so.
5. Two people cutting at once: one release, enforced by the database.

---

### Task 1: The app follows releases

**Files:** Create `packages/mendel-forge/src/mendel_forge/releases.py`,
`services/github_releases.py`, `services/registry_releases.py`; Modify `settings.py`, every
`settings.registry_root` reader, `locate.py`, `lockfile.py`, `worker.py`, `catalogue.py` (settings),
`reports.py`, `docker-compose*.yml`.

**Interfaces:** Produces `active_registry() -> Path`, `Release(tag, commit, notes, published_at)`,
`ReleaseSource`, `Unreleased`, `follow() -> str | None`, `status() -> FollowStatus`,
`Locator.release`, `LockedLayer.release`, `registry.release`.

- [x] **Step 1: Write the failing tests** for focus 1–4, `latest` choosing the newest,
  `a pin never moves`, `no release runs the configured root`, `a release is read-only`,
  `the lockfile names the release`, and a guard that no reader but `active_registry` reads
  `settings.registry_root`.
- [x] **Step 2: Run; they fail.**
- [x] **Step 3: Implement.**
- [x] **Step 4: Run; pass.**
- [x] **Step 5: Commit.**

### Task 2: Cutting a release

**Files:** Create `services/forge_releases.py`, a migration; Modify `publishing.py`,
`github_publisher.py`, `routes/forge.py`, `worker.py`, `models.py`, `diagnostics.yml`.

**Interfaces:** Produces `ForgeRelease(id, version, state, says, commit, cut_by, cut_at)`,
`GET /forge/releases`, `POST /forge/releases`, `MF0519`, `cut_release(version, notes, commit)`.

- [x] **Step 1: Write the failing tests** `a version must be new and newer`, `nothing to release is
  refused`, `a red main is refused at the job`, `cutting names the commit it read`,
  `two cuts make one release` (focus 5), `no token says why`, `the page lists fragments and merged
  pull requests`.
- [x] **Step 2: Run; they fail.**
- [x] **Step 3: Implement.**
- [x] **Step 4: Run; pass.**
- [x] **Step 5: Commit.**

### Task 3: The Releases page

**Files:** Create `frontend/src/registry/Releases.tsx`, `useReleases.ts`; Modify `RegistryTabs.tsx`,
`router.tsx`, generated client.

- [x] **Step 1: Write the failing tests**: the tab links; what is unreleased; the suggested version
  and notes; a red main disables cutting and says why; a release in progress; no token.
- [x] **Step 2: Run; they fail.**
- [x] **Step 3: Implement.**
- [x] **Step 4: Run; pass.**
- [x] **Step 5: Commit.**

### Task 4: Docs and the whole suite

- [x] **Step 1:** How-to, `CHANGELOG.md`, `docs/notes/now.md`, a journal entry.
- [ ] **Step 2:** The whole Python suite, frontend, guards, doc checks.
- [ ] **Step 3:** Commit. Pushing `forge-6-releases` asks the operator first.

## Not in this plan

- The first real release, and pinning the `registry/` submodule to it (spec §7).

## Deviations

- `.run/registry` stays for now: until a first release exists it is the root a stack runs on. It
  goes once one does.
- `active_registry()` is a function beside `settings`, not a dynamic `registry_root`: tests and
  deployment set the field, and a guard holds every reader to the function.
- `registry.release` is a text setting, with *Release in use* reporting beside it: a choice's
  options are declared in the catalogue, and releases are data. A wrong version changes nothing.
- The Releases page reads public GitHub data from the API, cached for 60 seconds, so an installation
  with no token still sees it. `ReleaseSource` gained `unreleased`; `Unreleased.ahead` decides
  "nothing to release", because a first release has no fragments.
- `_load` in `services/registry.py` now keys on the root too: a release with the same bytes as the
  last would otherwise have kept the old paths.
- Tests in Tasks 1 and 2 were written with their code; the job's re-read of `main` was broken by
  hand and a test failed. The reader guard caught a real import, and the suite caught the cache bug.
