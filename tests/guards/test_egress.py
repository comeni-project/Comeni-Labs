"""Invariant 14: data leaves through six declared doors and no others.

The doors are listed here, literally, on purpose. Adding one means editing a file
whose contents say "these are all the ways data leaves this building" — which is
the moment a person should be thinking, and this test is what makes them.

**Six since 2026-10-04 (door 6, the characteriser); five since 2026-09-05, on two
paths.** Five carry pipeline data along one prompt-taint path, door 6 the start of a sample;
`forge_review` carries a curator's message to a model about a candidate the forge proposed.
The forge stayed off this list for as long as it had no prompt — one of the three legs the
2026-08-17 exemption stood on, beside taking no `Goal` and writing no `pipeline.yml` — and a
review chat breaks exactly that leg. The other two still hold, which is what `DoorPath` records.

A separate `FORGE_DOORS` was considered and rejected: two files creates a cheaper file, and the
less-scrutinised one is where a door that belonged on the other list eventually goes."""

import enum
import typing

import pytest
from comeni_core.egress import boundaries as egress
from comeni_core.egress.authoring import AuthoringRequest
from comeni_core.egress.base import EgressPayload
from comeni_core.egress.characterisation import CharacteriseRequest
from comeni_core.egress.forge_review import ForgeReviewRequest, ReviewRole, ReviewTurn
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
    _marks_in,
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


def test_the_forge_review_door_is_grounded_on_a_revision():
    """§5.8 requires an immutable revision id, so an answer is about a specific candidate rather
    than about whatever the conversation has drifted to — the same reason `pipeline.yml` pins
    contracts by content digest.

    A chat grounded on the conversation alone is a chat that can be talked into discussing a
    candidate nobody is looking at, and the reviewer reading the answer has no way to tell.
    """
    with pytest.raises(ValidationError):
        ForgeReviewRequest(candidate="a contract")
    assert ForgeReviewRequest(revision="sha256:" + "a" * 64, candidate="a contract")


def test_the_forge_review_door_carries_codes_rather_than_a_tools_output():
    """`GateFailure`'s lesson, one level up. Nextflow's stderr names work directories and input
    filenames, which is why `ErrorCategory` is a closed vocabulary and the output stays on the
    machine that made it.

    A diagnostic code is the whole of what a reader needs in order to look something up, and it
    has no room for a path — which is the point of the alias rather than a side effect of it.
    """
    grounded = {"revision": "sha256:" + "a" * 64, "candidate": "x"}
    assert ForgeReviewRequest(**grounded, validation=["MD0105", "MF0401"])
    with pytest.raises(ValidationError):
        ForgeReviewRequest(**grounded, validation=["/work/ab/cd12 failed: no such file"])


def test_a_review_turn_says_who_wrote_it_from_a_closed_set():
    """The curator/model distinction is the whole reason this door exists: one is a string a
    person typed at request time and the other is what came back. A free-text author field
    would make the two indistinguishable in the record."""
    assert set(ReviewRole) == {ReviewRole.CURATOR, ReviewRole.MODEL}
    with pytest.raises(ValidationError):
        ReviewTurn(role="reviewer", content="hello")


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


def test_only_the_characterisation_door_can_reach_a_sample():
    """A sample field nested in any other door's payload, through any path, fails here."""
    reaching = {
        name
        for name, payload in egress.PAYLOADS.items()
        for model in reachable(payload)
        if _fields(model, Mark.SAMPLE)
    }
    assert reaching == {"characterisation"}


def test_the_characterisation_door_carries_the_excerpt_and_nothing_of_the_file():
    """Spec §6: no file name, no extension, no session, no question, no conversation."""
    door = egress.PAYLOADS["characterisation"]
    assert list(door.model_fields) == ["excerpt", "binary_before", "registry"]
    assert reachable(door) == {door}, "the payload holds no nested model that could grow a field"


@pytest.mark.parametrize(
    "text",
    ["x" * 8193, "a\n" * 201, "é" * 4097],
    ids=["bytes", "lines", "bytes-as-utf8"],
)
def test_an_excerpt_over_its_bound_is_refused_by_its_type(text):
    with pytest.raises(ValidationError):
        CharacteriseRequest(excerpt=text)


