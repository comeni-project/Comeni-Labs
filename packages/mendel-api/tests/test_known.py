"""What is known about a session, gathered from the store for the prompts (Part I.0 §6.3)."""

from mendel_api.services import decisions, known
from mendel_authoring.decisions import ActorKind
from test_authoring_gathering import _gathering
from test_authoring_gathering import clean as clean


def _draft_of(sid):
    from mendel_api.db import session_scope
    from mendel_api.models import PipelineAuthoringSession

    with session_scope() as db:
        return db.get(PipelineAuthoringSession, sid).draft_id


def test_what_was_heard_is_known_with_its_words_and_what_is_open_is_listed(clean):
    sid = _gathering(["counts.matrix"])
    draft = _draft_of(sid)
    decisions.set_want(draft, "counts.matrix", who="model", actor_kind=ActorKind.MODEL,
                       heard="gene counts", heard_seq=1)
    decisions.set_fact(draft, "paired", True, who="model", actor_kind=ActorKind.MODEL,
                       heard="paired-end", heard_seq=1)
    decisions.set_asked(draft, "differential expression", who="model",
                        actor_kind=ActorKind.MODEL, heard="differential expression", heard_seq=1)
    said = known.text(sid)
    assert '- gene counts matrix · you said · "gene counts"' in said
    assert '- paired: yes · you said · "paired-end"' in said
    assert "- differential expression" in said
    assert "Still open:" in said and "sequencing reads (FASTQ)" in said
    assert "paired-end" not in said.split("Still open:")[1]
