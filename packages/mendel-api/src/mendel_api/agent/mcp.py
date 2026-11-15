"""The engine's tools over MCP (#463): the builder agent's tool layer, served to other agents.

The same definitions as the in-process agent, plus `open_draft`, which creates a draft or opens
one; every other tool names its draft. A client's writes are recorded as the model's, with the
client's name as who made them. **Behind a bearer token** (`MENDEL_MCP_TOKEN`) in every
environment: Mendel has no accounts, and in production the API is public. With no token set,
MCP is off.
"""

import inspect
import json
import secrets

from comeni_core.plan.draft import DraftGraph
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.responses import JSONResponse

from mendel_api.agent.tools import TOOLS, Tool, ToolContext, call
from mendel_api.services import decisions, drafts
from mendel_api.settings import settings

server = MCPServer(
    name="comeni-mendel",
    instructions=(
        "Build bioinformatics pipelines with Comeni's engine. Open a draft first with "
        "open_draft; every other tool takes its draft_id. Rules are advice: choosing otherwise "
        "is recorded as yours, with your reason. The engine routes and wires the steps; it "
        "never takes pipeline code."),
)


def _who(ctx: Context | None) -> str:
    try:
        name = ctx.session.client_params.clientInfo.name  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        # Outside a request (an in-process call) there is no client to name.
        name = None
    return f"mcp:{name or 'client'}"[:200]


def _served(tool: Tool):
    fields = tool.input.model_fields
    parameters = [inspect.Parameter("draft_id", inspect.Parameter.KEYWORD_ONLY, annotation=str)]
    parameters += [
        inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=field.annotation,
                          default=(inspect.Parameter.empty if field.is_required()
                                   else Field(default=field.get_default(call_default_factory=True),
                                              description=field.description)))
        for name, field in fields.items()]
    parameters.append(inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY,
                                        annotation=Context, default=None))

    def run(*, draft_id: str, ctx: Context | None = None, **arguments) -> dict:
        context = ToolContext(draft_id=draft_id, session_id=None, who=_who(ctx),
                              expected_revision=decisions.revision(draft_id))
        return call(context, tool.name, arguments).model_dump(mode="json", exclude_none=True)

    run.__signature__ = inspect.Signature(parameters, return_annotation=dict)
    run.__annotations__ = {p.name: p.annotation for p in parameters} | {"return": dict}
    run.__name__ = tool.name
    return run


def open_draft(name: str = "From another agent", draft_id: str | None = None,
               ctx: Context | None = None) -> dict:
    """Create a draft, or open the one `draft_id` names: every other tool takes its id."""
    if draft_id is None:
        draft_id = drafts.create(DraftGraph(), name[:120], _who(ctx))
    return {"draft_id": draft_id, "revision": decisions.revision(draft_id)}


server.add_tool(open_draft, name="open_draft",
                description="Create a draft to build a pipeline in, or open an existing one. "
                            "Every other tool takes the draft_id it returns.")
for _tool in TOOLS.values():
    server.add_tool(_served(_tool), name=_tool.name, description=_tool.description)


def draft_of(result) -> str:
    """The draft id in `open_draft`'s result, however the SDK wraps it."""
    if hasattr(result, "content"):
        result = result.content
    for part in result if isinstance(result, (list, tuple)) else [result]:
        if isinstance(part, dict) and "draft_id" in part:
            return part["draft_id"]
        if isinstance(part, (list, tuple)):
            found = next((draft_of(p) for p in part), None)
            if found:
                return found
        text = getattr(part, "text", None)
        if text and "draft_id" in text:
            return json.loads(text)["draft_id"]
    raise LookupError("open_draft returned no draft id")


def app():
    """The MCP endpoint behind the token: a refusal before any tool runs (Review Focus 5)."""
    # **The token is the guard**, so the SDK's DNS-rebinding check (a guard for unauthenticated
    # local servers) is off: a page rebinding a name to this server cannot present the token,
    # and the check refuses the hosts nginx and Vite forward from.
    inner = server.streamable_http_app(
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))

    async def guarded(scope, receive, send):
        if scope["type"] == "http":
            token = settings.mcp_token
            given = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
            if not token:
                await JSONResponse({"detail": "MCP is off: set MENDEL_MCP_TOKEN to serve it"},
                                   status_code=401)(scope, receive, send)
                return
            if not secrets.compare_digest(given, f"Bearer {token}"):
                await JSONResponse({"detail": "a valid bearer token is required"},
                                   status_code=401)(scope, receive, send)
                return
        await inner(scope, receive, send)

    return guarded
