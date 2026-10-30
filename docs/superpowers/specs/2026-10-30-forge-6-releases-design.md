# Forge MVP 6 — releases; the app follows registry releases (#367, #381)

Status: design, awaiting the operator's approval. Parent: #360. Builds on pull requests (#366).
Board 6 could not be read, so the page follows the issue and is compared with the board later.
`comeni-registry` has no GitHub release yet, and this needs a first one.

## 1. What this adds

- **A Releases tab** where a person sees what is merged and unreleased, and cuts a release: a
  version and notes, published as a tag and a GitHub release.
- **The app follows releases.** A *registry release* setting, `latest` (default) or a pinned version.
  Releases are fetched into read-only folders, replacing the writable `.run/registry`.
- **A pipeline names the release it was built with.**
- **Settings** gains that one setting. #381's overlay redraw is done; its spec left this to the forge.
  The token already shows as set or not, never typed.

## 2. Cutting a release

- **What is unreleased** comes from `comeni-registry`'s `main`: the `changelog.d/` fragments added
  since the last tag. Fragments are never deleted, so a release needs no commit of its own and
  nothing has to push to `main`. The page also lists merged forge pull requests with no release.
- **The form** suggests the next minor version and notes built from the fragments; both are editable.
- `RegistryPublisher` gains `unreleased() -> Unreleased`, `releases() -> list[Release]` and
  `cut_release(version, notes, commit) -> Release`, in the worker, which alone holds the token.
- **Refused:** a version that exists or is not newer than the last, an empty release, and a `main`
  whose latest commit has CI that is not green. Tagging names the commit whose checks were read.
- A forge pull request stays *merged, not released* until the app loads a release holding it.
- Cutting a release is a person's click and is hard to undo: the form states the tag and commit
  first. **`forge_release`** records who cut what.

## 3. The app follows releases

- **A cron in `mendel-worker`, hourly**, reads the repository's releases. Public reads need no token.
- A release is fetched into `.run/registries/<tag>/layer`, with `release.yml` beside it (repository,
  tag, commit, digest) and then made read-only. The tarball's commit is checked against the tag.
- **A fetched release must load before it is used:** `layers.load` runs on it, and one that fails
  stays unused, with the reason shown in Settings. The registry's format floor (`MD0020`) makes this
  the normal way an old app meets a release it cannot read.
- **`.run/registries/current`** names the active tag, replaced atomically. `settings.registry_root`
  resolves through it, so every reader follows and `registry.stack()`'s digest key invalidates
  itself. Without one, it is the configured root, as today: the submodule in development and tests.
- `latest` moves to the newest usable release. **Pinned never fetches**, apart from fetching the
  pinned version when it is absent. **Offline keeps the newest it has.**
- A running job keeps the stack it loaded, and a kept pipeline is unaffected: it pins its layers.

`make dev` and production stop preparing `.run/registry`. Each Mendel service mounts
`.run/registries` read-only, and the worker alone read-write.

## 4. A pipeline names its release

`LockedLayer` gains an optional `release`, read from `release.yml`, with `source` and `commit` filled
from it, since a fetched folder has no git metadata. That also ends `MD0231` for released layers.
**Additive and omitted when unknown,** so existing pipelines keep their digests. The pipeline page
shows it, and `registry_label()` returns the tag.

## 5. The setting

`registry.release` in *Registry & sources*: text, `latest` or a version, validated against the
fetched and listed releases, and offered as a choice on the page. It says what is in use now, when
it was last checked, and any release that failed to load. `MENDEL_REGISTRY_RELEASE` in `.env` wins,
like every other setting.

## 6. What forging is based on

**Forging stays on the release in use**, not `main` as design answer 1 said, because the app no
longer holds a writable checkout. A chain of tools still works without a release between each:
assembled and merged drafts are already visible as pending layers, and publishing's checks run on a
fresh `main`, so a stale base fails there and says why. `base` on an adaptation records the release.

## 7. Prerequisites and order

1. The `comeni-registry` pull request (`test` in `layout:`, `changelog.d/`, `ENGINE_REF`).
2. Comeni-Labs' forge branches on `main`, then `ENGINE_REF` moved to that commit.
3. The first release of `comeni-registry`, then the `registry/` submodule pinned to its tag
   (design answer 4). **Until that first release, an installation runs its configured root.**

## 8. Not in this MVP

- Polish of the page: a release can be cut from it, plainly (the design's first cut after pipelines).
- Deleting old fetched releases.
- A real release: built against a fake publisher, walked against a test repository with #412.

## 9. Costs and risks

- `settings.registry_root` becoming dynamic touches every reader. A reader that cached the path
  would keep the old release; the plan audits each.
- Dropping the writable `.run/registry` changes how `make dev` runs. Anyone editing registry data
  against the stack should use a layer or a checkout through `MENDEL_REGISTRY_ROOT`.
- `latest` means a release can change what an installation builds, without anyone there acting.
  Replays and kept pipelines are safe, and a pinned installation never moves, so a lab that must not
  drift should pin.
- A pipeline schema change needs `make verify`, which needs Docker and Nextflow.
