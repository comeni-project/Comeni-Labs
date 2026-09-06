"""One adaptation becoming the ten sections of §5.3.

Every input is a value — no registry on disk, no network, no model — which is what makes the
composition testable at all, and what will make the golden prompts golden.
"""

import json

import pytest
from comeni_core.review import Excerpt
from mendel_forge.ai import select
from mendel_forge.ai.context import Drop, Section
from mendel_forge.ai.schemas import Proposal
from mendel_forge.catalogue import (
    BundleFact,
    CatalogueItem,
    NumberedExcerpt,
    SourceBundle,
    SourceCapabilities,
)
from mendel_forge.hole_manifest import HoleKind, ScaffoldHole


def _item(**overrides) -> CatalogueItem:
    base = {
        "id": "d" * 64,
        "source": "nf-core",
        "ref": "fastqc",
        "display_name": "fastqc",
        "content_digest": "c" * 64,
        "source_revision": "9339809",
        "capabilities": SourceCapabilities(supplies_nextflow=True),
    }
    return CatalogueItem(**{**base, **overrides})


def _excerpt(evidence_id: str, kind: str = "prose", text: str = "some documentation"):
    return NumberedExcerpt(
        id=evidence_id,
        excerpt=Excerpt(locator=f"meta.yml:{evidence_id}", text=text),
        kind=kind,
    )


def _source(**overrides) -> SourceBundle:
    base = {
        "item": _item(),
        "source_digest": "s" * 64,
        "evidence": (_excerpt("E001"), _excerpt("E002", kind="metadata")),
        "facts": (
            BundleFact(name="nf_process", value="FASTQC", evidence_id="E002"),
            BundleFact(name="arity", value=1),
        ),
    }
    return SourceBundle(**{**base, **overrides})


def _hole(hole_id: str = "consumes.reads.type_id", **overrides) -> ScaffoldHole:
    base = {
        "id": hole_id,
        "pointer": "/consumes/0/type_id",
        "kind": HoleKind.TYPE,
        "question": "the semantic type of the input the module calls reads",
        "why_open": "nf-core declares an output as type: file with a filename pattern",
        "legal_values": ("fastq.reads", "alignment.bam"),
    }
    return ScaffoldHole(**{**base, **overrides})


def _dossier(**overrides):
    base = {
        "source": _source(),
        "scaffold_holes": [_hole()],
        "registry_digest": "r" * 64,
        "schema_version": 6,
        "instruction": "answer every hole",
        "budget": 100_000,
    }
    return select.analysis_dossier(**{**base, **overrides})


def test_the_identity_section_says_which_revision_and_which_registry():
    """Two calls that disagree are two different registries — a fact the record should carry
    rather than a nondeterminism it hides, which is the argument `derive()` already makes."""
    text = select.identity(_source(), registry_digest="r" * 64).text
    assert "nf-core:fastqc" in text
    assert "9339809" in text
    assert "r" * 64 in text


def test_the_identity_section_states_what_the_source_can_prove():
    """It changes what the model is being asked to do — a source that ships Nextflow gets a
    contract bound to an existing process, and one that ships a container and prose is asked to
    author a module. A model that cannot tell which it is looking at will do the wrong one
    confidently."""
    ships = select.identity(_source(), registry_digest="r").text
    container_only = select.identity(
        _source(item=_item(capabilities=SourceCapabilities(supplies_container_digest=True))),
        registry_digest="r",
    ).text
    assert "ships a Nextflow process: True" in ships
    assert "ships a Nextflow process: False" in container_only
    assert "pins its container by digest: True" in container_only


def test_machine_readable_evidence_is_protected_and_prose_is_droppable():
    """§5.3's reduction order says *redundant prose*, and this is where that word becomes a
    decision. Made on the `kind` the adapter recorded rather than on how long the text is: a
    short `meta.yml` entry is what a port claim rests on, and a long README paragraph is
    context around it."""
    by_id = {s.key: s for s in select.evidence(_source())}
    assert by_id["E001"].drop is Drop.PROSE
    assert by_id["E002"].drop is Drop.KEPT


def test_a_fact_with_no_evidence_is_marked_derived_rather_than_left_bare():
    """`BundleFact`'s own rule, carried into the prompt. Citing a line for a value nothing was
    read from is worse than citing nothing, because a reviewer follows it and finds text that
    does not support the claim."""
    text = select.facts(_source()).text
    assert "[E002]" in text
    assert "(derived, not read)" in text


def test_every_hole_carries_its_instruction_fragment_inlined():
    """A prompt that says *see ports.state.v1* is a prompt with a dangling pointer. The
    versioning that makes the id worth having lives in the file name, not in what a model
    reads."""
    (segment,) = select.holes([_hole()])
    assert "what the data *is*" in segment.text
    assert "consumes.reads.type_id" in segment.text


def test_a_hole_says_whether_its_list_is_the_whole_vocabulary():
    """`exhaustive=False` with a ranked list is a real state — *we listed what we found* — and
    collapsing it into the closed case is how a reviewer comes to believe a suggestion is the
    only legal answer. The model reads the same distinction."""
    (closed,) = select.holes([_hole()])
    (open_,) = select.holes([_hole(exhaustive=False)])
    assert "the only legal answers" in closed.text
    assert "known so far" in open_.text


def test_a_hole_with_no_closed_vocabulary_says_so_rather_than_showing_an_empty_list():
    """A process name has no candidate set. Rendering `legal values: ` with nothing after it
    reads as a vocabulary that came back empty, which is a different and alarming claim."""
    (segment,) = select.holes([_hole("nf_process", kind=HoleKind.NEXTFLOW, legal_values=())])
    assert "no closed vocabulary" in segment.text


