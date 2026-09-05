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
        ("/api/pipeline/compatibility", "get"): "compatibilityIndex",
        ("/api/pipeline/candidates", "get"): "listCandidates",
        # Every landed contract, for the builder's picker. Distinct from `listTools`, which
        # answers *what is the state of everything* and carries drafts and undrafted tools —
        # neither of which can be dragged onto a canvas.
        ("/api/pipeline/modules", "get"): "listModules",
        ("/api/pipeline/validate", "post"): "validatePipeline",
        ("/api/pipeline/compare", "post"): "comparePipeline",
        ("/api/pipeline/draw", "post"): "drawPipeline",
        ("/api/pipeline/drafts", "get"): "listDrafts",
        ("/api/pipeline/drafts", "post"): "createDraft",
        ("/api/pipeline/drafts/{draft_id}", "get"): "readDraft",
        ("/api/pipeline/drafts/{draft_id}", "put"): "saveDraft",
        ("/api/pipeline/drafts/{draft_id}/keep", "post"): "keepDraft",
        ("/api/pipeline/drafts/{draft_id}/artifact", "get"): "readArtifact",
        # **The only route that answers with bytes** — the courier's Mendel half, A179. It
        # serves a zip, so the generated client's return type is not a schema; `client.ts`
        # has a `blob()` for exactly this one and nothing else.
        ("/api/pipeline/drafts/{draft_id}/bundle", "get"): "downloadBundle",
        ("/api/pipeline/drafts/{draft_id}/gate", "post"): "startGate",
        ("/api/pipeline/gates/{run_id}", "get"): "readGate",
        ("/api/sources/draft", "post"): "draftTool",
        ("/api/attention", "get"): "whatNeedsYou",
        # **The forge surface, §7 of the Forge MVP plan.** Fourteen operations over twelve
        # paths, added in Task 8 *beside* `/tools` rather than replacing it — that migration
        # is Tasks 10 and 11's, and removing the old endpoints in the change that adds their
        # replacement would break the interface for as long as the rework takes.
        ("/api/forge/overview", "get"): "forgeOverview",
        ("/api/forge/catalogue", "get"): "forgeCatalogue",
        ("/api/forge/catalogue/{item_id}", "get"): "forgeCatalogueItem",
        ("/api/forge/sources/sync", "post"): "forgeSyncSources",
        ("/api/forge/adaptations", "get"): "forgeAdaptations",
        ("/api/forge/adaptations", "post"): "forgeStartAdaptation",
        ("/api/forge/adaptations/{adaptation_id}", "get"): "forgeAdaptation",
        (
            "/api/forge/adaptations/{adaptation_id}/revisions/{revision_id}",
            "get",
        ): "forgeRevision",
        ("/api/forge/adaptations/{adaptation_id}/retry", "post"): "forgeRetryAdaptation",
        ("/api/forge/adaptations/{adaptation_id}/messages", "get"): "forgeReviewConversation",
        ("/api/forge/adaptations/{adaptation_id}/messages", "post"): "forgeAskReview",
        ("/api/forge/adaptations/{adaptation_id}/changes", "post"): "forgeRequestChanges",
        ("/api/forge/adaptations/{adaptation_id}/approve", "post"): "forgeApproveAdaptation",
        ("/api/forge/adaptations/{adaptation_id}/archive", "post"): "forgeArchiveAdaptation",
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


KNOWN_COLLISIONS = [
    # **Two pairs that predate the guard, listed rather than exempted by a rule.** `Candidate`
    # is a reviewer's offered option in `comeni_core.review` and a routing candidate in
    # `services/candidates` — genuinely two things with one word. `Verdict` is a rule's
    # judgement and the forge's drift result. Both are load-bearing names in their own homes
    # and neither rename is obviously right, so they are carried and the list is what makes a
    # THIRD one fail.
    "comeni_core__review__question__Candidate",
    "comeni_core__review__verdict__Verdict",
    "mendel_api__services__candidates__Candidate",
    "mendel_forge__drift__Verdict",
]


def test_no_two_models_share_a_schema_name():
    """**A name collision silently renames the OTHER model, and only the frontend notices.**

    FastAPI disambiguates two classes sharing a name by qualifying *both* with their module
    path — so adding `forge_overview.Attention` beside `services/attention.Attention` renamed
    the existing one to `mendel_api__services__attention__Attention` in the served document,
    and `Home.tsx` stopped compiling on a screen nobody had touched.

    Nothing in this suite saw it: `make check` does not typecheck the frontend, and the schema
    is only a contract when both consumers are built. This is that gap closed on the Python
    side, where the collision is introduced.
    """
    schemas = _schema()["components"]["schemas"]
    assert sorted(name for name in schemas if "__" in name) == KNOWN_COLLISIONS, (
        "a schema name is module-qualified because two classes share a name. Rename one — the "
        "generated client refers to the qualified spelling, so the collision renames a type "
        "the frontend was already using, on a screen nobody touched."
    )
