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
    ANY_KEY = "any-key"
    PORT_NAME = "port-name"
    STATE_NAME = "state-name"
    DECISION_KEY = "decision-key"
    RESOLVER_ID = "resolver-id"
    MEASUREMENT_ID = "measurement-id"
    DIGEST = "digest"
    LAYER_NAME = "layer-name"
    TEST_DATA_REF = "test-data-ref"
    CONTAINER_REF = "container-ref"
    MODULE_KEY = "module-key"
    ROLE_NAME = "role-name"
    SPDX_ID = "spdx-id"
    CHANNEL_NAME = "channel-name"

    NF_IDENTIFIER = "nf-identifier"
    """A name emitted into a Nextflow or Groovy *declaration* — a process name, a channel,
    a port. There is no escaping option for a declaration site, so an identifier is
    validated or it is not one."""

    NF_PATH = "nf-path"

    NF_TEMPLATE = "nf-template"
    """A flag fragment carrying exactly one Mendel substitution, `{value}`.

    Distinct from GROOVY_EXPRESSION: an entry channel is unbounded Groovy by design,
    while a template is a fragment whose only variable part is a value this code
    substitutes. Two interpolation systems meet in one string and they are not the
    same kind of risk."""
    """A relative path fragment under the emitted pipeline directory."""

    EDGE_REF = "edge-ref"
    """`<node>.<port>` — which upstream output feeds a consumer's port. A declared shape,
    not an unlucky filename: `dual.bam` is legal *because* both halves are identifiers, and
    `run.cram` is refused because `run` names no node. That is what let A3's blocklist stop
    guessing."""

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
    the publication payload — the door with no undo. `human_override` is the sharpest case,
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


def _role_name(value: str) -> str:
    """`snake_case`, non-empty, no leading digit. A key a person types in two places."""
    ok = (
        value
        and not value[0].isdigit()
        and not value.startswith("_")
        and not value.endswith("_")
        and all(c.islower() or c.isdigit() or c == "_" for c in value)
    )
    if not ok:
        raise ValueError(
            f"{value!r} is not a role name. Roles are lower-case words joined by "
            f"underscores, e.g. `ribo_depletion`."
        )
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

def _edge_ref(value: str) -> str:
    """`<node>.<port>`, both Groovy identifiers.

    The resolver writes these when it records which output it wired. They were bare
    `ParamValue`s indistinguishable from filenames, which is the exact reason
    `_reject_path_shaped` had to be scoped to human-written fields rather than applied to
    `chosen`. A16.
    """
    # Shape alone cannot separate this from a filename, and saying so is the point: the
    # spec predicted `run.cram` would be refused and it is not — `run` and `cram` are both
    # identifiers, exactly as `dual` and `bam` are. What the shape *does* refuse is every
    # filename with a second dot or a hyphen — `S1_R1.fastq.gz`, `PT-4471023.bam` — and
    # what closes the rest is that a source decision is checked against the candidate set,
    # which is built from the pipeline's own nodes. A16's gain is that the *kinds* no
    # longer share a field, not that a string became self-describing.
    node, separator, port = value.partition(".")
    if not separator or not _is_identifier(node) or not _is_identifier(port):
        raise ValueError(
            f"{value!r} is not an edge reference. It names an upstream output as "
            f"`<node>.<port>`, both Nextflow identifiers."
        )
    return value


def _contract_id(value: str) -> str:
    """`<owner>/<name…>@<version>` — what a contract file declares as its `id`.

    A `ProducerDecision.chosen` is one of these, so giving the alias a shape is what makes
    that type say something. `module_key()` splits on the `@` and shadowing is decided on
    the part before it; an id with no `@` would make every contract its own module key.
    """
    owner, separator, version = value.rpartition("@")
    if not separator or not version or "/" not in owner:
        raise ValueError(
            f"{value!r} is not a contract id. They are `<owner>/<name>@<version>` — the "
            f"part before the `@` is the module key that shadowing is decided on."
        )
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/")
    if set(owner) - allowed or set(version) - (allowed - {"/"}):
        raise ValueError(f"{value!r} is not a contract id: unexpected characters")
    return value


