"""A mountable ASGI app over the same request and result models the CLI uses.

**Every route is three lines**: take the request model, call the one `ops` function,
return the result model. FastAPI validates the body against the same pydantic class
argparse fills, so the two transports cannot drift in what they accept either.

**No route may contain an `if`.** A branch in a transport is logic the other transport
does not have, and the moment one exists `forge draft --json` and `POST /drafts` stop
being the same payload. `tests/test_http.py` compares them directly rather than trusting
this paragraph.

**It binds nothing and has no auth.** Phase 1 ships an `app` object; Plan 3's
`mendel-api` mounts it and owns the questions this file deliberately does not answer —
who is calling, over what, and whether they may.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from mendel_forge import ops
from mendel_forge.land import LandResult

app = FastAPI(title="mendel-forge", version="0.1.0")


@app.exception_handler(ValueError)
async def _refusal(request: Request, exc: ValueError) -> JSONResponse:
    """One place turns a refusal into a status code, exactly as `cli.main` does.

    422 rather than 400: the body parsed and the values were wrong for it, which is what
    FastAPI already means by 422 for its own validation. A coded refusal is the same kind
    of answer, so it gets the same code and the message carries the `MF`/`MD` code for a
    client to read.
    """
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/sources")
def sources() -> ops.SourcesResult:
    return ops.sources_()


@app.post("/discover")
def discover(req: ops.DiscoverRequest) -> ops.DiscoverResult:
    return ops.discover(req)


@app.post("/drafts")
def create_draft(req: ops.DraftRequest) -> ops.DraftResult:
    return ops.draft(req)


@app.post("/drafts/list")
def list_drafts(req: ops.ListRequest) -> ops.ListResult:
    return ops.list_(req)


@app.post("/drafts/show")
def show_draft(req: ops.ShowRequest) -> ops.ShowResult:
    return ops.show(req)


@app.post("/drafts/fill")
def fill_draft(req: ops.FillRequest) -> ops.FillResult:
    return ops.fill(req)


@app.post("/drafts/verify")
def verify_draft(req: ops.VerifyRequest) -> ops.VerifyResult:
    return ops.verify_(req)


@app.post("/drafts/land")
def land_draft(req: ops.LandRequest) -> LandResult:
    return ops.land(req)


@app.post("/check")
def check(req: ops.CheckRequest) -> ops.CheckResult:
    return ops.check(req)


@app.post("/update")
def update(req: ops.UpdateRequest) -> ops.DraftResult:
    return ops.update(req)


__all__ = ["app"]
