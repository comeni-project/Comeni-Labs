# Why Comeni does not use MCP (2026-10-17)

**For the thesis.** A note on why model access goes through `comeni-ai` with structured output
and not through the Model Context Protocol, and on when that should change. True on this date.

## What MCP is

MCP is a protocol for delivering tool definitions and tool calls between **separate programs**:
an AI application (Claude Desktop, Claude Code, Cursor) on one side, a server exposing tools or
data on the other. It does not change what the model sees. A host converts an MCP server's tools
into ordinary tool definitions (name, description, JSON schema) — the same `tools=` a direct API
call takes. MCP is the plug between two independently written sides, not a capability.

## What Comeni does instead

**The engine asks; the model answers in a declared shape.** Every call is
`generate(instruction, shape, evidence)` in `comeni-ai`: the reply is validated against a
Pydantic shape before any caller sees it, enforced server-side through
`response_format: json_schema, strict: true` where the provider is verified, written into the
prompt otherwise (`formats.py`). A reply that fails becomes a coded refusal (`MA0004`, …), never
a write. The engine — not the model — applies the result to records and files.

MCP assumes the opposite arrangement: the model decides which tools to call and when. Inside
Comeni that would invert the position that the resolver decides and the model fills only the
choices rules cannot settle, with each contribution recorded.

## Why not MCP for our own tools

When the tool and the AI application are both ours, MCP adds a server process, a JSON-RPC
transport, authentication, latency and a failure point, and gains nothing: the engine is the only
client and can call the function directly.

| Tool | AI application | MCP? |
|---|---|---|
| Ours | Ours | **No.** Call it directly. |
| Ours | Someone else's (Claude, Cursor) | **Yes.** It is the only way in. |
| Someone else's (GitHub, Sentry) | Ours | **Maybe.** Reuse an existing server instead of writing an integration. |
| Ours | Ours and others' | **Yes.** Written once, used everywhere. |

## Memory and agent-to-agent communication

Neither needs MCP while it stays inside the engine.

- **Memory** is a table plus retrieval: the engine selects relevant entries and passes them as
  `evidence`, so what each agent was shown is recorded and a bad memory can be traced and
  removed. If an agent should choose what to look up, that is tool calling run by the engine.
- **Agents talk through the engine**, not to each other: A's validated output becomes B's
  evidence. Every handoff is recorded, and no agent pushes unvalidated output into another
  (orchestration).
- Agents in *separate systems owned by different parties* talking to each other is what A2A
  (Agent2Agent) addresses — MCP is AI ↔ tools, A2A is AI ↔ AI across systems.

## When to revisit

- **Outside users driving Comeni from their own assistant.** A thin MCP server over the CLI —
  `search_registry`, `explain`, `validate_contract`, `build` — with Mendel still deciding.
- **Contributors drafting registry contracts with an assistant** that runs conformance itself.
- **A tool that becomes a separate service**, where some protocol is needed anyway.
- **Users plugging their own MCP servers into Comeni.**

Each is a layer over the existing functions; none requires changing `comeni-ai` now.
