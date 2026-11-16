"""Invariant 14: data leaves through six declared doors and no others.

The doors are listed here, literally, on purpose. Adding one means editing a file
whose contents say "these are all the ways data leaves this building" — which is
the moment a person should be thinking, and this test is what makes them.

**Five, on the pipeline path.** Four carry pipeline data along one prompt-taint path and door 6
the start of a sample. **One on the forge's path**, `forge_drafting` (forge MVP 3, #364): public
module files and registry ids in, drafted items out, and no lab data.

A separate `FORGE_DOORS` was considered and rejected: two files creates a cheaper file, and the
less-scrutinised one is where a door that belonged on the other list eventually goes."""

import enum
import typing

import pytest
from comeni_core.egress import boundaries as egress
from comeni_core.egress.agent import AgentToolResult
from comeni_core.egress.base import EgressPayload
from comeni_core.plan.tiers import Tier, ValueSource
from comeni_core.spell.marks import Mark
from pydantic import ValidationError, computed_field
from support.egress import (
    BUILDERS,
    DOORS,
    FORGE_DOORS,
    FREE_TEXT_FIELDS,
    PIPELINE_DOORS,
    SAMPLE_FIELDS,
    _fields,
    _has_bare_str,
    _leaf_problems,
    _mentions_any,
    _mentions_binary,
    _mentions_mapping,
    _payload_types,
    _serialised_hints,
)
from support.walk import reachable


def test_every_door_is_walked_by_the_checks_below():
    """The guard that would have caught the hole above.

    Every check in this file starts from `_payload_types()`, so a door whose payload that
    set does not contain is a door nothing in here inspects — silently, and with a full green
    run to say so.
    """
    walked = _payload_types()
    for name, payload in egress.PAYLOADS.items():
        assert payload in walked, f"door {name} carries {payload.__name__}, and nothing walks it"


def test_every_payload_field_is_a_declared_shape():
    """Invariant 14, asked as an allowlist rather than as four prohibitions.

    Audit A19 (`object`), A20 (`Any`) and A30 (`Path`) are all the same defect: a shape the
    guard was not written against is silence. This closes them together with everything
    round three would otherwise find.
    """
    models = _payload_types()
    offenders: list[str] = []
    for payload in sorted(models, key=lambda m: m.__name__):
        for name, annotation in _serialised_hints(payload).items():
            offenders += _leaf_problems(annotation, f"{payload.__name__}.{name}", models)
    assert offenders == [], "these payload fields are not declared shapes:\n" + "\n".join(offenders)


def test_the_doors_are_exactly_the_ones_listed_here():
    """Require the boundary registry to match the explicitly allowed names."""
    assert set(egress.PAYLOADS) == DOORS


def test_pipeline_data_leaves_through_exactly_the_pipeline_doors():
    """Check that pipeline and forge payloads are assigned to the intended flows."""
    assert set(egress.payloads_for(egress.BoundaryFlow.PIPELINE)) == PIPELINE_DOORS
    assert set(egress.payloads_for(egress.BoundaryFlow.FORGE)) == FORGE_DOORS


def test_every_door_declares_which_path_it_is_on():
    """Check that payload and flow lookups are derived from the same boundary registry."""
    assert set(egress.FLOWS) == set(egress.PAYLOADS) == set(egress.BOUNDARIES)
    for name, door in egress.BOUNDARIES.items():
        assert egress.PAYLOADS[name] is door.payload
        assert egress.FLOWS[name] is door.flow


def test_every_door_declares_an_egress_payload():
    assert egress.PAYLOADS, "no outbound boundary is declared"
    for name, payload in egress.PAYLOADS.items():
        assert issubclass(payload, EgressPayload), name


def test_free_text_lives_only_where_declared():
    """Fourteen fields, not two, and not six, and not ten.

    CLAUDE.md said "exactly two" for a plan and a half while this list held four, then six;
    the list is the honest count and the prose is what drifts. Six became seven when
    `Pipeline` took door 4 — by a payload swap rather than by a new kind of string crossing,
    which is exactly the sort of change a literal list exists to make someone look at.
    """
    found: set[tuple[str, str]] = set()
    for payload in _payload_types():
        found |= _fields(payload, Mark.FREE_TEXT)
    assert found == FREE_TEXT_FIELDS


