# packages/wiener-api/tests/test_models.py
"""What Wiener persists, and what it deliberately does not."""


def test_the_tables_are_the_four_that_argued_for_themselves():
    """`docs/design/wiener.md` §7.1. `run_event` is the source of truth and everything else
    is a projection; a fifth table needs its argument written here first."""
    import wiener_api.models as m

    tables = {v.__tablename__ for v in vars(m).values() if hasattr(v, "__tablename__")}
    assert tables == {"run", "run_event", "run_task", "run_artifact", "run_intent"}, (
        f"the tables moved: {sorted(tables)}. run_event is the record and run_task and run "
        "are projections of it with a rebuild path — a table that is neither needs an "
        "argument in docs/design/wiener.md §7.1 before it exists. NOTE: `run_message` is "
        "already argued for in §7.1 and lands in W3 — widen this set in W3's plan, not here."
    )


def test_no_table_stores_a_samplesheet_s_contents():
    """The path is in the admitted `started` payload because Nextflow put it there. Nothing
    copies it into a column and nothing indexes it — §7.1."""
    import wiener_api.models as m

    forbidden = {"samplesheet", "sample_name", "input_path", "sample_id"}
    found = {
        f"{t.__tablename__}.{c.name}"
        for t in (m.Run, m.RunEventRow, m.RunTask, m.RunArtifact)
        for c in t.__table__.columns
        if c.name in forbidden
    }
    assert not found, (
        f"a table grew a column for a sample: {sorted(found)}. The samplesheet PATH reaches "
        "Wiener in the admitted `started` payload because Nextflow put it there; nothing "
        "copies it into a column of its own and nothing indexes it — docs/design/wiener.md "
        "§7.1. A column is where a thing gets queried, joined and exported."
    )
