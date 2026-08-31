"""What could sit on the other end of a wire, and why that order.

**The picker's headline claim is that the reason is computed.** `n-bport`: *`producers_of`
already ranks by `(surplus, -priority, id)`, so the reason is real — SAMTOOLS_SORT is first
because it is the only producer of the state FEATURECOUNTS asks for.* These hold that sentence to
arithmetic rather than to a string somebody typed.
"""

from mendel_api.services import candidates


def test_the_order_is_the_resolvers_own():
    """`(surplus, -priority, id)` — the key `router.py` sorts by, not a second one.

    The spine's aligner choice is the case with a real tie-break: STAR and HISAT2 both produce
    `alignment.bam` with nothing surplus, and STAR wins on registry priority. A picker ordering
    alphabetically would put HISAT2 first and be wrong in a way nobody would notice.
    """
    got = candidates.producing("alignment.bam", frozenset())
    order = [row.process for row in got.candidates]

    assert order.index("STAR_ALIGN") < order.index("HISAT2_ALIGN"), (
        "STAR carries the higher registry priority and must come first"
    )
    assert order.index("HISAT2_ALIGN") < order.index("SAMTOOLS_SORT"), (
        "the sorter produces a BAM with a surplus state; surplus outranks priority"
    )
    # And the surplus term is the FIRST term, so it dominates whatever the priorities are.
    assert [row.surplus for row in got.candidates] == sorted(
        row.surplus for row in got.candidates
    )


def test_a_candidate_names_why_it_is_first():
    """The reason is composed from the numbers that produced the order.

    This is the sentence the canvas promises, and it must be arithmetic: a hand-written reason
    beside a computed order is a `why:`-less value wearing a UI costume.
    """
    got = candidates.producing("alignment.bam", frozenset({"coordinate_sorted"}))

    assert len(got.candidates) == 1
    assert got.candidates[0].process == "SAMTOOLS_SORT"
    assert got.candidates[0].why == "the only producer of alignment.bam[coordinate_sorted]"


def test_the_closest_fit_comes_first_in_both_directions():
    """**The ordering was backwards on the consuming side and the docstring said otherwise.**

    `surplus` there is how much LOOSER an input is than what you have: an input naming
    `[trimmed]` scores 0 against trimmed reads, one taking anything scores 1. Sorting descending
    put the vaguest candidate first — found by printing the real registry's answer and reading
    it, not by a test that already existed.
    """
    got = candidates.consuming("fastq.reads", frozenset({"trimmed"}))
    named = [row for row in got.candidates if "[trimmed]" in row.why]
    anything = [row for row in got.candidates if "any state" in row.why]

    assert named and anything, "the fixture stopped covering both kinds of input"
    last_named = max(got.candidates.index(row) for row in named)
    first_any = min(got.candidates.index(row) for row in anything)
    assert last_named < first_any, (
        "an input that names the states you have is a closer fit than one that takes anything"
    )


def test_the_total_is_the_registry_and_not_a_catalogue():
    """*6 of N*, where N is what actually exists to choose between.

    Issue #77: discovery reads vendored modules only, so a catalogue total would be aspirational.
    The honest denominator for a filtered list is the number of contracts the registry holds.
    """
    bams = candidates.producing("alignment.bam", frozenset())
    reports = candidates.producing("qc.report", frozenset())

    assert bams.total > len(bams.candidates), "the total is a denominator, not the page"
    assert bams.total == reports.total, (
        "the total is a property of the registry and must not change with the question asked"
    )


def test_two_contracts_sharing_a_process_name_are_two_rows():
    """`comeni/profile/fastqc` and `nf-core/fastqc` both declare the process `FASTQC`.

    They are genuinely different contracts and the picker must be able to tell them apart — which
    means a row cannot be identified by its process. Found while reading the probe output, where
    two identical-looking lines turned out to be correct.
    """
    got = candidates.consuming("fastq.reads", frozenset())
    fastqcs = [row for row in got.candidates if row.process == "FASTQC"]

    assert len(fastqcs) == 2
    assert len({row.contract_id for row in fastqcs}) == 2, "the rows must be distinguishable"


def test_nothing_here_resolves():
    """A registry query on the cached stack. The 2026-08-19 audit found every registry-touching
    screen costing ~250ms warm, and this one opens under somebody's cursor."""
    import mendel_resolver.materialise as materialise

    original = materialise.ir_of
    materialise.ir_of = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("resolved"))
    try:
        assert candidates.producing("alignment.bam", frozenset()).candidates
    finally:
        materialise.ir_of = original