def test_sample_data_lives_only_where_declared():
    found: set[tuple[str, str]] = set()
    for payload in _payload_types():
        found |= _fields(payload, Mark.SAMPLE)
    assert found == SAMPLE_FIELDS


def test_only_the_agent_door_can_reach_a_sample():
    """A sample field nested in any other door's payload, through any path, fails here. The
    builder agent's door reaches a sample's name (the operator's decision, 2026-11-14; see
    `tests/fixtures/guard-ledger.md`)."""
    reaching = {
        name
        for name, payload in egress.PAYLOADS.items()
        for model in reachable(payload)
        if _fields(model, Mark.SAMPLE)
    }
    assert reaching == {"builder_agent"}


def test_the_builder_agent_door_is_the_conversation_and_one_typed_result_per_tool_call():
    """#463: what reaches the agent's model is the conversation — the person's words and the
    agent's own — and, per tool call, a tool's name, whether it worked, a typed view or a coded
    refusal: never a raw row or a dict."""
    from comeni_core.egress.agent import AgentToolResult, AgentTurn

    door = egress.PAYLOADS["builder_agent"]
    assert list(door.model_fields) == ["turns", "results"]
    assert list(AgentTurn.model_fields) == ["speaker", "content"]
    assert list(AgentToolResult.model_fields) == ["tool", "ok", "view", "refusal"]
    assert egress.FLOWS["builder_agent"] is egress.BoundaryFlow.PIPELINE


def test_payloads_forbid_unknown_fields():
    payloads = _payload_types()
    assert payloads, "no payload types were found — the scan, not the doors, is what failed"
    for payload in payloads:
        assert payload.model_config.get("extra") == "forbid", payload.__name__


def test_no_payload_carries_an_undeclared_string():
    """Every string is either a declared ID alias or explicitly marked `Mark.FREE_TEXT`.

    Without this, `user_note: str` sails through every other test in this file — it
    carries no `Mark` to catch and no `Any` to forbid — and a prompt fits in
    it perfectly. Found by running the plan's own break-the-guard step, which is what
    that step is for.
    """
    offenders = []
    for payload in _payload_types():
        for name, annotation in _serialised_hints(payload).items():
            if _has_bare_str(annotation):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == [], (
        "these fields are plain `str`; annotate them as an ID type or as free text: "
        + ", ".join(sorted(offenders))
    )


def test_no_payload_carries_a_mapping():
    """A payload may not contain a dict, however cleverly its key is typed.

    `dict[MeasurementId, MeasurementValue]` passes every other rule in this file —
    the key is an Annotated newtype, so the bare-str rule does not fire — and is
    still unsafe, because nothing checks the key was ever *declared*. A payload
    carrying {"patient_id": "4471023"} would type-check perfectly.

    That is the `user_note: str` lesson one level up: the right shape is not the
    right content. Rather than a subtle rule about which key types are acceptable,
    payloads carry lists of declared records. Subtlety is what failed last time.
    """
    offenders = []
    for payload in _payload_types():
        for name, annotation in _serialised_hints(payload).items():
            if _mentions_mapping(annotation):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == [], (
        "these fields are mappings; use a list of declared records instead: "
        + ", ".join(sorted(offenders))
    )


def test_no_payload_carries_raw_bytes():
    """A blob is an unbounded channel, and no rule in this file can see inside one.

    Nothing carries one today, which is why this is the easy time to forbid it. A
    `signature: bytes` on the lockfile is the plausible next field and would have been
    accepted by every other rule here.
    """
    offenders = []
    for payload in _payload_types():
        for name, annotation in _serialised_hints(payload).items():
            if _mentions_binary(annotation):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == [], (
        "these fields are binary blobs, which no rule in this file can inspect: "
        + ", ".join(sorted(offenders))
    )


def test_no_payload_carries_an_untyped_container():
    """A dict[str, Any] would defeat the whole thing, so no payload may declare one."""
    offenders = []
    for payload in _payload_types():
        for name, annotation in _serialised_hints(payload).items():
            if _mentions_any(annotation):
                offenders.append(f"{payload.__name__}.{name}")
    assert offenders == [], (
        "these fields are `Any`, which defeats every other rule here: "
        + ", ".join(sorted(offenders))
    )