_VALUE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789" "_.:+-"
)
"""The characters `{value}` may carry, spelled out rather than compiled.

`re` is not on `comeni-core`'s purity allowlist and `_is_identifier` already refused to widen
it for a character class, for the reason given there: the allowlist is valuable precisely
because it has no unknown unknowns. This is the same trade and gets the same answer.
"""


_TEMPLATE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " _.:+-/=,'"
)
"""What a template's fixed text may contain, once `{value}` and `${meta.x}`/`${task.x}` are
removed. A superset of `_VALUE_CHARS` — a template needs spaces, single quotes and `:`, which a
resolved value does not — but it still excludes `"`, a backtick, `;`, `|`, `&`, `<`, `>`, `#`
and a bare `$`, because a template is composed into a shell command line and, when it carries an
interpolation, into a double-quoted Groovy closure. Spelled out rather than a regex: `re` is off
`comeni-core`'s purity allowlist.
"""


def _nf_template(value: str) -> str:
    """A flag fragment with Mendel and Groovy substitutions, and nothing else executable.

    Two interpolation systems meet in one string and only one of them is ours:

    - `{value}` is **Mendel's**, substituted at emit time. The only one this code touches.
    - `${…}` is **Groovy's**, evaluated by Nextflow per task and passed through verbatim.

    A template mentioning `${…}` is emitted as a *closure* rather than a string — measured on
    Nextflow 25.10.4, where `ext.args = "--rg ID:${meta.id}"` fails at config parse with
    `Unknown config attribute process.withName:FOO.meta.id`, because a config GString is
    evaluated when the config is read and no task exists then. The closure form resolves.

    **A45.** Only newlines used to be refused, so the fixed text around `{value}` was an open
    door: a `${…}` body was arbitrary Groovy in that closure, and shell metacharacters
    (`; touch x #`) reached the tool's command line verbatim. Now every `${…}` must be a single
    `meta.<id>` or `task.<id>` reference, and the rest of the text is a closed character class.
    One line only: a newline would end the command rather than the flag.
    """
    # Imported inside the call: `diagnostics` imports `Line` and `Text` from this
    # module, so a module-level import here is the cycle this file's docstring exists
    # to warn about. By the time a validator runs, both modules are loaded.
    from comeni_core.diagnostics import coded

    if "\n" in value:
        raise ValueError(
            coded("MD0204", "a template is one line — it composes into an argument string")
        )
    residue: list[str] = []
    i = 0
    while i < len(value):
        if value.startswith("${", i):
            end = value.find("}", i)
            if end == -1:
                raise ValueError(coded("MD0204", f"unterminated ${{ in template {value!r}"))
            head, _, tail = value[i + 2 : end].partition(".")
            if head not in ("meta", "task") or not _is_identifier(tail):
                raise ValueError(
                    coded("MD0204", f"${{{value[i + 2 : end]}}} is not an allowed interpolation. A "
                    "template may reference only ${meta.<id>} or ${task.<id>}; anything else is "
                    "arbitrary Groovy reaching the generated config.")
                )
            i = end + 1
        elif value.startswith("{value}", i):
            i += len("{value}")
        else:
            residue.append(value[i])
            i += 1
    bad = sorted(set(residue) - _TEMPLATE_CHARS)
    if bad:
        raise ValueError(
            coded("MD0204", f"a template may not contain {bad[0]!r}. The text around {{value}} is "
            "composed into a shell command line; letters, digits, spaces, single quotes and "
            "`_ . : + - / = ,` are allowed, and `{value}`, `${meta.x}`, `${task.x}` interpolate.")
        )
    return value


