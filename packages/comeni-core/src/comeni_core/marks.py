"""Type markers and closed value unions shared across the core.

These live apart from `ir.py`, `decision.py` and `egress.py` because all three need them
and any two of those importing each other would be a cycle. They are also the vocabulary
`tests/test_egress.py` reasons about, so keeping them in one small file makes the guard's
subject matter readable in one screen.

Every marker is a member of `Mark`, which is closed. That is what lets the egress guard ask
"is this a declared identifier?" rather than "does this carry any metadata?" — the second
question was the one it used to ask, and `Annotated[str, "clinical-notes"]` answered yes.

A bare `str` carries no marker at all, which is why the guard rejects it: a field with
nothing said about it is a field where anything fits.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator


class Mark(StrEnum):
    """Every kind of thing a declared string may be. **Closed, on purpose.**

    Markers used to be bare strings — `Annotated[str, "contract-id"]` — and the egress
    guard exempted a field from the bare-`str` rule if it carried *any* metadata at all. So
    "declared identifier" meant "somebody wrote a string here", and
    `Annotated[str, "clinical-notes"]` was as declared as `ContractId`. You could mint a new
    identifier kind by typing one.

    An enum makes `isinstance(meta, Mark)` a question with an answer, which is what lets the
    egress guard's leaf rule be an allowlist rather than another blocklist. Inverting that
    rule without closing this set first would have rebuilt the same hole one level up.

    A `StrEnum` rather than a plain `Enum` so the metadata still reads as itself in a repr;
    the `isinstance` check discriminates either way, and a bare `"contract-id"` string is
    *not* an instance of `Mark` even though it compares equal to one.

    Audit A20, and the unnumbered hole found while writing root A's spec.
    """

    CONTRACT_ID = "contract-id"
    TYPE_ID = "type-id"
    NODE_ID = "node-id"
    SUBJECT = "subject"
    PORT_NAME = "port-name"
    STATE_NAME = "state-name"
    DECISION_KEY = "decision-key"
    RESOLVER_ID = "resolver-id"
    MEASUREMENT_ID = "measurement-id"
    DIGEST = "digest"
    LAYER_NAME = "layer-name"
    CONTAINER_REF = "container-ref"
    MODULE_KEY = "module-key"

    NF_IDENTIFIER = "nf-identifier"
    """A name emitted into a Nextflow or Groovy *declaration* — a process name, a channel,
    a port. There is no escaping option for a declaration site, so an identifier is
    validated or it is not one."""

    NF_PATH = "nf-path"
    """A relative path fragment under the emitted pipeline directory."""

    GROOVY_EXPRESSION = "groovy-expression"
    """Unbounded Groovy, emitted verbatim. The designed exception, marked so that it is
    visibly the exception rather than merely being one."""

    FREE_TEXT = "free-text"
    """Text a human typed or a tool printed. Unbounded, and the thing the egress boundary
    exists to contain. Only the fields named in the guard's allowlist may carry it."""

    PARAM_LITERAL = "param-literal"
    """A scalar drawn from curated registry data rather than from a person. It can be a
    string, but not an arbitrary one — see `_reject_path_shaped` for how little that
    currently guarantees."""


_SEQUENCING_SUFFIXES = (".fastq", ".fq", ".bam", ".cram", ".vcf")


def _reject_path_shaped(value: object) -> object:
    """Refuse the values that most obviously are not registry data. A **blocklist**.

    Applied only to the fields a *person* fills in — see `HumanParamValue`. It cannot be
    applied to `ParamValue` at large: the resolver records which upstream output it wired
    as `"{node}.{port}"`, ports in the registry are named `bam`, and `"dual.bam"` is
    therefore a legitimate internal pointer that is character-for-character a filename.
    No text rule separates it from `"run.bam"`, so the choice is between rejecting real
    pipelines and letting `PT-4471023.fastq.gz` through. Neither is acceptable, and
    neither is necessary: a pointer is written by this code from registry data, never
    typed by anyone.

    **This is a stopgap and it is not a guarantee.** A blocklist enumerates what somebody
    thought of; the real fix is parameters as closed vocabulary, where a value is legal
    because a contract declared its domain rather than because no rule here objected.
    That is Plan 2 Task 11, where `Param`'s domain was deliberately left to be designed.

    It exists now because A3 is a live route into a published artifact and Plan 2 is not
    close: on the unmodified tree, with no monkeypatching, `DecisionRecord.human_override`
    accepted `/data/patients/PT-4471023/S1_R1.fastq.gz` and carried it into a
    `PublishBundle` — the door with no undo. `human_override` is the sharpest case,
    because it is by design the slot for a human's answer.

    The 2026-08-03 audit's C3 reported this and it was recorded fixed. It was fixed in
    *shape* — the open `dict[str, Any]` is gone, so arbitrary keys are impossible — and
    not in *substance*, because `Mark.PARAM_LITERAL` is a marker with no closed
    domain and the
    egress guard treats "has a label" as "has a domain". Do not record A3 as closed on the
    strength of this function.

    Deliberately narrow. A contract ID carries slashes and an `@version`, and a rule's
    `then:` is exactly that, so anything rejecting `nf-core/star/align@2.7.11b` would make
    the registry unloadable — which is why this tests for a *leading* separator, a `..`
    segment, and sequencing suffixes rather than for "looks like a path".
    """
    if not isinstance(value, str):
        return value
    if value.startswith(("/", "~")):
        raise ValueError(
            f"{value!r} starts with a path separator. A parameter is registry data, not a "
            "location on somebody's disk; Mendel does not receive file paths (invariant 15)."
        )
    if ".." in value.split("/"):
        raise ValueError(f"{value!r} contains a `..` path segment, so it is a path.")
    stem = value[: -len(".gz")] if value.lower().endswith(".gz") else value
    if stem.lower().endswith(_SEQUENCING_SUFFIXES):
        raise ValueError(
            f"{value!r} ends in a sequencing-file suffix. Profiling happens where the data "
            "is; a pipeline references `params.input`, which the lab fills at run time."
        )
    return value