# --- Plan 1.10 Task 11: Pipeline is door 4's payload ----------------------------------
def test_publication_carries_a_pipeline():
    """The artifact a person reads before publishing and the thing that crosses the boundary
    are one document. `PublishBundle` held goal + IR + decisions + lockfile — the same
    information one layer less assembled, and one more thing that could disagree with what
    was on disk."""
    from comeni_core.artifact.pipeline import Pipeline

    assert egress.PAYLOADS["publication"] is Pipeline


def test_publish_bundle_is_gone():
    """Retired, not deprecated. A type nothing constructs is a type that drifts, and its name
    was load-bearing rationale in eight other files — rationale citing a deleted type reads as
    authoritative and cannot be checked."""
    assert not hasattr(egress, "PublishBundle")


def test_the_publication_payload_is_frozen():
    """`EgressPayload` sets `frozen=True`, so what was reviewed is what is sent.

    `gate` and `emitted` are stamped with `model_copy` rather than assigned, which is the
    right shape for them anyway: both are evidence about a finished pipeline, and evidence
    should not be edited in place.
    """
    import pytest
    from comeni_core.artifact.pipeline import Pipeline
    from comeni_core.goal.asked import Goal
    from pydantic import ValidationError

    # A real intent and facts so the refusal is the *frozen assignment*, not a missing field
    # (A48 made them required, and a bare `Pipeline()` would raise for the wrong reason).
    frozen = Pipeline(intent=Goal().intent, facts=Goal().facts)
    with pytest.raises(ValidationError):
        frozen.gate = "test"


def test_pipeline_holds_no_registry():
    """`registry.py` carries a mapping and says it is legal because a `Registry` is not
    payload-reachable. That sentence became load-bearing the moment the artifact itself
    crossed door 4: materialisation must copy values, never hold the thing it read them from.
    """
    import re

    from comeni_core.artifact.pipeline import Pipeline

    # Word boundaries, not `in`. The first version matched `RegistryProvenance` and reported
    # `Pipeline.registry holds a Registry` — the same substring trap `test_pipeline_totality`
    # hit on the same word, which is what makes it worth a comment rather than a quiet fix.
    forbidden = re.compile(r"\b(Registry|ModuleContract|Vocabulary|MeasurementRegistry)\b")
    for model in reachable(Pipeline):
        for name, annotation in _serialised_hints(model).items():
            held = forbidden.search(str(annotation))
            assert held is None, f"{model.__name__}.{name} holds a {held.group()}"


def test_a_computed_field_cannot_cross_a_door_unchecked():
    """A57. `@computed_field` puts a key in the serialised JSON and lands in
    `model_computed_fields` — which no rule in this file consulted, because every one of them
    filtered on `model_fields`.

    The leaf allowlist was inverted from a blocklist precisely so that a shape nobody named
    could not be silence (A19, A20, A30). It was still a blocklist with respect to *where a
    value comes from*: the audit put a patient path into door 1's JSON this way with the whole
    file reporting 15 passed. (The payload was `PromptRequest` then; the hole and the fix are
    the same on any door.)
    """

    class Sneaky(AgentToolResult):
        @computed_field
        @property
        def context(self) -> str:
            return "/data/patients/PT-4471023/notes: BRCA1 c.68_69del"

    models = _payload_types() | {Sneaky}
    offenders = [
        problem
        for name, annotation in _serialised_hints(Sneaky).items()
        for problem in _leaf_problems(annotation, f"Sneaky.{name}", models)
    ]
    assert offenders, "a computed bare `str` crossed the door with no Mark and no complaint"


def test_no_payload_replaces_its_own_dump():
    """A57, the other half — and a different shape, which is the finding's real content.

    A `@computed_field` has a return annotation, so it can go through the leaf check above.
    A `@model_serializer` replaces the dump wholesale: there is no per-key annotation left to
    check, and the audit returned `{"site": "/mnt/phi/…", "notes": "BRCA1 c.68_69del"}` from
    one with 15 passed. Nothing can be checked about it, so the only enforceable rule is that
    a payload may not define one.
    """
    for payload in sorted(_payload_types(), key=lambda m: m.__name__):
        declared = dict(payload.__pydantic_decorators__.model_serializers)
        assert not declared, (
            f"{payload.__name__} defines @model_serializer {sorted(declared)} — the dump no "
            "longer corresponds to the fields this file checks, so nothing here can see what "
            "crosses the door"
        )


