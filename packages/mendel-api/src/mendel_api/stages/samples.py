"""②a Inside: reading a sample. The section runs inside its request (or the reading's job);
`upload` is the one step the interpreter sees, and its outcome is the section's way out."""

from mendel_api.services.session import Ctx, handles


@handles("upload")
def upload(ctx: Ctx) -> str:
    return "answered" if ctx.payload["answered"] else "stays"
