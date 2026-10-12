"""What a model quoted from a sample lives only in its reply, which retention clears (Part H
spec §5.2). A quote copied into a turn, a proposal or an observation would outlive the reply and
escape the setting that promises it goes."""

import pytest
import sqlalchemy as sa
from mendel_api.authoring.types import CharacteriseReply, StateRead
from mendel_api.db import session_scope
from mendel_api.services import session as facade
from mendel_api.stages import samples
from mendel_authoring import commands
from mendel_postgres import reachable
from test_authoring_samples import clean  # noqa: F401
from test_characterise_reading import _at, readable  # noqa: F401

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

QUOTE = "QUOTE-7f3a @HD VN:1.6 SO:coordinate"
STORES = {
    "pipeline_authoring_turn": "blocks",
    "pipeline_authoring_proposal": "payload",
    "pipeline_observation": "evidence",
    "pipeline_authoring_session": "blueprint",
    "pipeline_decision_migration": "snapshot",
}


def test_no_quote_reaches_a_turn_a_proposal_or_an_observation(clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    attempt = samples.start_reading(pid)
    reply = CharacteriseReply(type_id="alignment.bam",
                              states=[StateRead(id="coordinate_sorted", evidence=QUOTE)])
    sent = reply.model_dump(mode="json")
    assert QUOTE in str(sent), "the reply carries no quote — measuring nothing"
    answer = facade.perform(commands.ReadingAnswered(pid, attempt, sent, "ana", False)).result
    assert answer.recorded == ["alignment.bam"], "the reading was not recorded"
    with session_scope() as db:
        found = {
            table: db.scalar(sa.text(
                f"SELECT count(*) FROM {table} WHERE CAST({column} AS text) LIKE :q"),
                {"q": "%QUOTE-7f3a%"})
            for table, column in STORES.items()
        }
    assert found == dict.fromkeys(STORES, 0)
