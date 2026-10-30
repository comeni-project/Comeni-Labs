"""The schema is the contract, so it gets a guard.

`frontend/src/api/schema.d.ts` is generated from this document and an agent driving Mendel
reads the same document — two consumers, one artifact. Everything asserted here is something
that is *invisible* until a client is generated and wrong: FastAPI happily emits
`{function}_{path}_{method}` as an operation id, and happily documents a 422 in a shape the
route never returns.
"""

from mendel_api.main import create_app


def _schema() -> dict:
    return create_app().openapi()


REFUSING = ("/api/pipeline/authoring/{session_id}/facts/{subject}/history", "get")
"""A route that answers a coded refusal, to check how the document describes one."""


def _operations(schema: dict):
    for path, methods in schema["paths"].items():
        for method, op in methods.items():
            yield path, method, op


def test_every_operation_is_named_by_hand():
    """FastAPI's default id is `{function}_{path}_{method}`, which is what a generated client
    method would be called. The
    literal list is the point: adding a route means editing this test."""
    got = {(p, m): op.get("operationId") for p, m, op in _operations(_schema())}
    assert got == {
        ("/api/registry/types/{id}", "get"): "lookupType",
        # The tier vocabulary, served rather than retyped into an interface.
        ("/api/registry/tiers", "get"): "listTiers",
        # The forge's catalogue of upstream modules (forge part 1, #362).
        ("/api/forge/catalogue", "get"): "readCatalogue",
        ("/api/forge/catalogue/{source}/{path}", "get"): "readCatalogueModule",
        ("/api/forge/catalogue/sync", "post"): "syncCatalogue",
        ("/api/registry/tools/{contract_id}", "get"): "readTool",
        # Forging (forge MVP 3, #364).
        ("/api/forge/adaptations", "post"): "startAdaptation",
        ("/api/forge/adaptations", "get"): "listAdaptations",
        ("/api/forge/adaptations/{adaptation_id}", "get"): "readAdaptation",
        ("/api/forge/adaptations/{adaptation_id}", "delete"): "abandonAdaptation",
        ("/api/forge/adaptations/{adaptation_id}/commands", "post"): "commandAdaptation",
        ("/api/forge/adaptations/{adaptation_id}/messages", "post"): "messageAdaptation",
        ("/api/forge/adaptations/{adaptation_id}/draft", "post"): "draftAdaptationPiece",
        ("/api/forge/adaptations/{adaptation_id}/assemble", "post"): "assembleAdaptation",
        ("/api/forge/adaptations/{adaptation_id}/tests", "post"): "runAdaptationTests",
        # **The build path, reachable at last.** `resolve_verbs.run` was argparse-shaped until
        # Plan 3C phase 0, so no route could exist here at all. `POST` because a `Goal` is a
        # document — profile, wants, producer pins — and a URL is the wrong place for one.
        ("/api/pipeline", "post"): "buildPipeline",
        ("/api/pipeline/example", "get"): "examplePipeline",
        ("/api/pipeline/compatibility", "get"): "compatibilityIndex",
        ("/api/pipeline/candidates", "get"): "listCandidates",
        # Every landed contract, for the builder's picker.
        ("/api/pipeline/modules", "get"): "listModules",
        ("/api/pipeline/validate", "post"): "validatePipeline",
        ("/api/pipeline/compare", "post"): "comparePipeline",
        ("/api/pipeline/draw", "post"): "drawPipeline",
        # **The living pipeline.** Two of these six are answered by the AI worker and return
        # before the answer exists (201 and 202); the other four answer in the response, because
        # a button click is not put behind the slow queue.
        ("/api/pipeline/authoring", "post"): "beginAuthoring",
        ("/api/pipeline/authoring/{session_id}", "get"): "readAuthoring",
        ("/api/pipeline/authoring/{session_id}/messages", "post"): "sayToAuthoring",
        (
            "/api/pipeline/authoring/{session_id}/proposals/{proposal_id}/decide",
            "post",
        ): "decideAuthoringProposal",
        (
            "/api/pipeline/authoring/{session_id}/proposals/{proposal_id}/alternatives/{option_id}",
            "get",
        ): "previewAuthoringAlternative",
        ("/api/pipeline/authoring/{session_id}/retry", "post"): "retryAuthoring",
        ("/api/pipeline/authoring/{session_id}/samples", "post"): "uploadAuthoringSample",
        ("/api/pipeline/authoring/{session_id}/preview", "get"): "previewAuthoring",
        ("/api/pipeline/authoring/{session_id}/edits", "post"): "editAuthoringDraft",
        ("/api/pipeline/authoring/{session_id}/facts/{subject}", "post"): "correctAuthoringFact",
        ("/api/pipeline/authoring/{session_id}/changes", "post"): "changeAuthoring",
        (
            "/api/pipeline/authoring/{session_id}/suggestions/{suggestion_id}",
            "post",
        ): "decideAuthoringSuggestion",
        (
            "/api/pipeline/authoring/{session_id}/facts/{subject}/history",
            "get",
        ): "authoringFactHistory",
        (
            "/api/pipeline/authoring/{session_id}/disagreements/{proposal_id}",
            "post",
        ): "answerAuthoringDisagreement",
        ("/api/pipeline/authoring/{session_id}/release-tool", "post"): "releaseAuthoringTool",
        ("/api/pipeline/authoring/vocabulary", "get"): "authoringVocabulary",
        # 14.7.4 (#191): the call panel, fetched when opened, never polled.
        ("/api/pipeline/authoring/{session_id}/calls", "get"): "listAuthoringCalls",
        ("/api/pipeline/drafts", "get"): "listDrafts",
        ("/api/pipeline/drafts", "post"): "createDraft",
        ("/api/pipeline/drafts/{draft_id}", "get"): "readDraft",
        ("/api/pipeline/drafts/{draft_id}", "put"): "saveDraft",
        ("/api/pipeline/drafts/{draft_id}", "delete"): "deleteDraft",
        # One builder (#395): every pipeline opens as a conversation.
        ("/api/pipeline/drafts/{draft_id}/session", "post"): "openDraftSession",
        ("/api/pipeline/drafts/{draft_id}/keep", "post"): "keepDraft",
        ("/api/pipeline/drafts/{draft_id}/artifact", "get"): "readArtifact",
        # **The only route that answers with bytes** — the courier's Mendel half, A179. It
        # serves a zip, so the generated client's return type is not a schema; `client.ts`
        # has a `blob()` for exactly this one and nothing else.
        ("/api/pipeline/drafts/{draft_id}/bundle", "get"): "downloadBundle",
        ("/api/pipeline/drafts/{draft_id}/emitted", "get"): "emittedPipeline",
        ("/api/pipeline/drafts/{draft_id}/gate", "post"): "startGate",
        ("/api/pipeline/gates/{run_id}", "get"): "readGate",
        ("/api/attention", "get"): "whatNeedsYou",
        ("/api/health/ai", "get"): "aiHealth",
        ("/api/health", "get"): "liveness",
        ("/api/health/registry", "get"): "registryHealth",
        ("/api/settings", "get"): "readSettings",
        ("/api/settings/retention/last", "get"): "readLastRetentionSweep",
        # Whether a model is configured, from settings alone: the describe box's question,
        # apart from `/health/ai`'s probe (issue 268).
        ("/api/settings/ai", "get"): "aiConfigured",
        ("/api/settings/{key}", "put"): "writeSetting",
        ("/api/settings/{key}/items/{name}/{action}", "post"): "runSettingAction",
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
    """The gap this closes: a route answers a coded refusal correctly and says nothing about it
    in its document, so a generated client types `detail` as the validation array and the UI
    renders nothing for the one message a person must read."""
    schema = _schema()
    assert "Refusal" in schema["components"]["schemas"]

    answer = schema["paths"][REFUSING[0]][REFUSING[1]]
    got = answer["responses"]["422"]["content"]["application/json"]["schema"]
    assert got["$ref"].endswith("/Refusal")


def test_the_refusal_schema_is_a_bare_ref():
    """A `$ref` with sibling keywords is legal JSON Schema and renders wrongly in every
    generator worth using — `openapi-typescript` produces an intersection nobody meant. This
    caught exactly that: declaring `model` *and* a hand-rolled `anyOf` merged into both."""
    schema = create_app().openapi()
    got = schema["paths"][REFUSING[0]][REFUSING[1]]["responses"]["422"]
    assert list(got["content"]["application/json"]["schema"]) == ["$ref"]


KNOWN_COLLISIONS: list[str] = []
"""None: the last two pairs went with the old forge. A new one fails the test below."""


def test_no_two_models_share_a_schema_name():
    """**A name collision silently renames the OTHER model, and only the frontend notices.**

    FastAPI disambiguates two classes sharing a name by qualifying *both* with their module
    path — so adding a second `Attention` beside `services/attention.Attention` once renamed
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
