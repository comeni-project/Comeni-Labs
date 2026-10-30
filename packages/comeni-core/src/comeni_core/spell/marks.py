"""Closed string markers and validators shared across the core.

Public aliases combine a :class:`Mark` with any grammar required at the boundary where the
value is used. Egress guards can therefore distinguish declared identifiers, bounded samples,
free text, and deliberately unbounded expressions without accepting arbitrary annotation
metadata. A bare ``str`` has no declared boundary meaning and is rejected by those guards.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator


class Mark(StrEnum):
    """Every recognized semantic kind for a declared string.

    The enum is intentionally closed so guards can use ``isinstance(metadata, Mark)`` as an
    allowlist. ``StrEnum`` keeps annotations readable while preventing arbitrary strings from
    becoming recognized markers.
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
    PIECE_REF = "piece-ref"
    """An inspector piece and version, such as ``fastq@1.0.0``."""
    LAYER_NAME = "layer-name"
    REPO_URL = "repo-url"
    """A network location from which a registry layer can be fetched."""
    REPO_PATH = "repo-path"
    """Where in its repository a layer sits, e.g. `registry/`: inside the repository, never a
    path on a machine."""
    COMMIT_SHA = "commit-sha"
    """A git commit in full: which state of that repository a layer was."""
    RELEASE_TAG = "release-tag"
    """A registry release: which published state of a layer it was built with."""
    TEST_DATA_REF = "test-data-ref"
    CONTAINER_REF = "container-ref"
    MODULE_KEY = "module-key"
    ROLE_NAME = "role-name"
    DIAGNOSTIC_CODE = "diagnostic-code"
    SPDX_ID = "spdx-id"

    CHANNEL_NAME = "channel-name"
    """A derived pipeline channel name, distinct from its carried type and Groovy spelling."""

    SOCKET_KEY = "socket-key"
    """`<node>.<port>` — one end of one wire, on a **draft**.

    Distinct from `DECISION_KEY`, which is `<node>.<subject>` and names something that was
    decided. This names a place on a drawing: the socket a person can put a label on. It is
    not a `NodeId`, and that is the whole point of it — a label should survive its node being
    dragged and not survive its port being rewired, which is a property only a key naming
    both can have.
    """

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
    """``<node>.<port>`` identifying the upstream output feeding an input."""

    GROOVY_EXPRESSION = "groovy-expression"
    """Unbounded Groovy, emitted verbatim. The designed exception, marked so that it is
    visibly the exception rather than merely being one."""

    FREE_TEXT = "free-text"
    """Text a human typed or a tool printed. Unbounded, and the thing the egress boundary
    exists to contain. Only the fields named in the guard's allowlist may carry it."""
    SAMPLE = "sample"
    """**Data from a person's file.** The start of a sample, decoded to text, for the
    characteriser (14.7.7). Not `FREE_TEXT`: nobody typed it, and it is the one thing this
    system holds that came from inside someone's data. Bounded by its type (`SampleText`), and
    reachable from door 6 only (`tests/guards/test_egress.py`)."""

    OPTION_ID = "option-id"
    """One answer a person may pick, addressed by id rather than by value.

    The living pipeline's whole shape: the engine offers a closed set and the browser — or a
    model — posts back **an id from that set and nothing else**, which is what makes "a model
    cannot produce a value outside the candidate set" a property rather than a hope. An
    identifier, so it can carry neither prose nor a path."""

    PARAM_LITERAL = "param-literal"
    """A scalar drawn from curated registry data rather than from a person. It can be a
    string, but not an arbitrary one — see `_reject_path_shaped` for how little that
    currently guarantees."""


_SEQUENCING_SUFFIXES = (".fastq", ".fq", ".bam", ".cram", ".vcf")


