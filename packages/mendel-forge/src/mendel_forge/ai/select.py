"""Turning one adaptation into the ten sections of §5.3, deterministically.

Separate from `context.py` because the two answer different questions. That module knows how a
dossier is *shaped* — the order, the reduction, the manifest — and nothing about ports; this
one knows what a Forge adaptation has to say and delegates every judgement about similarity to
`candidates.py`, which already ranks against real port names and tool names.

**Nothing here scores anything itself.** The one place that would be tempting is the exemplar
ranking, and `candidates.for_field` has done that since Plan 3D with a measured result — the
right type first in 25 of 30 holes rather than 1 of 30. A second ranker beside it would be the
pair the journal keeps warning about: two mechanisms answering one question, one of them a
decoration that quietly disagrees.

**Deterministic, in the sense the whole forge means it.** No clock, no environment, no path.
The registry a dossier was ranked against is named in the identity section rather than left
implicit, for the reason `derive()` gives: two calls that disagree are two different
registries, which is a fact to record rather than a nondeterminism to hide.
"""

import json
from collections.abc import Sequence

from mendel_forge.ai.context import Dossier, Drop, Section, Segment, compose
from mendel_forge.ai.schemas import Proposal
from mendel_forge.catalogue import SourceBundle
from mendel_forge.hole_manifest import ScaffoldHole
from mendel_forge.prompts import hint

EXEMPLARS = 3
"""§5.3: *at most three similar landed contracts*.

The same number `candidates._EXEMPLARS` uses for the same reason, and it is a coincidence worth
not merging: that one bounds how many existing users are named *beside a candidate*, this one
bounds how many whole contracts are quoted. They would diverge the first time either was tuned.
"""


def identity(source: SourceBundle, *, registry_digest: str) -> Segment:
    """Section 1: which tool, at exactly which revision, from a source with which reach.

    `capabilities` is here rather than left implicit because it changes what the model is being
    asked to do. A source that supplies Nextflow gets a contract bound to an existing process;
    one that supplies a container and prose is asked to author a module, and a model that
    cannot tell which it is looking at will do the wrong one confidently.
    """
    item = source.item
    caps = item.capabilities
    lines = [
        f"tool: {item.display_name} ({item.source}:{item.ref})",
        f"source revision: {item.source_revision or '(none recorded)'}",
        f"content digest: {item.content_digest}",
        f"fetched digest: {source.source_digest}",
        f"registry digest: {registry_digest}",
        f"latest version: {item.latest_version or '(unknown)'}",
        "",
        "what this source can prove:",
        f"  ships a Nextflow process: {caps.supplies_nextflow}",
        f"  declares ports machine-readably: {caps.supplies_structured_ports}",
        f"  pins its container by digest: {caps.supplies_container_digest}",
        f"  ships something runnable: {caps.supplies_tests}",
    ]
    if item.licence:
        lines.append(f"  licence: {', '.join(item.licence)}")
    return Segment(section=Section.IDENTITY, key="identity", text="\n".join(lines))


def evidence(source: SourceBundle) -> list[Segment]:
    """Section 2: every excerpt, addressed by the id assigned when it was fetched.

    **Machine-readable evidence is protected and prose is droppable.** A `meta.yml` entry is the
    thing a port claim rests on; a paragraph of README is context around it. §5.3's reduction
    order says *redundant prose* and this is where that word becomes a decision, so it is made
    on the `kind` the adapter recorded rather than on the length of the text.
    """
    segments = []
    for numbered in source.evidence:
        prose = numbered.kind == "prose"
        segments.append(
            Segment(
                section=Section.EVIDENCE,
                key=numbered.id,
                text=(
                    f"[{numbered.kind}] {numbered.excerpt.locator}\n{numbered.excerpt.text}"
                ),
                drop=Drop.PROSE if prose else Drop.KEPT,
                rank=0 if prose else 1,
            )
        )
    return segments


def facts(source: SourceBundle) -> Segment:
    """Section 3: what was read, and what it was read from.

    One segment rather than one per fact, because a fact without its neighbours is unreadable —
    an arity means nothing beside a process name it cannot see. **A fact with no evidence id is
    marked derived**, which is `BundleFact`'s own rule: citing a line for a value nothing was
    read from is worse than citing nothing, because a reviewer follows it and finds text that
    does not support the claim.
    """
    lines = []
    for fact in sorted(source.facts, key=lambda f: f.name):
        where = fact.evidence_id or "(derived, not read)"
        lines.append(f"{fact.name} = {fact.value!r}   [{where}]")
    return Segment(
        section=Section.FACTS,
        key="facts",
        text="\n".join(lines) or "(the adapter read nothing)",
    )


def holes(scaffold_holes: Sequence[ScaffoldHole]) -> list[Segment]:
    """Section 4: the questions, each with the instruction fragment it names.

    **One segment per hole, and every one protected.** A dropped hole is a question the model is
    never asked and therefore never declines — it comes back as a complete-looking proposal with
    a field missing, and `owed()` reports it as forgotten. `MF0400` refusing is the honest end
    of that road.

    The fragment is inlined rather than referenced. A prompt that says *see ports.state.v1* is a
    prompt with a dangling pointer, and the versioning that makes the id worth having lives in
    the file name rather than in the text a model reads.
    """
    segments = []
    for hole in scaffold_holes:
        lines = [
            f"id: {hole.id}",
            f"asks: {hole.question}",
            f"open because: {hole.why_open}",
            f"required: {hole.required}",
        ]
        # **How many, said before which.** A model given a list of legal values and no
        # statement of arity reads it as *pick one* — which is right for a type id and wrong
        # for `roles`, and on 2026-09-06 it was the difference between an answer and a skip.
        lines.append(
            "answer with: a list of values"
            if hole.multiple
            else "answer with: a single value"
        )
        if hole.legal_values:
            closed = "these are the only legal answers" if hole.exhaustive else "known so far"
            lines.append(f"legal values ({closed}): {', '.join(hole.legal_values)}")
        elif hole.exhaustive:
            lines.append("legal values: none enumerated — this field has no closed vocabulary")
        if hole.evidence_ids:
            lines.append(f"related evidence: {', '.join(hole.evidence_ids)}")
        lines.append("")
        lines.append(hint(hole.hint).body.strip())
        segments.append(
            Segment(section=Section.HOLES, key=hole.id, text="\n".join(lines))
        )
    return segments


