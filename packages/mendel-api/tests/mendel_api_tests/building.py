"""The database fixture the builder's tests share."""

from typing import NamedTuple

import pytest
from mendel_api.db import session_scope

from mendel_api_tests.database import truncate

HISAT2 = "nf-core/hisat2/align@2.2.2"


@pytest.fixture
def clean():
    """Every table a builder session and its draft touch, in one statement — `clean_invocations`'s
    reason, extended. Each foreign key here is `RESTRICT`."""
    tables = ("ai_invocation, pipeline_authoring_turn, pipeline_authoring_session, "
              "pipeline_draft, gate_run")
    with session_scope() as session:
        session.execute(truncate(f"TRUNCATE TABLE {tables}"))
    yield


class Case(NamedTuple):
    session_id: str
    draft_id: str


@pytest.fixture
def authoring_case(clean) -> Case:
    """A conversation whose pipeline is built: the example goal recorded and resolved, a turn
    said and answered, as the agent's loop leaves one."""
    from comeni_core.plan.draft import DraftGraph
    from mendel_api.agent import direct, loop
    from mendel_api.services import decisions, drafts
    from mendel_resolver.goal import Goal
    from support.example import example_mapping

    draft_id = drafts.create(DraftGraph(), "rnaseq", "ana")
    session_id = loop.start_session(draft_id, who="ana")
    decisions.import_goal(draft_id, Goal.model_validate(example_mapping()), who="ana")
    direct._rebuild(session_id, draft_id, "ana")
    loop.add_person_turn(session_id, "gene counts from my reads")
    return Case(session_id, draft_id)