# --- Round four's carried egress findings: A63, A65, A66 ---------------------------------
def test_an_enum_with_a_missing_hook_is_not_a_declared_shape():
    """A63, issue #27. `_leaf_problems` returned `[]` for any `Enum`, on the premise that an
    enum is closed vocabulary. `Enum._missing_` is the documented hook for accepting
    *undeclared* values and can synthesise a member from anything — the reviewer added such a
    field to `GateFailure` (door 3) and crossed an arbitrary path string with 15 passed.

    So "an enum is closed" is a claim about a class, not about the type, and the check has to
    read the class to know which it has.
    """

    class Sneaky(enum.StrEnum):
        KNOWN = "known"

        @classmethod
        def _missing_(cls, value):  # pragma: no cover — never called; its presence is the point
            return cls.KNOWN

    assert _leaf_problems(Sneaky, "Probe.field", set()), "an open enum passed as closed vocabulary"


def test_an_ordinary_enum_is_still_a_declared_shape():
    """The negative. Every closed vocabulary in this repository is a `StrEnum`, and refusing
    them would be a check nobody could satisfy."""
    assert _leaf_problems(Tier, "Probe.field", set()) == []
    assert _leaf_problems(ValueSource, "Probe.field", set()) == []


def test_a_missing_hook_on_a_base_class_is_caught_too():
    """`_missing_` inherited from a base below `Enum` is the same hook one level up, and a
    check that reads only `vars(cls)` would miss it."""

    class OpenBase(enum.StrEnum):
        @classmethod
        def _missing_(cls, value):  # pragma: no cover
            return None

    class Derived(OpenBase):
        KNOWN = "known"

    assert _leaf_problems(Derived, "Probe.field", set())


def test_the_ambiguity_kinds_tuple_is_the_subclass_set():
    """A65, issue #29. The door-totality test loops over a literal tuple in `decision.py`,
    and its docstring claims "a fourth kind added without a slot would fail" — true only if
    the author also edits the tuple. The reviewer added a fourth `Ambiguity` subclass not in
    the tuple and got 15 passed: the check is live and its input was incomplete.
    """
    from comeni_core.plan.decision import Ambiguity, AmbiguityKinds

    assert set(AmbiguityKinds) == set(Ambiguity.__subclasses__()), (
        "a kind exists that the totality check never sees"
    )


def test_every_publication_payload_model_is_frozen():
    """A66, issue #30. `EgressPayload` was frozen and every nested model was a plain
    `BaseModel`, so `Emitted.files[0].digest` could be reassigned after review — on the one
    field that *is* the self-verification evidence.

    `test_the_publication_payload_is_frozen` asserted the top level and generalised in its
    docstring to "what was reviewed is what is sent". Publication is the door with no undo,
    so the gap between the claim and the check mattered most exactly there.
    """
    mutable = sorted(
        model.__name__
        for model in reachable(egress.PAYLOADS["publication"])
        if not model.model_config.get("frozen", False)
    )
    assert mutable == [], (
        "these models are reachable from the publication payload and can be mutated after "
        f"review; that door has no undo:\n  {', '.join(mutable)}"
    )


def test_the_only_unfrozen_payload_models_are_the_ir_builders():
    """The residue, named so it is a decision rather than an oversight — and pinned, so a
    *new* mutable model cannot join them quietly."""
    mutable = {
        model.__name__ for model in _payload_types() if not model.model_config.get("frozen", False)
    }
    assert mutable == BUILDERS, (
        "the unfrozen set moved. Anything outside the IR that a payload can reach must be "
        f"frozen, or listed in BUILDERS with its reason:\n  {sorted(mutable ^ BUILDERS)}"
    )


