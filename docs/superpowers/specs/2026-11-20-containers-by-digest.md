# Containers pinned by digest

Issue: #308 (second half; the Nextflow minimum is PR #606). Tracked in #600.

## The defect

A run uses the image the vendored module names in its own `main.nf`, by tag:
`community.wave.seqera.io/library/htslib_samtools:1.24--d697cfb9dce007cd`. A tag can be repointed,
so the same `pipeline.yml` can run different software. `@sha256:…` cannot.

The contract's `container:` (`ContainerRef`) does not reach the run. It is recorded in
`pipeline.yml` (`comeni_core/artifact/lockfile.py`) and conformance requires it to equal the
module's (`mendel_compiler/conformance.py`, the `contract.container != spec.container` check).
The vendored `main.nf` cannot carry the digest either: editing it breaks the module's digest.

## What changes

1. **Resolving a tag** (`comeni-vendor`, which already does network I/O; pure packages stay
   pure): `digest_of_image(ref) -> str`, an anonymous OCI distribution `HEAD
   /v2/<repo>/manifests/<tag>` with the index and manifest `Accept` types, reading
   `Docker-Content-Digest`, answering the bearer-token challenge quay.io and Wave send. A
   multi-architecture image pins its index digest, so every architecture is kept.
2. **The contract records the digest**: `container: <name>:<tag>@sha256:<digest>`. Conformance
   compares the contract's image *without* the digest to the module's, so a pinned contract still
   agrees with its module.
3. **The emitter applies it**: for each step whose contract container carries a digest,
   `withName: <PROCESS> { container = '<name>:<tag>@sha256:<digest>' }`. Config beats the module's
   `container` statement in Nextflow, so the run pulls by digest. Docker and Nextflow accept the
   `name:tag@sha256:` form. Under Singularity/Apptainer the same reference is pulled as
   `docker://…@sha256`, in place of the module's Singularity URL, which is already
   content-addressed.
4. **Pinning**: `comeni-vendor pin-containers --registry <dir>` resolves every contract's image
   and rewrites its `container:` line, nothing else, in a writable registry checkout. It runs
   once on `comeni-registry`, reviewed as one PR there; new tools are pinned the same way when
   they are added. The forge drafts a contract's container from the module (`mendel_forge`);
   pinning a forged contract is a follow-up once this lands.
5. **A warning, not a refusal** (operator, 2026-11-20): conformance reports a contract whose
   container has no digest as *unpinned*, like an absent module source is *unverified*
   (`MD0100`, `refuses: false`). Making it an error is one line, once the registry is pinned.

## Out of scope

- Wiener resolving or rewriting containers at launch: it runs what the artifact names.
- The forge pinning what it drafts (follow-up, above).

## Verification

- Unit: parsing a reference and rendering `name:tag@sha256:`; the token challenge and digest
  header against recorded responses (no live registry in tests); the emitter's override and its
  absence for an unpinned contract; conformance agreeing with a pinned contract and warning on an
  unpinned one.
- One live `pin-containers` on a registry copy, its diff read by a person.
- `make verify` against the pinned registry: every slow gate pulls by digest.