def substitutable(value: object) -> bool:
    """Whether `{value}` may carry this value.

    **Refuse rather than escape.** Escaping-for-context is where injection bugs live, and a value
    that cannot contain a quote cannot close one. The substituted result lands in a shell command
    line, so a quote, dollar, backtick, semicolon or newline is the whole reason this exists.

    The class is deliberately narrow on a **stated assumption**: that almost no tool setting needs
    a space or a slash. That assumption has not met a real counterexample, which is why `MD0201`'s
    message asks the person who finds one to report it. Loosening later is backward-compatible —
    every file that validated still validates — while tightening is not, so it starts strict.
    """
    if isinstance(value, bool | int | float):
        return True
    return isinstance(value, str) and all(char in _VALUE_CHARS for char in value)


NfIdentifier = Annotated[str, Mark.NF_IDENTIFIER, AfterValidator(_groovy_identifier)]
EdgeRef = Annotated[str, Mark.EDGE_REF, AfterValidator(_edge_ref)]
NfPath = Annotated[str, Mark.NF_PATH, AfterValidator(_relative_path)]
NfTemplate = Annotated[str, Mark.NF_TEMPLATE, AfterValidator(_nf_template)]
GroovyExpression = Annotated[str, Mark.GROOVY_EXPRESSION]
"""Unbounded Groovy emitted verbatim — `entry_channel`, and nothing else.

Marked rather than validated because the whole point is that a laboratory can bring a type
the compiler has never seen and say how it arrives. Root B reports when an overlay replaces
one (A24); root C makes it the only field of this kind."""



def _identifier(what: str):
    """A validator refusing anything that is not a bare snake-case identifier.

    A64, issue #28. Nine aliases were `Annotated[str, Mark.X]` with **no** `AfterValidator`,
    so invariant 14's *"a declared ID alias or marked `Mark.FREE_TEXT`"* meant, for those
    nine, "a `str` with a label". On the unmodified tree a reviewer crossed door 2 with a
    patient identifier as a `node_id` and clinical notes with an embedded newline as a
    `state`, and door 4 with `digest='not-a-digest: PT-4471023'`.

    Every one of these is derived from the registry — a process name lowercased, a port name
    a contract declared, a state a vocabulary lists — so the shape is free: nothing this
    repository writes has ever had a space in it. That is what makes the check costless in
    the way `ctypes`' ban is, and unlike a check somebody would have to disable.
    """

    def check(value: str) -> str:
        if not value:
            raise ValueError(f"a {what} cannot be empty")
        if not value.replace("_", "").isalnum() or not value[0].isalpha():
            raise ValueError(
                f"{value!r} is not a {what}: it must start with a letter and hold only "
                f"letters, digits and underscores. A payload string that is not a declared "
                f"shape is how a patient identifier crosses a door (A64)."
            )
        return value

    return check


def _joined_identifier(what: str, separators: str = ".:"):
    """The same, permitting identifier segments joined by declared separators.

    A `Subject` is `producer:alignment.bam`, `source:reads`, or a bare parameter name — three
    shapes `decision.py`'s own module docstring writes out — and a `DecisionKey` is
    `<node>.<subject>`, so it carries both. The separators are the whole of the permission: a
    key may hold a colon because the code puts one there, and may not hold a space because
    nothing does.
    """
    segment = _identifier(what)

    def check(value: str) -> str:
        # Split by hand rather than with `re`. The first draft normalised the separators to
        # `"\n"` and split on that, so an actual newline in the value read as a separator and
        # `"a\nb"` passed the check written to refuse it — caught by the probe, which is the
        # argument for writing the probe first. `re.split` fixes that and is not on
        # `comeni-core`'s purity allowlist; widening the allowlist for a two-line loop is a
        # worse trade than the loop.
        part = ""
        for character in value:
            if character in separators:
                segment(part)
                part = ""
            else:
                part += character
        segment(part)
        return value

    return check


def _slashed(what: str):
    """A registry key: `nf-core/star/align`. Slashes and hyphens, no spaces, no newlines."""

    def check(value: str) -> str:
        if not value:
            raise ValueError(f"a {what} cannot be empty")
        allowed = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
        )
        bad = sorted(set(value) - allowed)
        if bad:
            raise ValueError(
                f"{value!r} is not a {what}: it may not contain {', '.join(map(repr, bad))}"
            )
        return value

    return check


