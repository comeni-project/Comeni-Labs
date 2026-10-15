"""Select isolated databases before pytest imports application settings or test modules.

Loaded through pyproject.toml for repository and package-only test runs. Explicit
MENDEL_TEST_DATABASE_URL and WIENER_TEST_DATABASE_URL support other isolated servers.
"""

import os

from support.databases import configure

configure(os.environ)
