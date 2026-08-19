"""Who an answer is recorded as.

No accounts (spec §2), so this is ATTRIBUTION and not security: it says who to write on the
value, and a user can override it. What it must never do is guess silently — an answer
recorded as the wrong person is worse than one that asked.
"""

from unittest.mock import patch

from mendel_api.identity import default_author


def test_it_reads_the_git_author():
    with patch("subprocess.run") as run:
        run.return_value.stdout = "Rafael Correia\n"
        run.return_value.returncode = 0
        assert default_author() == "Rafael Correia"


def test_it_falls_back_to_a_name_that_is_obviously_a_fallback():
    """`unknown` rather than `""` or the OS user: a blank `by` would land in
    Provenance.drafted_by looking like a value somebody chose, and the OS user is a
    different fact from who is curating."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert default_author() == "unknown"


def test_a_configured_but_empty_name_is_also_the_fallback():
    with patch("subprocess.run") as run:
        run.return_value.stdout = "\n"
        run.return_value.returncode = 0
        assert default_author() == "unknown"
