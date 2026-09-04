"""Re-exports of `comeni_ai`. **Nothing is implemented here.**

The package moved to `comeni-ai` on 2026-09-04, because a second consumer appeared: the Forge,
the builder and Wiener's agents would otherwise have grown three model clients, and
`MENDEL_MODEL` configuring a Wiener agent is a lie in a `.env` file.

**This shim exists for released consumers, not for this repository.** Every in-repo import has
already moved; `test_no_in_repo_module_imports_the_shim` is what keeps it that way, so a new
caller reaching for `mendel_ai` fails in the suite rather than in a year. Releases are per
package here (`docs/guides/releasing.md`), so `mendel-ai` at `0.1.0` is on a tag somebody may
have pinned, and deleting the import outright would break them with no warning.

**It is a window and it should close.** Remove this package once no released consumer pins
`mendel-ai`; the version here is bumped to `0.2.0` to carry the deprecation, and the honest
next step is a `0.3.0` that is nothing but this docstring, then deletion.

The names are the pre-rename surface exactly. `Metered`, `Usage`, `PromptTemplate`, `Turn` and
`converse` are deliberately **absent**: they did not exist under the old name, so re-exporting
them would invite new code to be written against the deprecated spelling.
"""

import warnings

from comeni_ai.access import ModelAccess
from comeni_ai.choice import WHY_LIMIT, Choice, Choices, Option, choose_many, choose_one
from comeni_ai.client import Client, ModelUnavailableError, NoModelError, Transport

warnings.warn(
    "mendel_ai is deprecated and re-exports comeni_ai; import comeni_ai instead. "
    "The environment variables moved too: COMENI_AI_MODEL, COMENI_AI_API_KEY, "
    "COMENI_AI_BASE_URL. The MENDEL_* names are read as a fallback for now.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "WHY_LIMIT",
    "Choice",
    "Choices",
    "Client",
    "ModelAccess",
    "ModelUnavailableError",
    "NoModelError",
    "Option",
    "Transport",
    "choose_many",
    "choose_one",
]
