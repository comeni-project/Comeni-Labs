"""The doors data may leave through, and the types that may pass them.

Invariant 14. There are four: goal extraction, tier-4 resolution, compiler repair,
and publication. Each carries one declared payload type.

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

from pydantic import BaseModel, ConfigDict

from comeni_core.decision import DecisionRecord
from comeni_core.digest import digest_of_bytes
from comeni_core.gates import Gate
from comeni_core.goal import Goal
from comeni_core.ir import PipelineIR
from comeni_core.lockfile import Lockfile
from comeni_core.marks import (
    ContractId,
    Digest,
    NfPath,
    NodeId,
    StateName,
    Subject,
    Text,
    TypeId,
)


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
    `tests/test_egress.py`: a field added to an ambiguity that has nowhere to land here is a
    field a model would silently not be told, which is the quiet half of A32. `type_id` and
    `required` were exactly that — `SourceAsked` carries them and the door had no slot.
    """

    node_id: NodeId
    subject: Subject
    candidates: list[ContractId] = []
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

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

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
        cls, directory: Path, names: Sequence[str], from_digest: Digest | None = None
    ) -> "Emitted":
        return cls(
            files=[
                EmittedFile(name=name, digest=digest_of_bytes((directory / name).read_bytes()))
                for name in sorted(names)
            ],
            from_digest=from_digest,
        )


class PublishBundle(EgressPayload):
    """Door 4 — publication. The door with no undo.

    A shareable pipeline is what a human asked for, what it resolved to, why each choice
    was made, and against exactly which registry — federation spec §4.1. All four, or the
    recipient cannot reproduce it and cannot audit it.
    """

    goal: Goal
    ir: PipelineIR
    decisions: list[DecisionRecord] = []
    lockfile: Lockfile = Lockfile()
    gate: Gate | None = None
    """The strongest gate this pipeline actually passed, or `None` if none ran. Audit A4.

    A contract can point channels at the wrong inputs and pass conformance, `nextflow
    lint`, `-preview` and `-stub-run`, because nf-core stubs never read their inputs. Only
    `--gate test` runs the tools on data. Requiring it to publish was considered and
    rejected — minutes, Docker and network per publish is too high a floor — so the bundle
    carries the evidence instead and a curator may refuse one that never ran the gate that
    checks wiring. `PipelineIR.unverified` set that precedent: state what was not checked
    rather than pretend it was.

    `None` is not a weak gate. It is no evidence at all, and must read differently from
    `lint`.
    """

    emitted: Emitted | None = None
    """The digests of the files this bundle was published from, recorded after the gate ran.

    `None` means the bundle predates the field — no evidence, exactly as `gate: None` means
    no gate ran. It must never read as "identical". Audit A28.
    """


DOORS: dict[str, type[EgressPayload]] = {
    "goal_extraction": PromptRequest,
    "tier4_resolution": AmbiguityRequest,
    "compiler_repair": RepairRequest,
    "publication": PublishBundle,
}
