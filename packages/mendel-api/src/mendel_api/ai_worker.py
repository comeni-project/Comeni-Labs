"""The worker that is allowed to call a provider, and nothing else.

**A separate process rather than a second function list, and the reason is starvation.** A model
call takes minutes; a gate or a sweep must not wait behind one on a shared concurrency budget.
Two queues means the slow thing cannot block the fast one, and it costs one container.

**Concurrency one by default.** A local Ollama serves one request at a time and a second
concurrent call makes both slower rather than either faster; a hosted provider has a rate limit
that a worker cannot see. `MENDEL_AI_MAX_JOBS` is there for the operator who knows their own
limit.
"""

from arq.connections import RedisSettings
from arq.worker import func

from mendel_api.jobs import AI_QUEUE
from mendel_api.services import authoring_jobs
from mendel_api.settings import settings


class AIWorkerSettings:
    """The AI lane. **Its function list is the allowlist of what may reach a provider.**

    Nothing here is shared with `WorkerSettings`: a job on both lists could be enqueued to
    either queue, and which one it landed on would depend on the caller rather than on what the
    job does. `test_ai_worker.py` holds the two lists disjoint.
    """

    functions = [
        # The builder's model calls. Answering a turn crosses door 1. Resolving a blueprint and
        # accepting a step make none and are not on this list.
        # A message waiting behind another's reply retries until that reply is written (#392).
        func(authoring_jobs.answer_authoring_turn,
             max_tries=authoring_jobs.tries_in_line(settings.ai_job_timeout_seconds)),
        authoring_jobs.phrase_authoring_gap,
        authoring_jobs.read_back_authoring_goal,
        # The characteriser (14.7.7) crosses door 6 carrying part of a person's file. **It keeps
        # no result**: ARQ stores a job's arguments with its result, and the excerpt must leave
        # Redis when the job does.
        func(authoring_jobs.characterise_sample, keep_result=0),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    queue_name = AI_QUEUE
    max_jobs = settings.ai_max_jobs
    job_timeout = settings.ai_job_timeout_seconds
    """A hard ceiling on one job, in seconds; ARQ cancels the coroutine when it passes."""
