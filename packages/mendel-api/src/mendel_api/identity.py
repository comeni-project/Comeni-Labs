"""Who an answer is recorded as.

There are no accounts (spec §2), so this is attribution rather than security. It is read from
git because that is the name already attached to everything else this person has done in the
repository, and adding real auth later changes only this function's source.
"""

import subprocess

FALLBACK = "unknown"


def default_author() -> str:
    """`git config user.name`, or an obvious fallback.

    Never the OS user: that is a different fact from who is curating, and it would land in
    `Provenance.drafted_by` looking like a name somebody chose.
    """
    try:
        done = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return FALLBACK
    name = done.stdout.strip()
    return name or FALLBACK
