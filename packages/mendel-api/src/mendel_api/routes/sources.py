"""`/sources` — what can be read, and starting a draft from it.

**The one write here starts work rather than finishing it.** A draft is a workspace artifact,
outside every registry layer, so this is not the boundary `land` is. What it must be careful
about is a name that is taken, which `MF0010` refuses — before phase 6 that overwrote a
person's answers and said nothing.
"""


from fastapi import APIRouter
from mendel_forge.ops import DraftResult
from pydantic import BaseModel, ConfigDict

from mendel_api.refusals import REFUSES
from mendel_api.services import sources as service

router = APIRouter(prefix="/sources", tags=["sources"])


class DraftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """**Forbid, not ignore.** A request naming `workspace_root` must be a refusal rather than a
    silently discarded field — that is the difference between a boundary and a habit, and
    `test_no_request_body_accepts_a_filesystem_path` is the general form of it."""

    ref: str
    """A `ToolRef` as the source spells it — `nf-core:samtools/faidx`."""
    name: str
    """What to call the draft. Letters, digits, hyphens and underscores — it becomes a
    directory, which is `MF0008`."""
    version: str
    """**Asked for, never derived.** Two of the thirteen vendored tools have a container with no
    version in it at all, and one shipped contract disagrees with the tag it does have — spec
    §3.3 has the measurements. The form shows the container beside this field as evidence."""


# **`GET /sources` was deleted with `Sources.tsx`.** `GET /tools` supersedes it — one list for
# one object's life, spec §1.3 — and a route whose only caller is gone is a route that answers a
# question nobody asks. What stays is the POST, because drafting is still started from a row.
#
@router.post(
    "/draft", operation_id="draftTool", summary="Start a draft from a source", responses=REFUSES
)
def draft(body: DraftBody) -> DraftResult:
    return service.draft(ref=body.ref, name=body.name, version=body.version)