@pytest.mark.parametrize("separator", ["\u2028", "\x85", "\x0c"], ids=["u2028", "nel", "ff"])
def test_an_excerpt_counts_lines_as_the_cutter_does(separator):
    """Issue 237: 200 newline-separated lines are 200 lines, whatever else they hold."""
    text = "\n".join(f"a{separator}b" for _ in range(200))
    assert CharacteriseRequest(excerpt=text).excerpt


def test_an_excerpt_at_its_bound_is_accepted():
    assert CharacteriseRequest(excerpt="a\n" * 199 + "a").excerpt
    assert CharacteriseRequest(excerpt="x" * 8192).excerpt


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


def test_every_ambiguity_field_can_cross_the_door():
    """A32 — a field a model is never told is as much a boundary defect as one it should
    not be told.

    `Ambiguity` projects to `AmbiguityRequest` at door 2. The projection is written in Plan
    2, so nothing builds one yet — which is exactly when this is worth asserting, because a
    field added to an ambiguity between now and then would land nowhere and nobody would
    see it fail. `type_id` and `required` were already in that state when this was written.
    """

    from comeni_core.egress.resolution import AmbiguityRequest
    from comeni_core.plan.decision import Ambiguity, AmbiguityKinds

    # `model_fields`, not `_serialised_hints`, and deliberately: this asks whether each
    # ambiguity field has somewhere *to go*, and a `@computed_field` is not a destination —
    # nothing can be assigned to it. A57 widened the rules that ask what crosses a door; this
    # one asks what can be carried, which is a different question with a different answer.
    crossable = set(AmbiguityRequest.model_fields)
    for asked in AmbiguityKinds:
        for name in asked.model_fields:
            if name == "kind":
                continue  # the discriminator picks the projection; it is not projected
            assert name in crossable, (
                f"{asked.__name__}.{name} has nowhere to go in AmbiguityRequest, so a "
                f"model behind door 2 would never be told it"
            )
    assert Ambiguity.model_config.get("extra") == "forbid"


