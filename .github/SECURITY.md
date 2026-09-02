# Security policy

## Reporting

Report privately through
[GitHub Security Advisories](https://github.com/comeni-project/Comeni-Labs/security/advisories/new).
Please do not open a public issue first.

Expect an acknowledgement within a week. If a report is valid we will agree a disclosure
timeline with you and credit you in the advisory unless you would rather we did not.

## What counts

This project's central claim is that laboratory data does not reach it and does not leave
through undeclared paths. Anything that undermines that is a security issue, not a bug
report:

**A way to get patient data into a `Goal`.** A filename, a path, a sample identifier, or
free text of any kind reaching a model or a persisted artifact. `Goal` is supposed to hold
a shape and nothing else.

**A way past the egress boundary.** Four doors are declared in
`packages/comeni-core/src/comeni_core/egress.py` and enforced by `tests/test_egress.py`.
A fifth path, a payload field that carries more than it declares, or a way to smuggle free
text through a typed field all qualify.

**A network call from a pure package.** `comeni-core`, `mendel-resolver` and
`mendel-compiler` are under a closed import allowlist. Reaching the network from any of
them — including through the standard library or a dynamic import — defeats the structural
guarantee that telemetry cannot live there.

**Code execution through generated Nextflow.** Parameter values are rendered into Groovy.
A value that closes a quote and executes is a critical issue; the escaping lives in
`mendel_compiler.emit._render_literal`.

**Registry poisoning.** A contract, rule or vocabulary file that causes a materially
different pipeline without a `SHADOW` record or a review flag. An installed overlay must
never reroute a pipeline silently.

### A test is the best report

The most useful report is a failing test. All three guards in this repository have holes in
their history, and every one was found by someone writing four lines that should not have
passed:

```python
import urllib.request, socket, http.client
importlib.import_module("httpx").post(...)
__import__("openai").OpenAI()
```

That defeated the purity guard entirely. A later attempt on the egress guard found that a
bare `user_note: str` passed every rule it had.

## What does not count

- Vulnerabilities in vendored `nf-core` modules, which live in the registry layer under `tools/<org>/<tool>/module/` — report those to
  [nf-core](https://github.com/nf-core/modules).
- Vulnerabilities in Nextflow, Docker, or container images.
- A pipeline producing scientifically wrong results. Real and important, but it is a bug —
  and Mendel makes no claim that a pipeline is correct, only that every choice is recorded.
- Missing hardening in `mendel-api`, `mendel-ai` or `mendel-forge`. They do not exist yet.

## Scope and versions

Only `main` is supported. There are no releases to backport to.

## What this software is not

Mendel constructs and documents analysis pipelines. **It is not a diagnostic device and
produces no diagnostic result.** Pipelines it emits must be validated by the laboratory
before clinical use.

We claim no compliance with IVDR, CLIA, CAP or ISO 15189. Those attach to a laboratory's
processes and no software can hold them on your behalf. What leaves the platform on the
build path, and when, is covered on its own page — not yet written.