def _is_identifier(value: str) -> bool:
    """`[A-Za-z_][A-Za-z0-9_]*`, without importing `re`.

    `re` is not on `comeni-core`'s purity allowlist and widening it for a character class
    would be the wrong trade — the allowlist is valuable precisely because it has no
    unknown unknowns. `str.isidentifier` is the same rule plus Unicode.

    **The ASCII test is a deliberate narrowing, not a correction.** Groovy follows Java, so
    `STAR_ÄLIGN` is a legal identifier there; this refuses it anyway. A process name is
    read by a reviewer deciding whether a pipeline does what it claims, and two names that
    render identically and are not equal is a bad property for that reading to have. No
    module in any registry needs it, so the cost is zero and the refusal is free.

    Recorded because reverting `isascii()` failed no test on the first pass, which is how a
    narrowing nobody has justified looks exactly like one nobody has tested.
    """
    return value.isascii() and value.isidentifier()


def _has_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _groovy_identifier(value: str) -> str:
    """A Groovy identifier, and nothing else.

    A34: `nf_process: "A }\nprintln 'x'"` loaded, and the emitter interpolated it into
    `process <name> {` and `include { <name> }` — so a contract could add statements to the
    generated pipeline. Conformance would have caught it, but only for a *vendored* module;
    an unverified contract was emitted on trust, which is the legitimate case for a lab's
    own module and therefore not a hole that can be closed by refusing unverified contracts.

    Validated at load, which is before conformance runs and before anything is emitted.
    """
    if not _is_identifier(value):
        raise ValueError(
            f"{value!r} is not a Nextflow identifier. Letters, digits and underscore, not "
            f"starting with a digit — it is emitted into a declaration, where there is "
            f"nothing to escape it with."
        )
    return value


def _relative_path(value: str) -> str:
    """A path fragment that stays inside the emitted directory.

    `nf_include` becomes `include { X } from './<path>'` in the generated `main.nf`. A
    leading separator or a `..` segment reaches out of the pipeline directory into whatever
    is around it on the machine that runs it.
    """
    if not value:
        raise ValueError("a path fragment cannot be empty")
    if value.startswith(("/", "~")) or _has_control_character(value):
        raise ValueError(f"{value!r} must be a relative path fragment with no control characters")
    if ".." in value.split("/"):
        raise ValueError(f"{value!r} contains a `..` segment, so it can leave the pipeline")
    return value


def _single_line(value: str) -> str:
    """Prose that reaches a generated file, on one line.

    A27: a `reason` carrying a newline was interpolated into `// <reason>` and the second
    line was Groovy. The emitter re-prefixes continuation lines as well — belt and braces,
    because the boundary must not depend on the emitter being careful and the emitter must
    not depend on its input being clean.
    """
    if _has_control_character(value):
        raise ValueError(
            f"{value!r} contains a control character. This text is written into a generated "
            f"file; free-form prose belongs in a field marked `Text`."
        )
    return value


def _type_id(value: str) -> str:
    """A type id, shaped so it is safe to emit.

    It feeds `_channel_name()`, which replaces `.` and `-` and nothing else — so a type id
    carrying a brace or a newline reaches an assignment target in the generated workflow.
    And a vocabulary type id is a *filename stem*: filenames on Linux may contain newlines,
    so "it comes from a file we control" is not a shape argument.

    Root E asks the other half of the question — whether the id names a type any layer
    declares. Both are needed and neither implies the other.
    """
    if not value:
        raise ValueError("a type id cannot be empty")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    bad = sorted(set(value) - allowed)
    if bad or not (value[0].isascii() and value[0].isalpha()):
        raise ValueError(
            f"{value!r} is not a type id. Letters, digits, dot, underscore and hyphen, "
            f"starting with a letter — it is emitted as a channel name."
        )
    return value


