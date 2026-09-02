"""A question a reviewer must answer, shared by the forge and the build path.

**Inert by design.** Whether an unanswered question *blocks* is not on this type and must
never be: `Scaffold` cannot assemble a contract while a hole is open, and the resolver flags
a tier-4 ambiguity and emits anyway. Putting that difference here — as a field or as an
overridden method — converts a structural guarantee into a runtime check on a value, which
is the mistake `CLAUDE.md` records about invariant 1. See the spec's §3.1.

**Closed vocabulary only.** `Ambiguity` subclasses this and projects to `AmbiguityRequest`, a
door-2 payload. A free-text field here widens door 2 without anybody editing
`tests/guards/test_egress.py`, which is the file that says *these are all the ways data leaves*.
Free text belongs on the subclasses, where the field count already tracks it.

See `docs/notes/specs/2026-08-18-the-shared-question.md`.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.spell.marks import Text

_NO_EXTRAS = ConfigDict(extra="forbid")


class Excerpt(BaseModel):
    """A span of source text and a resolvable pointer to it.

    `locator` is a `file:line` or a URL — never a bare claim. The rule drafter's §3.2
    makes the same demand of a citation for the same reason: a reviewer approving
    something is approving that the quoted text supports it, and they cannot do that
    without the text.

    **A file locator is relative to the root it was read under, never absolute.** An
    absolute one carries the machine into every draft and every golden file, which is the
    defect issue #46 found in `digest_of_directory` — and it was a golden file that caught
    it here too, on the first one written.

    **`text` is weaker than this docstring asks for, today.** The nf-core source sets one
    excerpt per fact naming the process and the file rather than quoting the line the fact
    was read from, because `ModuleSpec` records no line numbers. That is enough to find the
    evidence and not enough to read it without opening the file — a real gap, and the right
    place to close it is `ModuleSpec`, so that conformance diagnostics gain line numbers at
    the same time.

    **Moved here from the forge's `observe` module by Plan 2.5.** A build-path question that
    quotes its evidence needs the same type, and the forge is where it was first needed rather
    than where it belongs.

    (Naming that module's package in full here trips `test_no_pure_package_imports_an_impure_one`,
    which is a substring scan over the file text rather than an import analysis. The guard is
    blunt rather than wrong, and rewording is cheaper than teaching it to read Python.)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    """Frozen, because an `Excerpt` reaches door 2 through `Ambiguity.evidence` and what a
    reviewer read must be what is sent. `tests/guards/test_egress.py` demanded this the moment the
    type became reachable from a payload, which is the allowlist working as intended."""

    locator: Text
    """A `file:line` or a URL. `Text` rather than a bare `str` because it crosses a door and
    invariant 14 admits no undeclared string — it is a pointer rather than prose, but there
    is no closed vocabulary of source locations to type it against."""

    text: Text
    """The quoted span itself.

    **Free text that is quoted rather than composed**, which is a weaker claim than the other
    entries on that list: nobody writes this sentence, a source file already contains it and
    this copies it. It is still free text and still listed literally in
    `tests/guards/test_egress.py`, because the boundary is widened by editing the file that says
    *these are all the ways data leaves*.
    """


class Candidate(BaseModel):
    """One thing that may be answered, and where it comes from.

    Not `CandidateRef` — that is `egress.py`'s alias for a *reference* that crosses door 2
    (`ContractId | EdgeRef | None`). This is the offered option a reviewer reads.
    """

    model_config = _NO_EXTRAS

    value: str
    note: str = ""
    """Where this candidate is declared, so a reviewer can check it without a second lookup."""


class Question(BaseModel):
    """What is being asked, what it is about, and what may be answered."""

    model_config = _NO_EXTRAS

    subject: str
    """What is being decided.

    `Hole` spelled this `field` and `Ambiguity` spelled it `subject`; `subject` survives
    because it is already a declared mark, already in `AmbiguityRequest`, and already
    serialised into `pipeline.yml` through the decision records. Renaming the forge's side
    costs a golden file; renaming the build's side would cost an artifact.
    """

    what: str = ""
    """What the value is, in a sentence a reviewer can read."""

    why_open: str = ""
    """Why a human is being asked rather than a rule answering it."""

    candidates: list[Candidate] = Field(default_factory=list)
    """What may go here. Empty means nothing is known; see `closed` for whether the list
    binds."""

    closed: bool = True
    """Whether `candidates` is the *whole* of what is legal, or only what is suggested.

    **Not everything with candidates is a closed vocabulary, and treating it as one was a
    measured mistake.** Invariant 7 closes *vocabularies* — types, states, roles — and
    enforces that at load time. A port **name** is not one of those: `PortName` is a shape
    alias, and `ModuleContract` accepts any valid identifier. Binding a name to a list the
    forge invented is what made `multiqc`'s `reports` unreachable — a perfectly legal name
    that simply was not offered.

    So a name hole is open, with candidates as guidance, and a type or role hole is closed.
    """

    evidence: list[Excerpt] = Field(default_factory=list)
    """What the answer rests on.

    The forge carried this from its first day and the build path carried none of it, which is
    the asymmetry the spec's §7.1 is about: a tier-4 question handed a reviewer a list of
    candidates and nothing to judge them on.
    """

    def legal(self, value: Any) -> bool:
        """Is this an allowed answer?

        **A list is checked member by member.** `roles` and `produces[].state` hold
        several values from one closed set, so the candidates are the legal *members*
        rather than the legal *values* — comparing the whole list against them rejects
        `["qc_per_sample"]` while accepting `"qc_per_sample"`, which is backwards for
        the field it is guarding.

        **A candidate is a `Candidate` or a bare id, and both are legitimate.** The forge
        offers `Candidate(value=..., note=...)` so a reviewer can see where an option is
        declared. The build path re-narrows `candidates` to `list[ContractId]`,
        `list[ParamValue]` or `list[EdgeRef]` — plain declared-id strings — because door 2's
        payload types them as `CandidateRef` and A129 records that this payload accepted only
        one of the three `*Asked` types until their *values* were checked rather than their
        field names. Loosening the door to carry `Candidate` would undo that, so the shapes
        stay different and this method reads both.

        Found by `packages/mendel-resolver/tests/test_evidence.py`, which is the first thing
        ever to call `legal()` on the build path: before Plan 2.5 `Ambiguity` had no such
        method, so inheriting one that assumed the forge's shape broke it silently.
        """
        if not self.candidates or not self.closed:
            return True
        allowed = {c.value if isinstance(c, Candidate) else c for c in self.candidates}
        if isinstance(value, list | set | frozenset | tuple):
            return all(member in allowed for member in value)
        return value in allowed