def _reject_path_shaped(value: object) -> object:
    """Reject obvious filesystem and sequencing-file values supplied by a person.

    This deliberately narrow blocklist applies only to :data:`HumanParamValue`. Resolver-made
    values may legitimately resemble filenames, so general :data:`ParamValue` instances cannot
    use this check. A closed parameter vocabulary would provide a stronger guarantee.
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
    """Require an ASCII Groovy identifier before it reaches a declaration site."""
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
    """Require prose destined for a generated file to remain on one line."""
    if _has_control_character(value):
        raise ValueError(
            f"{value!r} contains a control character. This text is written into a generated "
            f"file; free-form prose belongs in a field marked `Text`."
        )
    return value


def _type_id(value: str) -> str:
    """Require a type identifier that can safely become a channel and filename stem."""
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
"""Free prose that reaches a generated file and therefore must be single-line."""

EXCERPT_BYTES = 8 * 1024
"""Maximum UTF-8 byte length of a sample excerpt shown to a model."""
EXCERPT_LINES = 200
"""…and in lines, whichever comes first."""


def _sample_text(value: str) -> str:
    """At most `EXCERPT_BYTES` and `EXCERPT_LINES`. **A bound, not a shape**: what a sample says
    is not this code's to check, but how much of it may leave is."""
    if len(value.encode()) > EXCERPT_BYTES:
        raise ValueError(f"an excerpt is at most {EXCERPT_BYTES} bytes")
    # Match the excerpt cutter: only `\n` separates lines. `splitlines()` would also treat
    # Unicode separators as boundaries and reject excerpts the cutter retained.
    lines = value.count("\n") + (1 if value and not value.endswith("\n") else 0)
    if lines > EXCERPT_LINES:
        raise ValueError(f"an excerpt is at most {EXCERPT_LINES} lines")
    return value


SampleText = Annotated[str, Mark.SAMPLE, AfterValidator(_sample_text)]
"""A bounded excerpt from the start of a sample."""

def _edge_ref(value: str) -> str:
    """`<node>.<port>`, both Groovy identifiers.

    The resolver writes these when it records which output it wired. They were bare
    `ParamValue`s indistinguishable from filenames, which is the exact reason
    `_reject_path_shaped` is scoped to human-written fields rather than applied to `chosen`.
    """
    # Shape alone cannot distinguish this from a filename. Candidate validation supplies the
    # context by checking the reference against the pipeline's own nodes and ports.
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

    Every `${…}` must be a single `meta.<id>` or `task.<id>` reference, and the rest of the
    text belongs to a closed character class. A newline is refused because it would end the
    command rather than the flag.
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
the compiler has never seen and declare how it arrives. Overlay provenance records replacements,
and the egress guard restricts this marker to its intended field."""



def _identifier(what: str):
    """Build a validator for a non-empty alphanumeric-or-underscore identifier."""

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
        # Split by hand because `re` is intentionally absent from comeni-core's import allowlist.
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


_PIECE_CHARACTERS = set("abcdefghijklmnopqrstuvwxyz0123456789_")


def _piece_ref(value: str) -> str:
    """`<piece>@<major>.<minor>.<patch>` — an inspector piece, as a fact records it.

    By string methods rather than a pattern: `re` is not on `comeni-core`'s import allowlist.
    The id half is capped at 64, as a piece's id is, and each version part at nine digits.
    """
    piece, separator, version = value.partition("@")
    parts = version.split(".")
    if (
        not separator
        or not piece
        or not set(piece) <= _PIECE_CHARACTERS
        or len(piece) > 64
        or len(parts) != 3
        or not all(part.isascii() and part.isdigit() and len(part) <= 9 for part in parts)
    ):
        raise ValueError(
            f"{value!r} is not a piece ref. They are `<piece>@<version>`, e.g. `fastq@1.0.0`."
        )
    return value


PieceRef = Annotated[str, Mark.PIECE_REF, AfterValidator(_piece_ref)]
ContractId = Annotated[str, Mark.CONTRACT_ID, AfterValidator(_contract_id)]
TypeId = Annotated[str, Mark.TYPE_ID, AfterValidator(_type_id)]
NodeId = Annotated[str, Mark.NODE_ID, AfterValidator(_identifier("node id"))]
Subject = Annotated[str, Mark.SUBJECT, AfterValidator(_joined_identifier("subject"))]
PortName = Annotated[str, Mark.PORT_NAME, AfterValidator(_identifier("port name"))]
StateName = Annotated[str, Mark.STATE_NAME, AfterValidator(_identifier("state name"))]
OptionId = Annotated[str, Mark.OPTION_ID, AfterValidator(_identifier("option id"))]
DecisionKey = Annotated[
    str, Mark.DECISION_KEY, AfterValidator(_joined_identifier("decision key"))
]
ChannelName = Annotated[
    str, Mark.CHANNEL_NAME, AfterValidator(_identifier("channel name"))
]
"""A plain identifier: it is spelled into Groovy as `ch_<name>` and read from
`params.<param>`, and a declaration site has no escaping option."""
SocketKey = Annotated[
    str, Mark.SOCKET_KEY, AfterValidator(_joined_identifier("socket key", "."))
]
"""`<node>.<port>`, and a dot is the only separator it permits.