# --- A64, issue #28: a declared ID alias that validates nothing is a `str` with a label ---
@pytest.mark.parametrize(
    "alias, bad, why",
    [
        ("NodeId", "patient PT-4471, /data/S1_R1.fastq.gz", "a path and an identifier"),
        ("PortName", "dx: carcinoma", "a colon and a space"),
        ("StateName", "dx: carcinoma\nnotes: see /mnt/phi/4471.pdf", "a newline"),
        ("MeasurementId", "/data/patients/PT-4471023/S1.fastq.gz", "a path"),
        ("ModuleKey", "notes: see /mnt/phi/4471.pdf", "a path"),
        ("Digest", "not-a-digest: PT-4471023", "not a digest at all"),
        ("Subject", "dx: carcinoma\nnotes: /mnt/phi/4471.pdf", "a newline"),
        ("DecisionKey", "a\nb", "a newline"),
        ("LayerName", "x\ny", "a newline"),
        ("PieceRef", "fastq@1.0.0 PT-4471023", "a patient id after a piece"),
    ],
)
def test_a_declared_id_alias_refuses_free_text(alias, bad, why):
    """A64, issue #28. Invariant 14 says every string on a payload is *"a declared ID alias
    or marked `Mark.FREE_TEXT`"*, and nine of the aliases were `Annotated[str, Mark.X]` with
    no `AfterValidator` — so "a declared ID alias" meant "a `str` with a label".

    On the **unmodified tree** the reviewer crossed door 2 with a patient identifier as a
    `node_id`, a variant as a `subject` and clinical notes with an embedded newline as a
    `state`, and door 4 with `digest='not-a-digest: PT-4471023'`. All serialised verbatim.
    This generalises A3, which was recorded for `PARAM_LITERAL` alone.
    """
    from comeni_core.spell import marks
    from pydantic import TypeAdapter

    with pytest.raises(ValidationError):
        TypeAdapter(getattr(marks, alias)).validate_python(bad)


@pytest.mark.parametrize(
    "alias, good",
    [
        ("NodeId", "star_align"),
        ("PortName", "reads"),
        ("StateName", "coordinate_sorted"),
        ("MeasurementId", "read_length"),
        ("ModuleKey", "nf-core/star/align"),
        ("Digest", "sha256:" + "a" * 64),
        ("Subject", "seq_platform"),
        ("DecisionKey", "star_align.seq_platform"),
        ("LayerName", "comeni-registry-examples"),
        ("PieceRef", "read_length@1.0.0"),
    ],
)
def test_a_declared_id_alias_accepts_what_the_repository_writes(alias, good):
    """The negative that keeps every validator above honest. A shape check tight enough to
    refuse a real value is a check somebody has to disable, and a disabled check is worse
    than none — which is `_computed_over`'s `paired-end` lesson, one layer down."""
    from comeni_core.spell import marks
    from pydantic import TypeAdapter

    assert TypeAdapter(getattr(marks, alias)).validate_python(good) == good


def test_every_mark_carries_a_validator_or_is_listed_as_a_label():
    """The residue, pinned. A `Mark` with no validator is legitimate only if somebody decided
    it, and this is what turns that into a decision."""
    from comeni_core.spell import marks

    unvalidated = sorted(
        name
        for name, alias in vars(marks).items()
        if name[0].isupper()
        and typing.get_origin(alias) is typing.Annotated
        and any(isinstance(m, Mark) for m in getattr(alias, "__metadata__", ()))
        and not any(
            type(m).__name__ == "AfterValidator" for m in getattr(alias, "__metadata__", ())
        )
    )
    assert unvalidated == sorted(marks.LABEL_ONLY), (
        "a declared ID alias with no validator is a `str` with a label. Give it one, or add "
        f"it to `marks.LABEL_ONLY` with the reason:\n  {unvalidated}"
    )


def test_unregistered_payloads_in_separate_modules_are_also_walked(monkeypatch):
    from comeni_core.egress import agent

    class UnregisteredPayload(EgressPayload):
        pass

    monkeypatch.setattr(agent, "UnregisteredPayload", UnregisteredPayload, raising=False)
    assert UnregisteredPayload not in egress.PAYLOADS.values()
    assert UnregisteredPayload in _payload_types()



def test_the_forge_door_carries_no_lab_data():
    """Forging sends public tool files and registry ids (#364): no goal, sample or run."""
    from comeni_core.egress.forge import ForgeRequest

    assert egress.PAYLOADS["forge_drafting"] is ForgeRequest
    forge = [p for p in _payload_types() if p.__module__ == "comeni_core.egress.forge"]
    assert forge, "the forge door's models are walked"
    for payload in forge:
        assert not _fields(payload, Mark.SAMPLE), payload.__name__
        hints = " ".join(repr(h) for h in typing.get_type_hints(payload).values())
        for lab in ("Goal", "Pipeline", "Characterise", "Sample"):
            assert lab not in hints, f"{payload.__name__} reaches {lab}"