def _digest(value: str) -> str:
    """`sha256:` and sixty-four hex characters, and nothing else.

    The one alias where the shape is fully determined, so there is no judgement in it —
    which is why it was worth having and why its absence was worth finding. `Emitted` is the
    self-verification evidence and `EmittedFile.digest` is what a reader checks a file
    against; a digest field holding prose is a check that cannot fail.
    """
    prefix, _, body = value.partition(":")
    if prefix != "sha256" or len(body) != 64 or any(c not in "0123456789abcdef" for c in body):
        raise ValueError(
            f"{value!r} is not a digest: it must be `sha256:` followed by 64 lowercase hex "
            f"characters"
        )
    return value


ContractId = Annotated[str, Mark.CONTRACT_ID, AfterValidator(_contract_id)]
TypeId = Annotated[str, Mark.TYPE_ID, AfterValidator(_type_id)]
NodeId = Annotated[str, Mark.NODE_ID, AfterValidator(_identifier("node id"))]
Subject = Annotated[str, Mark.SUBJECT, AfterValidator(_joined_identifier("subject"))]
PortName = Annotated[str, Mark.PORT_NAME, AfterValidator(_identifier("port name"))]
StateName = Annotated[str, Mark.STATE_NAME, AfterValidator(_identifier("state name"))]
DecisionKey = Annotated[
    str, Mark.DECISION_KEY, AfterValidator(_joined_identifier("decision key"))
]
ResolverId = Annotated[str, Mark.RESOLVER_ID, AfterValidator(_single_line)]
"""Who answered a tier-4 question — `flag-only`, `replay`, `human`, or a model adapter's
own name. Single-line, because it is supplied by whatever implements the port (an impure
package, in Plan 2) and lands in a publish bundle and in `mendel build`'s output."""
MeasurementId = Annotated[str, Mark.MEASUREMENT_ID, AfterValidator(_identifier("measurement id"))]

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
`/data/patients/PT-4471023/S1_R1.fastq.gz` and carried it through door 4 — the door
with no undo. Audit A3.

Scoped to these two rather than to `ParamValue` for a reason recorded in
`_reject_path_shaped`: the resolver's own `"{node}.{port}"` pointers are indistinguishable
from filenames, and they are not a risk, because nothing human reaches them. Guarding by who
writes a field is what keeps the blocklist from having to be clever, and cleverness is what
failed the last two times a guard was written here.

**Still a blocklist, still not a guarantee.** Do not record A3 as closed on the strength of
this alias.
"""


Digest = Annotated[str, Mark.DIGEST, AfterValidator(_digest)]
"""A content digest, `sha256:<64 hex>`. Not a version: a contract can be edited without
its `@version` moving, and in a private overlay it routinely is."""

_TEST_DATA_FORBIDDEN = frozenset("\"'`${}\\ \t\n\r")
"""Characters that never belong in a reference and are the way into the generated config.

Spelled out rather than a regex, for the reason `_VALUE_CHARS` gives: `re` is off
`comeni-core`'s purity allowlist. This is the injection surface — a quote or backtick starts a
new Groovy expression, `$` and `${}` interpolate, whitespace splits — and a URL or object-store
reference contains none of them.
"""


def _test_data_ref(value: str) -> str:
    """A reference to a small public example dataset, safe to emit into the `test` profile.

    A44: `test_data` is rendered as `params.<type> = <value>`, which is Groovy. It reached that
    line unescaped, so a crafted value executed at `nextflow config` time. The emitter now
    escapes it (`_render_literal`); this is the second gate, refusing the injection surface at
    load. The URL *scheme* is deliberately not dictated — a laboratory may host its example
    anywhere — so only the metacharacters are refused, not the shape.
    """
    # Imported inside the call: `diagnostics` imports `Line` and `Text` from this
    # module, so a module-level import here is the cycle this file's docstring exists
    # to warn about. By the time a validator runs, both modules are loaded.
    from comeni_core.diagnostics import coded

    bad = sorted(_TEST_DATA_FORBIDDEN & set(value)) or [c for c in value if ord(c) < 32]
    if bad:
        raise ValueError(
            coded("MD0217", f"test_data {value!r} contains {bad[0]!r}, which would inject into the "
            "generated config. A reference is a URL pinned to a commit; remove quotes, "
            "backticks, `$`, braces and whitespace.")
        )
    return value


TestDataRef = Annotated[str, Mark.TEST_DATA_REF, AfterValidator(_test_data_ref)]
"""Where a small public example of a type lives, for the `test` profile.

