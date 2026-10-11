"""The builder's jobs, as an action asks for them (spec §11.2): built here, queued by the facade
after the commit. `authoring_jobs` runs them; it imports their names from here."""

from mendel_api import jobs
from mendel_api.services.session import Job

ANSWER = "answer_authoring_turn"
PHRASE = "phrase_authoring_gap"
READ_BACK = "read_back_authoring_goal"
CHARACTERISE = "characterise_sample"


def turn(session_id: str, seq: int) -> Job:
    return Job(ANSWER, (session_id, seq), jobs.job_id_for("builder", "turn", session_id, str(seq)),
               jobs.AI_QUEUE)


def phrase(session_id: str, subject: str) -> Job:
    from mendel_api.stages import gathering

    stamp = gathering.phrasing_context(session_id, subject)
    if stamp is None:
        raise ValueError("this question is no longer needed")
    return Job(PHRASE, (session_id, subject, stamp.decision_revision, stamp.context_digest),
               jobs.job_id_for("builder", "phrase", session_id, subject,
                               str(stamp.decision_revision), stamp.context_digest), jobs.AI_QUEUE)


def readback(session_id: str, proposal_id: str) -> Job:
    return Job(READ_BACK, (session_id, proposal_id),
               jobs.job_id_for("builder", "readback", session_id, proposal_id), jobs.AI_QUEUE)


def characterise(session_id: str, proposal_id: str, attempt: int, excerpt, *, unqueued,
                 expires: float) -> Job:
    from mendel_api.services import characterise as ch

    return Job(
        CHARACTERISE,
        (session_id, proposal_id, attempt, ch.Sealed(excerpt.text), excerpt.binary_before),
        jobs.job_id_for("builder", "characterise", proposal_id, str(attempt)),
        jobs.AI_QUEUE,
        expires=expires,
        unqueued=unqueued,
    )
