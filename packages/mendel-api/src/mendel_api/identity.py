"""Who an answer is recorded as.

There are no accounts (spec §2), so this is attribution rather than security. It is read from
git because that is the name already attached to everything else this person has done in the
repository, and adding real auth later changes only this function's source.
"""

import subprocess

FALLBACK = "unknown"


def default_author() -> str:
    """The name in Settings (`system.author`, pinned by `COMENI_AUTHOR`), else `git config
    user.name`, else an obvious fallback.

    **Settings first** (issue 268): inside the API's container git knows no one, so every
    draft, answer and approval was recorded as `unknown`.

    Never the OS user: that is a different fact from who is curating, and it would land in
    `Provenance.drafted_by` looking like a name somebody chose.
    """
    from comeni_core.settings import catalogue

    from mendel_api.services.installation import installation

    named = installation().get(catalogue.AUTHOR)
    if isinstance(named, str) and named.strip():
        return named.strip()
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