A URL pinned to a commit, declared in the vocabulary. Never a laboratory's own path: this
reaches a published artifact, and a dataset that moves is one you cannot compare a result
against next year — a path on somebody's machine is both of those problems at once.

Validated for the **injection surface only** (`_test_data_ref`), not the URL shape. A44 showed
the premise that this "never reaches a shell" was false — it is emitted into Groovy — so the
metacharacters that make that an injection are refused. The scheme is still the laboratory's to
choose, because the vocabulary is where it says how a type it brought arrives.
"""

LayerName = Annotated[str, Mark.LAYER_NAME, AfterValidator(_slashed("layer name"))]
"""A registry layer's declared name. Never a filesystem path — a path is meaningless on
another machine and is exactly what invariant 15 keeps out of a shareable artifact."""

ContainerRef = Annotated[str, Mark.CONTAINER_REF]
"""A container image reference as a contract declares it, tag and all.

A declared ID rather than `FreeText`: this is registry data with a shape — a registry host,
a path, a tag — not prose a person wrote. It must never join `FREE_TEXT_FIELDS`, because
the two lists mean different things and the egress guard reads both literally.
"""

ModuleKey = Annotated[str, Mark.MODULE_KEY, AfterValidator(_slashed("module key"))]

def _spdx_id(value: str) -> str:
    """One SPDX licence identifier — `MIT`, `Apache-2.0`, `GPL-3.0-or-later`.

    An identifier, deliberately **not** an SPDX licence *expression*. `MIT OR Apache-2.0` and
    `Apache-2.0 WITH LLVM-exception` are legal SPDX and are refused here, because the field
    they sit on points at `LICENSES/<id>.txt` — one file per licence, the REUSE convention —
    and an expression names no single file. A module needing an expression is a module needing
    a decision from a person, which is the right place for it.

    That also keeps the shape narrow enough to refuse prose, which is the reason every alias
    in this module has a validator (A64).
    """
    if not value:
        raise ValueError("a licence identifier cannot be empty")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.+-")
    bad = sorted(set(value) - allowed)
    if bad:
        raise ValueError(
            f"{value!r} is not an SPDX licence identifier: it may not contain "
            f"{', '.join(map(repr, bad))}. An SPDX *expression* — `MIT OR Apache-2.0` — is "
            f"refused on purpose; `LICENSES/<id>.txt` names one file."
        )
    return value


SpdxId = Annotated[str, Mark.SPDX_ID, AfterValidator(_spdx_id)]

ChannelName = Annotated[str, Mark.CHANNEL_NAME, AfterValidator(_identifier("channel name"))]
"""What a pipeline calls one of the things it takes in.

**Its own alias rather than `TypeId`, and that is the whole of Plan 5B.** `StepInput.channel` was
a `TypeId`, so a channel's identity *was* its type — two `annotation.gtf` inputs were one
`params.gtf` and a GTF could not vary per sample. A name is what makes two channels of one type
addressable.

**And its own alias rather than `NfIdentifier`**, which it is emitted as. That one means *a name
going into a Groovy declaration, where there is no escaping option*; this one means *a key
another field references*. They validate identically today and they are answers to different
questions, which is the distinction `EdgeRef` already draws between `<node>.<port>` and a
filename that happens to have a dot in it.
"""
"""The licence a vendored module arrives under, as an SPDX identifier.