def test_every_tier_four_question_can_actually_cross_the_door():
    """A129 — the test above compares field *names*, and names were not the problem.

    `AmbiguityRequest` is documented as "the union of what the three `*Asked` types carry",
    and it accepted **one** of the three. Two failed on their *values*:

        ParamAsked  candidates=[None]                Input should be a valid string
        SourceAsked candidates=['star_align.bam']    not a contract id

    Door 2 is exactly what Plan 2 Task 5 opens, so today only producer questions can be asked
    of a model. A name-shaped assertion could never see it: every field had somewhere to go,
    and two kinds still could not get through. Construct one of each instead.
    """

    from comeni_core.egress.resolution import AmbiguityRequest
    from comeni_core.plan.decision import ParamAsked, ProducerAsked, SourceAsked

    for asked in (
        ParamAsked(node_id="star_align", subject="seq_platform", candidates=[None]),
        # Shaped exactly as `resolve.py:215` builds one — `type_id` and `required` included,
        # because a source question that does not say what type it is asking about is not a
        # question anybody asks. Omitting them here produced a second, spurious failure and
        # would have made this test assert something the resolver never emits.
        SourceAsked(
            node_id="samtools_sort",
            subject="source:reads",
            candidates=["star_align.bam", "trimgalore.reads"],
            type_id="alignment.bam",
            required=["coordinate_sorted"],
        ),
        ProducerAsked(
            node_id="star_align",
            subject="producer:alignment.bam",
            candidates=["nf-core/star/align@1.11.0"],
        ),
    ):
        payload = asked.model_dump()
        payload.pop("kind", None)
        AmbiguityRequest(**payload)


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
    file reporting 15 passed. (The payload was `PromptRequest` then and is `AuthoringRequest`
    now; the hole and the fix are the same one.)
    """

    class Sneaky(AuthoringRequest):
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


def test_the_door_carries_what_the_forge_measured_a_model_needs():
    """Not a shape check — a content one.

    The forge's prompt search (`docs/notes/journal/2026-08-17-prompt-search.md`) measured a local
    model going from 69% to 88% on three fixes, and two of them were **the question did not
    say what it was about** and **the evidence was not readable**. Door 2 projects a tier-4
    question to a model. A door that carries candidates and nothing else rebuilds the 69%
    configuration on the build path, having already paid to learn it.

    `closed` is here for the third measurement: opening a closed field was the *worst*
    configuration tested, six points below closing it, so whether the candidate list binds
    is something the model must be told rather than left to infer.
    """
    from comeni_core.egress.resolution import AmbiguityRequest

    for needed in ("what", "why_open", "closed", "evidence"):
        assert needed in AmbiguityRequest.model_fields, (
            f"{needed} does not cross door 2, so a tier-4 model call is the configuration "
            f"the forge measured at 69%"
        )


def test_the_authoring_door_cannot_reach_a_name_a_path_or_a_sample():
    """Door 1 grew, and this is the assertion that it grew only where it was argued to.

    `AuthoringRequest` replaced `PromptRequest` so that a *second* authoring turn could be
    grounded on what the first one established. Everything it gained beside the tail is typed
    registry vocabulary, and the risk in a change like that is not the field somebody argued
    for — it is the one that arrives later, on a nested model, because it was convenient.

    So this asks the question as an allowlist, the way `_leaf_problems` does: these are the
    marks reachable from door 1, and a new one fails here until somebody writes down why a
    goal-extraction call needs it.

    **What must never appear, and why each is tempting:**

    - `Mark.NF_PATH`, `Mark.TEST_DATA_REF` — a filename. `params.input` is a placeholder the
      lab fills at run time (invariant 15) and its *value* is the one thing Mendel never sees.
    - `Mark.FREE_TEXT` anywhere but the two declared fields — a draft's **name** is the
      tempting one. It is on the row the person clicked, it reads like helpful context, and it
      is the field a person is most likely to have typed a sample identifier into.
    - a `Path` of any kind, which `_leaf_problems` already refuses everywhere; named here
      because door 1 is the door where a path would look most like context.

    Samplesheet rows, run inputs and tool output are absent structurally rather than by a rule:
    none of the ten models reachable from here has a field that could hold one, and this test
    is what notices if one gains it.
    """
    door = egress.PAYLOADS["goal_extraction"]
    models = reachable(door)
    assert len(models) > 5, "the walk is not walking"

    marks = {
        meta
        for model in models
        for annotation in _serialised_hints(model).values()
        for meta in _marks_in(annotation)
    }
    assert marks == {
        Mark.FREE_TEXT,  # prompt, and a turn's content — the two argued for
        Mark.CONTRACT_ID,
        Mark.TYPE_ID,
        Mark.NODE_ID,
        Mark.OPTION_ID,
        Mark.STATE_NAME,
        # Through `Goal.have`, which names the port an input arrives on. Found by this test
        # rather than by reading — the list above was written from `AuthoringRequest`'s own
        # fields, and `Goal` brings its own vocabulary with it.
        Mark.PORT_NAME,
        Mark.CHANNEL_NAME,
        Mark.DIGEST,
        # Through `Goal.profile`: a fact an inspector measured names its pieces, `fastq@1.0.0`
        # (#134). A declared id with a validated shape, never prose.
        Mark.PIECE_REF,
        Mark.MEASUREMENT_ID,
        Mark.PARAM_LITERAL,
    }, f"door 1 reaches a mark nobody argued for: {sorted(m.value for m in marks)}"

    free = {field for model in models for field in _fields(model, Mark.FREE_TEXT)}
    assert free == {("AuthoringRequest", "prompt"), ("AuthoringTurn", "content")}, (
        f"free text reached door 1 somewhere new: {sorted(free)}"
    )


def test_unregistered_payloads_in_separate_modules_are_also_walked(monkeypatch):
    from comeni_core.egress import authoring

    class UnregisteredPayload(EgressPayload):
        pass

    monkeypatch.setattr(authoring, "UnregisteredPayload", UnregisteredPayload, raising=False)
    assert UnregisteredPayload not in egress.PAYLOADS.values()
    assert UnregisteredPayload in _payload_types()