Text = Annotated[str, Mark.FREE_TEXT]
"""Free prose that crosses a door and is never emitted into an artifact.

Multi-line on purpose: `GateFailure.tool_message` carries Nextflow's stderr."""

Line = Annotated[str, Mark.FREE_TEXT, AfterValidator(_single_line)]
"""Free prose that reaches a generated file. **The same `Mark.FREE_TEXT`**, so root A's
`FREE_TEXT_FIELDS` allowlist and its count are unaffected: the split is by destination, not
by prose-ness."""

NfIdentifier = Annotated[str, Mark.NF_IDENTIFIER, AfterValidator(_groovy_identifier)]
NfPath = Annotated[str, Mark.NF_PATH, AfterValidator(_relative_path)]
GroovyExpression = Annotated[str, Mark.GROOVY_EXPRESSION]
"""Unbounded Groovy emitted verbatim — `entry_channel`, and nothing else.

Marked rather than validated because the whole point is that a laboratory can bring a type
the compiler has never seen and say how it arrives. Root B reports when an overlay replaces
one (A24); root C makes it the only field of this kind."""

ContractId = Annotated[str, Mark.CONTRACT_ID]
TypeId = Annotated[str, Mark.TYPE_ID, AfterValidator(_type_id)]
NodeId = Annotated[str, Mark.NODE_ID]
Subject = Annotated[str, Mark.SUBJECT]
PortName = Annotated[str, Mark.PORT_NAME]
StateName = Annotated[str, Mark.STATE_NAME]
DecisionKey = Annotated[str, Mark.DECISION_KEY]
ResolverId = Annotated[str, Mark.RESOLVER_ID]
MeasurementId = Annotated[str, Mark.MEASUREMENT_ID]

ParamValue = int | float | bool | Annotated[str, Mark.PARAM_LITERAL] | None
"""What a resolved parameter or a decision may hold.

Replaces `Any`. Nextflow parameters are scalars — there is no shape a pipeline parameter
takes that this does not cover — and `Any` in a type reachable from an egress payload means
the payload can carry anything at all, which was true until 2026-08-03.

Note what this does *not* say: `Mark.PARAM_LITERAL` is a marker, not a domain, and the
egress guard treats "has a label" as "has a domain". That is audit A3, and closing it
properly is Plan 2 Task 11, where a parameter gets a declared set of legal values.
`HumanParamValue` below is the stopgap for the fields a person can reach meanwhile.
"""

HumanParamValue = Annotated[ParamValue, AfterValidator(_reject_path_shaped)]
"""A `ParamValue` a **person** supplied, rather than one this code built from registry data.

Two fields qualify: `DecisionRecord.human_override`, which is by design the slot for a
reviewer's answer, and `Goal`'s `ParamOverride.value`, which is what someone types into a
goal file. On the unmodified tree both accepted
`/data/patients/PT-4471023/S1_R1.fastq.gz` and carried it into a `PublishBundle` — the door
with no undo. Audit A3.

Scoped to these two rather than to `ParamValue` for a reason recorded in
`_reject_path_shaped`: the resolver's own `"{node}.{port}"` pointers are indistinguishable
from filenames, and they are not a risk, because nothing human reaches them. Guarding by who
writes a field is what keeps the blocklist from having to be clever, and cleverness is what
failed the last two times a guard was written here.

**Still a blocklist, still not a guarantee.** Do not record A3 as closed on the strength of
this alias.
"""


Digest = Annotated[str, Mark.DIGEST]
"""A content digest, `sha256:<64 hex>`. Not a version: a contract can be edited without
its `@version` moving, and in a private overlay it routinely is."""

LayerName = Annotated[str, Mark.LAYER_NAME]
"""A registry layer's declared name. Never a filesystem path — a path is meaningless on
another machine and is exactly what invariant 15 keeps out of a shareable artifact."""

ContainerRef = Annotated[str, Mark.CONTAINER_REF]
"""A container image reference as a contract declares it, tag and all.

A declared ID rather than `FreeText`: this is registry data with a shape — a registry host,
a path, a tag — not prose a person wrote. It must never join `FREE_TEXT_FIELDS`, because
the two lists mean different things and the egress guard reads both literally.
"""

ModuleKey = Annotated[str, Mark.MODULE_KEY]
"""A contract ID minus its `@version`. Shadowing is decided on this, not the full ID —
a lab pinning `@1.22.0` over `@1.21.0` is a version bump, not an ambiguity."""