def test_every_hole_is_protected_from_the_budget():
    """A dropped hole is a question the model is never asked and therefore never declines. It
    comes back as a complete-looking proposal with a field missing, and `owed()` reports it as
    forgotten rather than as something the budget removed."""
    assert all(s.drop is Drop.KEPT for s in select.holes([_hole("a"), _hole("b")]))


def test_a_vocabulary_is_never_droppable():
    """This is the section `MF0400` exists for. A model shown nine of eleven legal values does
    not know it was shown nine."""
    assert select.vocabulary(name="types", values=["a", "b"]).drop is Drop.KEPT


def test_exemplars_keep_the_callers_ranking_and_are_capped_at_three():
    """§5.3: *at most three similar landed contracts, selected deterministically*. The ranking
    is `candidates.py`'s — reproducing it here would be a second implementation of a thing that
    was measured, and the two would quietly disagree."""
    ranked = [(f"contract-{n}", f"body {n}") for n in range(5)]
    segments = select.exemplars(ranked)
    assert [s.key for s in segments] == ["contract-0", "contract-1", "contract-2"]
    assert [s.rank for s in segments] == sorted((s.rank for s in segments), reverse=True)
    assert all(s.drop is Drop.EXEMPLAR for s in segments)


def test_the_caller_s_first_exemplar_is_the_last_one_dropped():
    """Otherwise *ranked* means nothing: the budget would decide, and it would decide by key
    order, which is alphabetical by contract id."""
    ranked = [("best", "b" * 400), ("worst", "w" * 400)]
    without = _dossier().manifest.used
    dossier = _dossier(landed=ranked, budget=without + 500)
    assert [o.key for o in dossier.manifest.omitted] == ["worst"]
    assert "best" in dossier.render()


def test_existing_rules_are_protected_rather_than_droppable():
    """§5.3 asks for them *so a duplicate or conflict is visible*. A model that cannot see the
    existing rule proposes it again, and the duplicate is caught only by a human who happens to
    remember — a worse failure than a missing exemplar, and a silent one."""
    (segment,) = select.existing_rules([("R01", "when reads are short, prefer hisat2")])
    assert segment.drop is Drop.KEPT


def test_the_response_schema_is_generated_from_the_shape_it_describes():
    """So a field added to the response and a field described to the model cannot drift."""
    schema = json.loads(select.response_schema(Proposal).text)
    assert "analysis" in schema["properties"]
    assert "answers" in schema["$defs"]["Analysis"]["properties"]


def test_no_docstring_reaches_the_schema_section():
    """Pydantic renders a class docstring as `description`, and the docstrings in `schemas.py`
    are written for a maintainer — they cite invariant numbers, spec files and design history.

    This is how it was found: `confidence` appears in the schema section, through `Unresolved`'s
    docstring explaining why there is no confidence field. Sending that to a provider is noise
    in the one section that must be read precisely, and it makes a docstring edit into a silent
    prompt change.
    """
    text = select.response_schema(Proposal).text
    assert "confidence" not in text
    assert "invariant" not in text
    assert "notes/specs" not in text

    # **Parsed rather than substring-matched, because a field may be *named* `description`.**
    # `VocabularyProposal.description` is what a proposed vocabulary entry means, and the name
    # is not negotiable — `scaffold.Proposal.description` is the field it becomes. The blunt
    # `'"description"' not in text` fired on that name, and the stripper it was guarding had
    # the same confusion in the other direction: it deleted the *property* along with the
    # keyword, so the field silently vanished from the schema the model is shown.
    def keywords(node: object, *, naming: bool = False) -> list[str]:
        if isinstance(node, dict):
            found = [] if naming else [k for k in node if k in ("description", "title")]
            return found + [
                key
                for name, value in node.items()
                for key in keywords(value, naming=not naming and name in select._NAME_MAPS)
            ]
        if isinstance(node, list):
            return [key for item in node for key in keywords(item)]
        return []

    schema = json.loads(text)
    assert schema, "the schema parsed to nothing; this check would assert nothing"
    assert keywords(schema) == [], "a docstring reached the schema section"
    assert "description" in schema["$defs"]["VocabularyProposal"]["properties"], (
        "a field named `description` was stripped as though it were a docstring"
    )


def test_the_task_instruction_is_the_last_thing_in_the_rendered_dossier():
    """An instruction placed before six pages of vocabulary competes with the vocabulary."""
    rendered = _dossier(instruction="THE-FINAL-INSTRUCTION").render()
    assert rendered.rstrip().endswith("THE-FINAL-INSTRUCTION")


def test_the_sections_come_out_in_the_plan_s_order():
    """Composition order is whatever was convenient to gather; rendering order is §5.3's."""
    rendered = _dossier().render()
    positions = [
        rendered.index(f"## {section.value}: ")
        for section in Section
        if f"## {section.value}: " in rendered
    ]
    assert len(positions) >= 6, "too few sections rendered for this to be a real ordering check"
    assert positions == sorted(positions)


def test_two_dossiers_over_the_same_adaptation_are_byte_identical():
    """The whole point of building this half first. A prompt that moves between two runs cannot
    be a golden file, and a review record citing its digest would be citing the machine."""
    assert _dossier().render() == _dossier().render()
    assert _dossier().manifest.prompt_digest == _dossier().manifest.prompt_digest


def test_a_dossier_that_cannot_shed_enough_refuses_rather_than_dropping_a_hole():
    """The end of §5.3's road, reached through the real composer rather than a synthetic one —
    which is the only way to know the protected classes were assigned as this module intends."""
    with pytest.raises(ValueError, match="MF0400"):
        _dossier(budget=200)
