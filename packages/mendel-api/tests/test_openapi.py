"""The schema is the contract, so it gets a guard.

`frontend/src/api/schema.d.ts` is generated from this document and an agent driving Mendel
reads the same document — two consumers, one artifact. Everything asserted here is something
that is *invisible* until a client is generated and wrong: FastAPI happily emits
`answer_questions_answer_post` as an operation id, and happily documents a 422 in a shape the
route never returns.
"""

from mendel_api.main import create_app


def _schema() -> dict:
    return create_app().openapi()


def _operations(schema: dict):
    for path, methods in schema["paths"].items():
        for method, op in methods.items():
            yield path, method, op


def test_every_operation_is_named_by_hand():
    """FastAPI's default id is `{function}_{path}_{method}` — `listQuestions` becomes
    `queue_questions_get`, which is what a generated client method would be called. The
    literal list is the point: adding a route means editing this test."""
    got = {(p, m): op.get("operationId") for p, m, op in _operations(_schema())}
    assert got == {
        ("/api/questions", "get"): "listQuestions",
        ("/api/questions/answer", "post"): "answerQuestion",
        ("/api/visits", "post"): "markVisited",
        ("/api/registry/types/{id}", "get"): "lookupType",
        # The tier vocabulary, served rather than retyped into an interface.
        ("/api/registry/tiers", "get"): "listTiers",
        # FastAPI strips the `:path` converter when generating OpenAPI, so this reads
        # `{id}` even though the route is declared `{id:path}` — a contract id has slashes.
        ("/api/contracts/{id}", "get"): "readContract",
        # Registered BEFORE the greedy `/{id:path}` above, or they never match — and the
        # failure is a 200 carrying the module page rather than a 404.
        ("/api/contracts/{id}/drift", "get"): "readDrift",
        ("/api/contracts/{id}/drift/accept", "post"): "acceptDrift",
        ("/api/questions/answer-all", "post"): "answerAll",
        ("/api/questions/propose", "post"): "proposeType",
        ("/api/questions/proposals/decide", "post"): "decideProposal",
        # **`listTools` replaced `listSources` and `listContracts`**, and both were deleted in
        # the same commit as the screens that called them — this list is where that was checked.
        # `POST /sources/draft` survives because drafting is still started from a row.
        ("/api/tools", "get"): "listTools",
        # **The build path, reachable at last.** `resolve_verbs.run` was argparse-shaped until
        # Plan 3C phase 0, so no route could exist here at all. `POST` because a `Goal` is a
        # document — profile, wants, producer pins — and a URL is the wrong place for one.
        ("/api/pipeline", "post"): "buildPipeline",
        ("/api/pipeline/example", "get"): "examplePipeline",
        # Every landed contract, for the builder's picker. Distinct from `listTools`, which
        # answers *what is the state of everything* and carries drafts and undrafted tools —
        # neither of which can be dragged onto a canvas.
        ("/api/pipeline/modules", "get"): "listModules",
        ("/api/sources/draft", "post"): "draftTool",
        ("/api/attention", "get"): "whatNeedsYou",
        ("/api/health", "get"): "liveness",
        ("/api/health/registry", "get"): "registryHealth",
    }


def test_every_operation_carries_a_tag():
    """An untagged operation lands in a `default` bucket, which is where operations go to
    become undiscoverable once there are thirty of them."""
    untagged = [f"{m.upper()} {p}" for p, m, op in _operations(_schema()) if not op.get("tags")]
    assert untagged == []


def test_every_operation_says_what_it_does():
    missing = [f"{m.upper()} {p}" for p, m, op in _operations(_schema()) if not op.get("summary")]
    assert missing == []


def test_the_coded_refusal_is_in_the_schema():
    """The gap this closes: the forge answers a coded refusal correctly and says
    nothing about it in its document, so a generated client types `detail` as the validation
    array and the UI renders nothing for the one message a curator must read."""
    schema = _schema()
    assert "Refusal" in schema["components"]["schemas"]

    answer = schema["paths"]["/api/questions/answer"]["post"]
    got = answer["responses"]["422"]["content"]["application/json"]["schema"]
    assert got["$ref"].endswith("/Refusal")


def test_the_refusal_schema_is_a_bare_ref():
    """A `$ref` with sibling keywords is legal JSON Schema and renders wrongly in every
    generator worth using — `openapi-typescript` produces an intersection nobody meant. This
    caught exactly that: declaring `model` *and* a hand-rolled `anyOf` merged into both."""
    schema = create_app().openapi()
    got = schema["paths"]["/api/questions/answer"]["post"]["responses"]["422"]
    assert list(got["content"]["application/json"]["schema"]) == ["$ref"]


def test_the_answer_response_is_typed():
    """A route returning an untyped dict generates `unknown` on the client, and every use of
    it then needs a cast — which is how a generated client stops being worth generating."""
    ok = create_app().openapi()["paths"]["/api/questions/answer"]["post"]["responses"]["200"]
    ref = ok["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/Answered")
