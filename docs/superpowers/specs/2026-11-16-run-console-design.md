# Run console: Nextflow's terminal, a shell, and the assistant

Part of the frontend redesign (#511). Board: `2026-11-16-run-console-board/` (approved 2026-11-16,
"good for mvp"). Security trade-off: #525.

## Intent

Run → Console is where a person sees exactly what Nextflow printed and works on the run directly:
reads a failed task's error, reruns one task, resumes. Comeni is a local tool for now, so the
console is a real shell; a hosted platform revisits that (#525).

## What it is

- **Nextflow pane**: Nextflow's own terminal output, live, with its colours and progress lines,
  replayed from the run's `console.log` once the run is over. Copy and Download.
- **Shell pane**: a bash in the run's folder, with what the run had: `nextflow`, `docker`, the
  data roots read-only, the run's `work/` and results. A *full access to this machine* label.
  **New shell**. A draggable divider between the panes.
- **Commands**: a searchable list (like Add step), grouped *This run*, *A step's task*, *From this
  pipeline's tools*, *Disk and machine*. Each has a plain name, what it does and the exact command,
  with Insert or Run. Commands are declared data, so the list grows with the registry: general
  ones ship with Comeni, a tool's own ones beside its contract and shown only when that tool is in
  the pipeline.
- **Assistant** (a panel, opened from the header): sees the Nextflow pane and the shell's output.
  It may run **read-only commands** itself (an allowlist: `cat`, `head`, `tail`, `grep`, `ls`,
  `wc`, `du`, `df`, `free`, `nextflow log`), each marked AI in the shell and listed under *How I
  got here*. Anything else comes as a **Suggested command** card the person runs (Run in the shell,
  Insert). Its answers name the evidence they rest on.
- **A failed run** opens with a banner naming the failed step and sample, with *Open its folder in
  the shell* and *Resume the run*. Steps' **Log** opens the shell in that task's folder.
- **Phone**: Nextflow and Shell are tabs; a key row adds Tab, Ctrl, Esc, ↑, ↓ and Ctrl-C.
- The terminals follow the app's theme (light and dark tokens); colour marks meaning only.

## How it is built

- **Worker**: Nextflow is started under a pseudo-terminal; everything it prints is written to the
  run's `console.log`. Launching, tracking and cancelling are otherwise unchanged.
- **`wiener-term`**: a new service from the Wiener image with the worker's mounts. One WebSocket per
  run under `/api/runs/{id}/terminal`, through nginx, behind the Wiener token: it streams
  `console.log` and runs shell sessions (pty) in the run's folder.
- **Browser**: xterm.js for both panes, themed from the tokens.
- **Assistant**: an agent point with two tools, *read the console* and *run a read-only command*
  (checked against the allowlist on the server), plus *suggest a command* (shown, never run). Model
  calls go through the declared AI points and typed payloads, as Build's agent does.

## Not in this MVP

Commands declared by tools in the registry beyond a first handful; a resume form (Resume runs
`-resume` with the same params); per-user shells.
