"""The doors data may leave through, and the types that may pass them.

Invariant 14. There are **five**, on **two paths**. Four carry pipeline data along one
prompt-taint path — goal extraction, tier-4 resolution, compiler repair, publication — and the
fifth carries forge review, which is a different path with a different author and the same
rules. Each carries one declared payload type.

**Why one list rather than two.** The forge is not on the pipeline path and never was
(`notes/specs/2026-08-17-forge-phase-2.md` §1), so a separate `FORGE_DOORS` was the tidy
option. It is the wrong one: the mechanism this file buys is that widening the boundary means
editing a file that says *these are all the ways data leaves*, and two files creates a cheaper
file — the less-scrutinised one, which is where a door that belonged on the other list
eventually goes. `DoorPath` keeps the distinction without splitting the scrutiny.

This module declares those types and can never send one. Invariant 1 keeps every
transport in the impure packages, so pure code decides what may leave and impure
code does the leaving; neither can do the other's job.

Publication is the door with no undo. A leaked prompt in a model call is an
incident; a leaked prompt in a signed public registry is in every clone's history
permanently, and git is built to make that hard to reverse.
"""

from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from comeni_core.artifact.digest import digest_of_bytes
from comeni_core.plan.ir import PipelineIR
from comeni_core.review.question import Excerpt
from comeni_core.spell.marks import (
    ContractId,
    DiagnosticCode,
    Digest,
    EdgeRef,
    Line,
    NfPath,
    NodeId,
    StateName,
    Subject,
    Text,
    TypeId,
)

CandidateRef = ContractId | EdgeRef | None
"""What a tier-4 question can offer a model. **A closed union, not a widening.**

Three shapes because there are three kinds of question, and the door is documented as their
union: a producer question offers contract ids, a source question offers `<node>.<port>` edge
references, and a parameter question offers `[None]` — the honest spelling of "no default was
ever written", which is A83 and not this alias's to fix. `None` stays until a `Param` has a
declared domain (Plan 2 Task 11).

It was `list[ContractId]`, so **two of the three kinds could not cross their own door**: a
`ParamAsked` failed on `None` and a `SourceAsked` on `star_align.bam` not being a contract id.
`test_every_ambiguity_field_can_cross_the_door` was green throughout, because it compares field
*names* and names were never the problem. Audit A129, and the same family as #32/A68.

**No bare `str`.** Every member is a declared alias, because a bare `str` bypasses the marker
in one line and a prompt fits in it perfectly — invariant 14's whole argument.
"""


def _publication_payload() -> type[BaseModel]:
    """`Pipeline`, resolved late.

    `comeni_core.artifact.pipeline` imports `Emitted` from this module, so naming the type
    at the top would be a cycle. A function keeps the declaration in `DOORS` where every other
    door is
    declared, rather than registering it from somewhere else — the point of that mapping is
    that the four doors are readable in one place.
    """
    from comeni_core.artifact.pipeline import Pipeline

    return Pipeline


class EgressPayload(BaseModel):
    """Base for anything that may cross a door.

    `extra="forbid"` so a field cannot be smuggled in at runtime; `frozen=True` so
    what was reviewed is what is sent.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class ErrorCategory(StrEnum):
    """Why a gate failed, as closed vocabulary.

    Nextflow's stderr carries work directories and input filenames, and the repair
    loop would forward it to a model. Machine-generated text is the likeliest leak
    precisely because nobody wrote it and nobody reads it. So the category is
    parsed from the output and the output itself stays on the machine that made it.
    """

    MISSING_INPUT = "missing_input"
    CHANNEL_CARDINALITY = "channel_cardinality"
    SYNTAX = "syntax"
    CONTAINER_PULL = "container_pull"
    TOOL_ERROR = "tool_error"
    UNKNOWN = "unknown"


class GateFailure(EgressPayload):
    """A gate failure reduced to facts."""

    process: NodeId
    exit_code: int
    category: ErrorCategory
    tool_message: Text | None = None
    """Populated only in the `open` profile. Free text, and declared as such."""


class PromptRequest(EgressPayload):
    """Door 1 — goal extraction. The single taint source."""

    prompt: Text


class AmbiguityRequest(EgressPayload):
    """Door 2 — tier-4 resolution. Registry vocabulary and nothing else.

    Deliberately not a free-form context dict. `dict[str, Any]` would carry
    anything, which is why the guard forbids it — the fields a tier-4 call
    actually needs are these.

    **The union of what the three `*Asked` types carry**, asserted by
    `tests/guards/test_egress.py`: a field added to an ambiguity that has nowhere to land here is a
    field a model would silently not be told, which is the quiet half of A32. `type_id` and
    `required` were exactly that — `SourceAsked` carries them and the door had no slot.

    **`what`, `why_open`, `closed` and `evidence` arrived with Plan 2.5**, when `Ambiguity`
    became a `Question` and inherited them. They are not incidental padding: the forge
    measured a local model at 69% without them and 88% with, and two of the three fixes
    behind that jump were *say what the question is about* and *make the evidence readable*.
    A door carrying bare candidates rebuilds the 69% configuration on the build path.

    **`candidates` keeps the door's own stricter typing.** `Question.candidates` is
    `list[Candidate]` — a value and a note a reviewer reads. Here it stays
    `list[CandidateRef]`, which is `ContractId | EdgeRef | None`, because A129 records that
    this payload accepted only one of the three `*Asked` types until their *values* were
    checked rather than their field names. Widening the door to the base's looser shape
    would undo that.
    """

    node_id: NodeId
    subject: Subject
    what: Line = ""
    why_open: Line = ""
    candidates: list[CandidateRef] = []
    closed: bool = True
    evidence: list[Excerpt] = []
    states: list[StateName] = []
    """States required of the thing being chosen. Was `list[TypeId]`, which is a different
    vocabulary — nothing had ever put a value in it, so nothing disagreed."""
    tier_hint: int | None = None
    type_id: TypeId = ""
    required: list[StateName] = []


class RepairRequest(EgressPayload):
    """Door 3 — compiler repair. The IR, plus typed failure facts."""

    ir: PipelineIR
    failure: GateFailure


class EmittedFile(BaseModel):
    """One generated file, and the digest of what was written."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: NfPath
    digest: Digest