Registry data with a shape rather than prose: it is the pointer from a `module.yml` to the
`LICENSES/<id>.txt` the registry ships, so a laboratory receiving a layer can tell what it may
do with the code in it without opening 1,600 near-identical NOTICE files.
"""


RoleName = Annotated[str, Mark.ROLE_NAME, AfterValidator(_role_name)]
"""The job a contract does, and the only thing a tier-3 rule may target.

Validated rather than merely marked, unlike the nine aliases A64 names: a role reaches a
rule's `decides:` key, a diagnostic message and `pipeline.yml`, and it is authored by hand
in a layer a lab controls. `snake_case` because it is a key a person types into YAML twice —
once in the vocabulary and once on the contract — and a role that differs by a hyphen from
the one it meant is a rule that silently targets nothing."""
"""A contract ID minus its `@version`. Shadowing is decided on this, not the full ID —
a lab pinning `@1.22.0` over `@1.21.0` is a version bump, not an ambiguity."""


def _any_key(value: str) -> str:
    """A key of *some* declared kind, whichever kind that is.

    `Displacement` records what an overlay replaced across every `DeclaredKind`, so its keys
    are contract ids, decision keys, measurement ids and vocabulary type ids at once — five
    shapes, one field. It has now borrowed two aliases and been broken by both: it was
    `ContractId` until root C gave that a validator and it started refusing the synthetic keys
    `test_layered.py` stacks, and it became `Subject` — which A64 has just given a validator
    of its own, refusing `nf-core/samtools/sort@1.21.0`.

    **Twice is the argument for its own alias.** What is actually true of every key is the
    minimum: no whitespace, no control character, not empty. That refuses a patient identifier
    and clinical notes — which is what invariant 14 asks of a declared shape — and refuses
    nothing any kind legitimately keys on.
    """
    if not value:
        raise ValueError("a key cannot be empty")
    if any(character.isspace() or ord(character) < 32 for character in value):
        raise ValueError(
            f"{value!r} is not a key: it may not contain whitespace or control characters. "
            f"A payload string that is not a declared shape is how clinical notes cross a "
            f"door (A64)."
        )
    return value


AnyKey = Annotated[str, Mark.ANY_KEY, AfterValidator(_any_key)]
"""A key of whichever `DeclaredKind` a record is about. See `_any_key`."""


LABEL_ONLY: frozenset[str] = frozenset({"Text", "GroovyExpression", "ContainerRef"})
"""Declared ID aliases that carry a `Mark` and no validator, each because somebody decided so.

`test_every_mark_carries_a_validator_or_is_listed_as_a_label` is what keeps it honest. A64
(issue #28) was **nine** aliases sitting here implicitly: invariant 14 promises every payload
string is *"a declared ID alias or marked `Mark.FREE_TEXT`"*, and for those nine the first
half meant "a `str` with a label". A reviewer crossed door 2 with a patient identifier as a
`node_id` and clinical notes with a newline as a `state`, on the unmodified tree.

The three that remain are each a decision:

- **`Text`** is `Mark.FREE_TEXT` and multi-line by definition — it is the marked half of
  invariant 14's sentence, not the declared half, and validating it would be validating prose.
- **`GroovyExpression`** is a channel expression the compiler emits verbatim. It cannot be
  shape-checked without parsing Groovy, and `MD0201`'s injection class plus `MD0211`'s
  params-versus-expression check are what guard it instead — both of which read the
  *expression*, which is the right level.
- **`ContainerRef`** is an OCI reference: registry host, path, tag or digest, with rules this
  repository does not own. A partial validator would refuse a legal reference somebody needs,
  which is `_computed_over`'s `paired-end` lesson.

Each of the three is guarded somewhere other than its shape, which is what makes leaving them
a decision rather than a gap. A fourth arriving without one fails this test.
"""
