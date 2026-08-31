"""What an exit code SAYS, and nothing about what it MEANS.

A process killed by signal *n* exits `128 + n` — a convention, not a judgement, and the whole
of what this module knows. `137` is `SIGKILL`.

**It stops there deliberately.** *The OOM killer did it* is the sentence everybody wants next,
and it is an inference: `SIGKILL` is also what a scheduler preemption, a `kill -9` and a
cgroup limit look like. §18.1 says nothing explains a failure until W3, and a gloss that
crossed into a cause would be that explanation arriving early, unlabelled, and right often
enough to be trusted when it is wrong.
"""

# The signals a task in this system actually dies of. Deliberately short: a table copied out of
# `signal(7)` would offer `SIGWINCH` for `156` and imply somebody had thought about it.
_NAMES = {
    1: "SIGHUP", 2: "SIGINT", 6: "SIGABRT", 9: "SIGKILL",
    11: "SIGSEGV", 13: "SIGPIPE", 15: "SIGTERM", 24: "SIGXCPU", 25: "SIGXFSZ",
}


def signal_of(exit_code: int | None) -> str | None:
    """`SIGKILL` for 137. `None` for an ordinary exit, and `None` for a code with no name.

    Absent rather than `"signal 43"`, because a made-up name reads as knowledge.
    """
    if exit_code is None or not 128 < exit_code < 128 + 64:
        return None
    return _NAMES.get(exit_code - 128)