def registry_version(schema_version: int) -> Segment:
    """Section 5. One line, and it is protected: a proposal is validated against the schema
    that is current, and a model told nothing about it will propose the shape it saw most of
    during training."""
    return Segment(
        section=Section.REGISTRY_VERSION,
        key="registry-version",
        text=f"registry schema version: {schema_version}",
    )


def vocabulary(*, name: str, values: Sequence[str], note: str = "") -> Segment:
    """Section 6, once per vocabulary — roles, types, states, measurements, parameter routes.

    Protected without exception. This is §5.3's *legal values*, and the argument for `MF0400`
    is exactly about this section: a model shown nine of eleven does not know it was shown
    nine, and the answer it gives passes every schema check on the way back.
    """
    body = ", ".join(values) or "(none declared)"
    return Segment(
        section=Section.VOCABULARY,
        key=name,
        text=f"{note}\n{body}" if note else body,
    )


def exemplars(landed: Sequence[tuple[str, str]]) -> list[Segment]:
    """Section 7: at most three contracts that already do something similar.

    `landed` is `(contract id, rendered text)`, **already ranked by the caller** — the ranking
    is `candidates.py`'s and reproducing it here would be a second implementation of a measured
    thing. Rank descends with position, so the caller's first is the last to be dropped.
    """
    return [
        Segment(
            section=Section.EXEMPLARS,
            key=contract_id,
            text=text,
            drop=Drop.EXEMPLAR,
            rank=len(landed) - position,
        )
        for position, (contract_id, text) in enumerate(landed[:EXEMPLARS])
    ]


def existing_rules(rules: Sequence[tuple[str, str]]) -> list[Segment]:
    """Section 8: rules already declared for the roles this tool might take.

    §5.3 asks for these *so a duplicate or conflict is visible*, which is why they are protected
    rather than droppable: a model that cannot see the existing rule proposes it again, and the
    duplicate is only caught by a human who happens to remember. That is a worse failure than a
    missing exemplar, and it is silent.
    """
    return [
        Segment(section=Section.EXISTING_RULES, key=rule_id, text=text)
        for rule_id, text in rules
    ]


def _structure_only(node: object) -> object:
    """Strip `description` and `title` from a JSON schema, recursively.

    **Pydantic renders a class docstring as `description`**, and the docstrings in
    `schemas.py` are written for a maintainer: they cite invariant numbers, spec files, other
    modules, and the history of why a field is shaped as it is. None of that helps a model
    produce the right shape, all of it is noise in the section that has to be read most
    precisely, and it would be sent to a provider on every call.

    Found by a test asserting the word `confidence` never reaches the schema section — it was
    arriving through `Unresolved`'s docstring, which explains *why* there is no confidence
    field. The shape says what is legal; the prompt says what it means. Keeping the two
    separate is also what stops a docstring edit from silently changing a prompt.
    """
    if isinstance(node, dict):
        return {
            key: _structure_only(value)
            for key, value in node.items()
            if key not in ("description", "title")
        }
    if isinstance(node, list):
        return [_structure_only(item) for item in node]
    return node


def response_schema(shape: type) -> Segment:
    """Section 9. Generated from the Pydantic model rather than written out, so a field added
    to the response and a field described to the model cannot drift — and `extra="forbid"`
    means the shape is also the enforcement."""
    return Segment(
        section=Section.RESPONSE_SCHEMA,
        key="response-schema",
        text=json.dumps(_structure_only(shape.model_json_schema()), indent=2, sort_keys=True),
    )


def task(instruction: str) -> Segment:
    """Section 10, last. An instruction placed before six pages of vocabulary competes with the
    vocabulary; placed after it, it is the last thing read."""
    return Segment(section=Section.TASK, key="task", text=instruction)


def analysis_dossier(
    source: SourceBundle,
    scaffold_holes: Sequence[ScaffoldHole],
    *,
    registry_digest: str,
    schema_version: int,
    vocabularies: Sequence[Segment] = (),
    landed: Sequence[tuple[str, str]] = (),
    rules: Sequence[tuple[str, str]] = (),
    instruction: str,
    budget: int,
) -> Dossier:
    """The ten sections for `forge.analysis.v1`, composed and reduced.

    Every argument is a value. This function reaches no registry and no network of its own —
    the caller loads the layers, ranks the exemplars and hands the results in, which is what
    keeps it testable without a registry on disk and what makes the golden prompts golden.
    """
    return compose(
        [
            identity(source, registry_digest=registry_digest),
            *evidence(source),
            facts(source),
            *holes(scaffold_holes),
            registry_version(schema_version),
            *vocabularies,
            *exemplars(landed),
            *existing_rules(rules),
            response_schema(Proposal),
            task(instruction),
        ],
        budget=budget,
    )