class Emitted(BaseModel):
    """What `mendel publish` actually wrote, recorded rather than reconstructed.

    A28: the verdict `mendel upgrade` printed came from `diff_ir`, which enumerates the
    fields it knows about — so every field added to the IR was a new blind spot, silently,
    and the tool said *"no changes: this pipeline re-resolves identically"* while `main.nf`
    had demonstrably moved.

    Comparing bytes is the right mechanism, but **do not reconstruct the past — record
    it.** Re-emitting the bundle's own IR needs the registry as it was, and a contract
    removed from the registry is one of the two cases upgrade exists to report: re-emitting
    dies with `KeyError` on exactly it. `drift_against` had this same bug in Plan 1.7, for
    the same reason.

    Sorted by name, for Plan 1.7's rule: a hash over concatenated fields means nothing
    unless each field can be read one way only. The generated files only — never the copied
    `modules/` tree, which is vendored rather than emitted.

    It also makes a bundle self-verifying independently of upgrade: a recipient can check
    that the pipeline they were handed is the pipeline the bundle describes. That property
    did not exist at all.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    """The `SCHEMA_VERSION` `from_digest` was taken under. **Not the file's version.**

    `from_digest` hashes the model dump, so **any field added to the artifact moves it** —
    for every pipeline ever archived, at once, without anybody touching one. Plan 1.13 added
    `CallArg.join` and `MD0213` began reporting every pre-1.13 file as edited by a human,
    while its `main.nf` and `nextflow.config` still hashed exactly to their records. The
    pipeline had not changed; the reader had.

    Recording the version the digest was taken under is what lets `is_stale` distinguish "you
    edited this" from "the schema moved" — two very different things that were one message.
    Defaulting to `1` is correct rather than convenient: a file with no such field *was*
    written under version 1, which is precisely the claim being made.

    Found while executing Plan 1.13, not by the design audit. The fixture that demonstrates
    it is `tests/fixtures/pipeline-v1/`.
    """

    files: list[EmittedFile] = []
    from_digest: Digest | None = None
    """The digest of the pipeline content these files were generated **from**.

    `files` catches a hand-edited `main.nf`. It cannot catch the opposite and likelier
    mistake, which consolidating four artifacts into one is what opens: **Nextflow runs
    `main.nf`, not `pipeline.yml`.** Edit the file you were told to edit, forget `mendel
    emit`, and the pipeline that runs is not the pipeline that is documented — with every
    digest here matching, because the bytes on disk are exactly the bytes that were written.
    The artifact and the run diverge silently, which is the one failure this whole design
    exists to prevent, arriving through the door the design itself installs.

    Computed over the model with `emitted:` **excluded** — otherwise it would have to contain
    its own digest. That is the same exclusion `ResolvedValue._drop_computed` makes for
    `review_level`, and for the same reason: a derived field inside the thing it describes
    does not round-trip.

    `None` means no evidence, as it does for `gate`. It must never read as "identical".
    """

    @classmethod
    def of(
        cls,
        directory: Path,
        names: Sequence[str],
        from_digest: Digest | None = None,
        schema_version: int = 1,
    ) -> "Emitted":
        return cls(
            files=[
                EmittedFile(name=name, digest=digest_of_bytes((directory / name).read_bytes()))
                for name in sorted(names)
            ],
            from_digest=from_digest,
            schema_version=schema_version,
        )


class ReviewRole(StrEnum):
    """Who wrote a turn of a review conversation.

    Closed, and the distinction is the whole reason door 5 exists: a `CURATOR` turn is a string
    a person typed, at request time, and that is what door 1 is on the pipeline side. A `MODEL`
    turn is what came back, quoted so the next turn has context.
    """

    CURATOR = "curator"
    MODEL = "model"


class ReviewTurn(EgressPayload):
    """One exchange in a forge review conversation."""

    role: ReviewRole
    content: Text


class ForgeReviewRequest(EgressPayload):
    """Door 5: a curator asking a model about a candidate the forge proposed.

    **Grounded on a revision, not on a conversation.** An answer is about a specific candidate
    rather than about whatever the chat has drifted to — the same reason `pipeline.yml` pins
    contracts by content digest.

    **`validation` carries codes, never a tool's output.** That is `GateFailure`'s lesson
    applied one level up: Nextflow's stderr names work directories and input filenames, so the
    category is parsed and the output stays on the machine that made it. A diagnostic code is
    the whole of what a reader needs in order to look something up, and `DiagnosticCode` has no
    room for a path.

    **`candidate` is free text and is listed as such.** It is the proposed contract or module
    as a reviewer sees it — composed by the forge from public sources and by a model from those
    same sources, never from a prompt or a goal, which is the bound that keeps `Excerpt` honest
    on the list above.
    """

    revision: Digest
    candidate: Text
    validation: list[DiagnosticCode] = []
    evidence: list[Excerpt] = []
    turns: list[ReviewTurn] = []


class DoorPath(StrEnum):
    """Which flow a door belongs to.

    `PIPELINE` is invariant 14's original claim — prompt, goal, build, pipeline, publish, one
    path with free text entering at exactly one point. `FORGE` is registry authoring: public
    tool documentation in, reviewed registry data out, and no `Goal` anywhere in it.

    They are distinguished rather than separated, so *pipeline data leaves through four doors*
    stays a checkable sentence while every door still lives in one list.
    """

    PIPELINE = "pipeline"
    FORGE = "forge"


class Door(NamedTuple):
    """One declared crossing: what may pass it, and which flow it serves.

    A `NamedTuple` rather than a dataclass because `dataclasses` is not on this package's
    purity allowlist, and rather than a `BaseModel` because it holds a *type* rather than a
    value — the payload class itself, which is what the guard walks from. Adding an import to
    a guard's allowlist to suit one record is the move that allowlist exists to make somebody
    argue for, and there was no argument here.
    """

    payload: type[BaseModel]
    path: DoorPath


DECLARED: dict[str, Door] = {
    "goal_extraction": Door(PromptRequest, DoorPath.PIPELINE),
    "tier4_resolution": Door(AmbiguityRequest, DoorPath.PIPELINE),
    "compiler_repair": Door(RepairRequest, DoorPath.PIPELINE),
    # Door 4 carries a `Pipeline` since Plan 1.10 Task 11. `PublishBundle` held goal + IR +
    # decisions + lockfile, which is the same information one layer less assembled; the
    # artifact on disk *is* the payload now, so what a person reads before publishing and
    # what crosses the door are one document rather than two that can disagree.
    #
    # Imported inside the mapping to keep this module's import graph acyclic:
    # `comeni_core.artifact.pipeline` imports `Emitted` from here.
    "publication": Door(_publication_payload(), DoorPath.PIPELINE),
    # Door 5, 2026-09-05. **The first string a person types into the forge.**
    #
    # The forge stayed off this list for as long as it had no prompt — that was one of the
    # three legs the 2026-08-17 exemption stood on, beside taking no `Goal` and writing no
    # `pipeline.yml`. A review chat breaks exactly that leg: `ReviewTurn.content` is authored
    # by a curator, at request time, and goes to a provider. The other two legs still hold,
    # which is what `DoorPath.FORGE` records.
    #
    # Generating a proposal is deliberately NOT a door, and the line is *who authored the
    # string*: a dossier is composed entirely from vendored modules and registry files, which
    # is the same bound that makes `Excerpt` the one quoted rather than composed entry above.
    "forge_review": Door(ForgeReviewRequest, DoorPath.FORGE),
}
"""Every door, in one place, each saying which flow it serves.

One declaration with two projections below — `DOORS` and `PATHS` — rather than two mappings
kept in step by hand. A pair of dicts that must agree is the shape this repository keeps finding
to be one mechanism and one decoration.
"""

DOORS: dict[str, type[BaseModel]] = {name: door.payload for name, door in DECLARED.items()}
"""Door name -> the one type that may cross it."""

PATHS: dict[str, DoorPath] = {name: door.path for name, door in DECLARED.items()}
"""Door name -> the flow it serves."""


def doors_on(path: DoorPath) -> dict[str, type[BaseModel]]:
    """The doors of one flow. `doors_on(DoorPath.PIPELINE)` is invariant 14's original four."""
    return {name: door.payload for name, door in DECLARED.items() if door.path is path}