Narrower than `DecisionKey`, which also allows `:` because a `Subject` carries one. A socket
key never does, so permitting it would be permission granted for nothing.
"""
ResolverId = Annotated[str, Mark.RESOLVER_ID, AfterValidator(_single_line)]
"""Who answered a tier-4 question — `flag-only`, `replay`, `human`, or a model adapter's
own name. Single-line because it lands in a publish bundle and in `mendel build` output."""
MeasurementId = Annotated[str, Mark.MEASUREMENT_ID, AfterValidator(_identifier("measurement id"))]

ParamValue = int | float | bool | Annotated[str, Mark.PARAM_LITERAL] | None
"""What a resolved parameter or a decision may hold.

Nextflow parameters are scalars. `Mark.PARAM_LITERAL` identifies string literals but does not
define a closed value domain; `HumanParamValue` adds a narrow path-shaped-value guard for fields
that a person can reach.
"""

HumanParamValue = Annotated[ParamValue, AfterValidator(_reject_path_shaped)]
"""A `ParamValue` a **person** supplied, rather than one this code built from registry data.

Used by reviewer overrides and goal-file parameter overrides. It is intentionally not applied
to resolver-created edge references, which may legitimately resemble filenames. This remains a
blocklist rather than a closed parameter domain.
"""



def _diagnostic_code(value: str) -> str:
    """Two uppercase letters and four digits — `MD0105`, `MA0001`, `MI0200`.

    **This alias exists so a door can carry what validation said without carrying what a tool
    printed.** `GateFailure` already learned that lesson once: Nextflow's stderr names work
    directories and input filenames, so `ErrorCategory` is a closed vocabulary and the output
    itself stays on the machine that produced it. A diagnostic code is the same trade one level
    up — it is the whole of what a reader needs to look something up, and it cannot hold a path.

    Not checked against `diagnostics.yml` here. This module is `comeni_core.spell` and the
    registry lives in `comeni_core.diagnostics`; importing it would make every marked string
    pay for the registry, and `coded()` is already the one place a code becomes text.
    """
    if len(value) != 6 or not value[:2].isupper() or not value[:2].isalpha():
        raise ValueError(
            f"{value!r} is not a diagnostic code. Two uppercase letters then four digits, "
            "as `mendel explain` accepts them — a field that takes prose is a field a tool's "
            "stderr fits in."
        )
    if not value[2:].isdigit():
        raise ValueError(f"{value!r} is not a diagnostic code: {value[2:]!r} is not four digits")
    return value


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

    `test_data` is rendered into generated Groovy. The emitter escapes it and this validator
    independently refuses interpolation and command metacharacters. The URL scheme remains a
    laboratory choice, so the validator constrains the injection surface rather than URL shape.
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


DiagnosticCode = Annotated[str, Mark.DIAGNOSTIC_CODE, AfterValidator(_diagnostic_code)]
"""A refusal, as the code a runbook cites and `mendel explain` resolves.

Carried instead of a message wherever a payload has to say *what validation found* — see
`_diagnostic_code` for why that is the whole point rather than a compression."""


TestDataRef = Annotated[str, Mark.TEST_DATA_REF, AfterValidator(_test_data_ref)]
"""Where a small public example of a type lives, for the `test` profile.

A URL pinned to a commit, declared in the vocabulary. Never a laboratory's own path: this
reaches a published artifact, and a dataset that moves is one you cannot compare a result
against next year — a path on somebody's machine is both of those problems at once.

