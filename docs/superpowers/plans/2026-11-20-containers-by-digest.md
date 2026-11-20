# Plan: containers pinned by digest

Spec: `docs/superpowers/specs/2026-11-20-containers-by-digest.md`. Branch: `feat/containers-by-digest`
from `main` here; `pin-containers` output lands on a branch in `../comeni-registry`.

- [x] **1. Probe.** By hand: resolve one Wave and one quay.io tag to a digest with an anonymous
      `HEAD /v2/.../manifests/<tag>`, and run a one-process pipeline whose config sets
      `container = '<name>:<tag>@sha256:<digest>'` over a module naming the tag. Confirm the task
      ran the digest (`.command.run`, `docker inspect`). If either fails, stop and bring options.
- [x] **2. Reference parsing, test first** (`comeni_core`): split a `ContainerRef` into name, tag
      and digest; render `name:tag@sha256:`; the image without its digest.
- [x] **3. Resolver, test first** (`comeni-vendor`): `digest_of_image` over a recorded token
      challenge and manifest response; a clear error when the registry refuses.
- [x] **4. `pin-containers` command, test first**: rewrites only the `container:` line of each
      contract in a registry copy; idempotent on a pinned one.
- [x] **5. Conformance, test first**: a pinned contract agrees with its module's tag; an unpinned
      one warns (a new diagnostic in `diagnostics.yml`, `refuses: false`).
- [x] **6. Emitter, test first**: the per-process `container =` override for a pinned contract,
      none for an unpinned one; goldens regenerated.
- [x] **7. Pin the registry.** Run `pin-containers` on a `comeni-registry` worktree, read the diff,
      commit; point the submodule at it.
- [x] **8. Docs and changelog**: contract schema (`container`), conformance diagnostics,
      `comeni-vendor` usage; CHANGELOG entries.
- [x] **9. `make check`, `make guards`, `make verify`**; ledger evidence; PRs here and in the
      registry; tick #600.

## Ledger
- Step 1 (2026-11-20, Nextflow 25.10.4, Docker): quay.io answers `HEAD /v2/<repo>/manifests/<tag>` anonymously; Wave answers 401 with `Bearer realm="https://cerbero.seqera.io/auth/token",service=…,scope=repository:<repo>:pull`, and the anonymous token from that realm works. Both return `Docker-Content-Digest`. A config `withName: P { container = 'name:tag@sha256:…' }` over a module naming the tag ran `docker run` on the digest reference; a digest one character off failed (`failed to resolve reference … not found`), so the tag is never a fallback.
- Step 9: `make verify` passed (4115, 51 slow, 84 guards), with `LITELLM_MODE=PRODUCTION` as this branch predates #604. The first run failed the purity guard: `comeni_core.spell.images` imported `re`, which is off comeni-core's allowlist; rewritten with a spelled-out check, as `marks.py` does.
- Step 7: `pin-containers` pinned all 13 contracts; every changed line is a `container:` line and every tag is kept. Contract digests in `test_digest.py` repinned (content change).
