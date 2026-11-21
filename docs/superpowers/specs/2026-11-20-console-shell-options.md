# The Console shell: options before hosted use

Issue: #525. Tracked in #600. An exploration for the operator to choose from; nothing here is
implemented. Design of the Console: `docs/superpowers/specs/2026-11-16-run-console-design.md`.

## What exists (read from the code on 2026-11-20)

- `wiener_api/terminal.py` serves Run → Console: the run's Nextflow output, read-only commands
  (`read_only`, an allowlist, 15 s and 2 MB caps), and **a real interactive `bash`** in the run's
  folder over a WebSocket (`pty.fork`, `bash --norc -i`).
- Both are behind the one Wiener bearer token (`_allowed`) and a same-origin check on the upgrade
  (`_same_page`). With no token set, Wiener is open, which is the laptop default.
- The service (`wiener-term` in `docker-compose.yml`) mounts the host Docker socket, the run
  directory and the data roots (read-only), and joins the socket's group. So the shell can run
  `docker run -v /:/host …`: **holding the Wiener token is host-level control.**
- `docker-compose.prod.yml` has **no `wiener-term` service**, while `ops/nginx/default.conf.template`
  proxies `/api/runs/<id>/terminal/` to it. In production the Console's shell and read-only
  commands therefore fail at the proxy today, a working pair of files that disagree.

## Why the socket is there

The shell is for looking at a run and resuming it. Resuming (`nextflow -resume`) starts task
containers, which needs Docker. Looking does not.

## Options

| | What a person can do | Removes host control? | Cost |
|---|---|---|---|
| **A. No shell** | Nextflow output, the read-only allowlist, and run verbs (resume, cancel) as buttons that Wiener performs | Yes | Smallest: delete the PTY route and the socket mount from `wiener-term`; resume becomes a Wiener verb run by the worker, which holds the socket already (today the Console only *suggests* the resume command, `resume_command`, for the person to run). Loses free-form looking |
| **B. Shell without the socket** | Free-form looking in the run folder; resume as a button (as A) | Yes, for the shell | Small: a second service (or the same one) without `docker.sock` and without the Docker group; the shell's user can read the run folder only. Resume moves as in A |
| **C. Shell in a per-run container** | A shell in a throwaway container with only that run's folder mounted | Yes | Medium: Wiener starts and reaps one container per session (it has the socket), proxies the PTY into it; images, limits and cleanup to own |
| **D. Per-user sandboxing** | As C, scoped to who is signed in | Yes | Large: needs per-person identity first (#83), then C per user |
| **E. Keep as is, documented** | Everything | No | None now; acceptable only while one person runs it on their own machine (the operator's 2026-11-16 decision) |

Independent of the choice: **make production agree with itself.** Either add `wiener-term` to
`docker-compose.prod.yml` with the chosen boundary, or remove the nginx location so the Console
says the shell is unavailable rather than failing at the proxy (#609).

## Recommendation

**B now, D only if Comeni becomes a shared platform.** B keeps what the shell is for (looking
at a run) and removes host control at the cost of moving resume behind a button, which the
board already draws as a verb. It needs no identity work. A is the fallback if a free shell
is not worth a second service. C buys little over B for one laboratory and costs container
lifecycle code.