Validated for the injection surface only, not URL shape. The scheme is the laboratory's choice;
quotes, interpolation syntax, control characters, and whitespace are refused before emission.
"""

LayerName = Annotated[str, Mark.LAYER_NAME, AfterValidator(_slashed("layer name"))]
"""A registry layer's declared name. Never a filesystem path — a path is meaningless on
another machine and does not belong in a shareable artifact."""

_HEX = frozenset("0123456789abcdef")


def _release_tag(value: str) -> str:
    parts = value.removeprefix("v").split(".")
    if not value.startswith("v") or len(parts) != 3 or \
            not all(part.isascii() and part.isdigit() for part in parts):
        raise ValueError(f"{value!r} is not a release tag: vMAJOR.MINOR.PATCH")
    return value


def _commit_sha(value: str) -> str:
    # Forty for a SHA-1 repository, sixty-four for a SHA-256 one: git's two object formats.
    if len(value) not in (40, 64) or not set(value) <= _HEX:
        raise ValueError(f"{value!r} is not a full commit: 40 or 64 lowercase hex digits")
    return value


def _repo_url(value: str) -> str:
    """A network location with no credentials. A path or `file://` is somebody's machine, which
    a shared file must not carry (as `LayerName` keeps paths out), and a password or token in
    the URL must never reach it."""
    if any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError(f"{value!r} is not a repository URL: it contains whitespace")
    if "?" in value or "#" in value:
        # A query or fragment is where a token rides (`?private_token=…`); a clone needs neither.
        raise ValueError("a repository URL must not carry a query or fragment")
    scheme, found, rest = value.partition("://")
    if found:
        host, _, path = rest.partition("/")
        user, at, _host = host.rpartition("@")
        if scheme not in ("https", "http", "ssh", "git") or not path or not _host:
            raise ValueError(f"{value!r} is not a network repository URL")
        if at and (scheme != "ssh" or ":" in user):
            raise ValueError("a repository URL must not carry credentials")
        return value
    # The scp form git uses: `git@host:owner/repo`.
    head, colon, path = value.partition(":")
    user, at, host = head.rpartition("@")
    if not (colon and at and user and host and path) or "/" in head:
        raise ValueError(f"{value!r} is not a network repository URL; a local path is not one")
    return value


RepoUrl = Annotated[str, Mark.REPO_URL, AfterValidator(_repo_url)]
"""Where a layer's repository is fetched from: `https://…`, `ssh://…` or `git@host:path`.
No password or token, and never a local path."""

RepoPath = Annotated[str, Mark.REPO_PATH, AfterValidator(_relative_path)]
"""A layer's folder inside its repository (`git rev-parse --show-prefix`), relative and
staying inside it. Absent when the layer is the repository's top folder."""

CommitSha = Annotated[str, Mark.COMMIT_SHA, AfterValidator(_commit_sha)]
"""A git commit in full (40 hex digits, or 64 in a SHA-256 repository): one state, no other."""

ReleaseTag = Annotated[str, Mark.RELEASE_TAG, AfterValidator(_release_tag)]
"""A registry release as it is tagged (`v0.5.0`)."""

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

    The narrow shape also prevents prose from occupying an identifier field.
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
"""The licence a vendored module arrives under, as an SPDX identifier.

Registry data with a shape rather than prose: it is the pointer from a `module.yml` to the
`LICENSES/<id>.txt` the registry ships, so a laboratory receiving a layer can tell what it may
do with the code in it without opening 1,600 near-identical NOTICE files.
"""


RoleName = Annotated[str, Mark.ROLE_NAME, AfterValidator(_role_name)]
"""The job a contract does, and the only thing a tier-3 rule may target.

Roles use `snake_case` because authors repeat the key in vocabulary and contract YAML; a stable
grammar prevents visually similar spellings from silently targeting different roles."""
"""A contract ID minus its `@version`. Shadowing is decided on this, not the full ID —
a lab pinning `@1.22.0` over `@1.21.0` is a version bump, not an ambiguity."""


def _any_key(value: str) -> str:
    """A key of *some* declared kind, whichever kind that is.

    `Displacement` records keys from every `DeclaredKind`, so no single kind-specific grammar
    applies. Their common contract is only non-empty text without whitespace or control
    characters.
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

`test_every_mark_carries_a_validator_or_is_listed_as_a_label` keeps this exception set explicit.

The three that remain are each a decision:

- **`Text`** is multi-line prose, so shape validation would contradict its purpose.
- **`GroovyExpression`** is guarded by its owning field and compiler checks; partial parsing here
  would present a false guarantee.
- **`ContainerRef`** is an OCI reference: registry host, path, tag or digest, with rules this
  repository does not own. A partial validator would reject legal external syntax.

Each of the three is guarded somewhere other than its shape, which is what makes leaving them
a decision rather than a gap. A fourth arriving without one fails this test.
"""
