---
title: Build a pipeline from another agent
description: Let Claude Code or any MCP client build pipelines through the same engine tools the builder's AI uses.
---

# Build a pipeline from another agent

The builder's AI works through a set of engine tools: read the pipeline, choose a tool, set a
value, build, compile, ask the person. Mendel serves the same tools over
[MCP](https://modelcontextprotocol.io), so another agent can build pipelines too. The engine
still checks every change, applies the registry's rules and writes the Nextflow. The agent
chooses; it never writes pipeline code.

## Turn it on

1. Generate a token: `openssl rand -hex 24`.
2. Put it in `.env` as `MENDEL_MCP_TOKEN`, then restart the API.

With no token, MCP is off. In production the API is public, so the production setup refuses to
start without one.

## Connect a client

The endpoint is `/api/mcp/` on the app's address, over streamable HTTP, with the token as a
bearer token. For Claude Code:

```bash
claude mcp add --transport http comeni http://127.0.0.1/api/mcp/ \
  --header "Authorization: Bearer $MENDEL_MCP_TOKEN"
```

## What a client can do

- **`open_draft`** creates a draft, or opens one by id. Every other tool takes its `draft_id`.
- The read, change and build tools are the builder's own. A change refused by the engine comes
  back as the tool's result, with its code.
- **Choices are recorded as the AI's**, with the client's name as who made them and the reason
  it gave, and they are marked for a person to review, as the builder's AI's are.
- **`ask`** returns the question to the client: its own user answers it.
- Data the tools return may include your samples' names, never a path or a file's contents.
