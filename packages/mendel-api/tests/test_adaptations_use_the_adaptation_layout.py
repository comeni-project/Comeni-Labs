"""An adaptation is never read through the CLI draft's loader.

**Two layouts live in one workspace, and mixing them shipped four times.** `save`/`load` write
`<root>/<name>/draft.json` for the `forge draft` CLI, which names its own drafts; an adaptation
lives at `<root>/forge/<id>/` beside its bundle and its stored source. They look
interchangeable — both take a string, both return a `Draft` — and they are not.

Every one of the four failed a layer away from the mistake, and none was visible to a test:

- `candidate()` answered 404 for every real adaptation
- `_generate` failed the first generation that ever reached the AI worker
- `answer_forge_review_message` would have failed the first review chat
- `publish_forge_adaptation` would have failed the first landing

They were found one at a time by driving the loop, each after fixing the last — which is what a
scan is for. `mendel_forge.ops` is exempt because it *is* the CLI path and correctly passes
`req.name`, a draft the user named.
"""

import ast
import inspect

import pytest
from mendel_api.services import forge_candidate, forge_jobs

MODULES = (forge_jobs, forge_candidate)

CLI_ONLY = ("load", "save")
"""The workspace verbs that address a draft by the name a person gave it.

`read_draft` and `write_draft` are the adaptation-addressed pair, and an adaptation id is never
a name a person gave anything.
"""


def _calls(module) -> list[tuple[str, str]]:
    """Every `<something>.<verb>(<first argument>)` in the module, as `(verb, first argument)`."""
    tree = ast.parse(inspect.getsource(module))
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        first = node.args[0] if node.args else None
        name = (
            first.id
            if isinstance(first, ast.Name)
            else ast.dump(first)
            if first is not None
            else ""
        )
        found.append((node.func.attr, name))
    return found


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__)
def test_no_adaptation_is_read_through_the_cli_draft_loader(module):
    """`workspace.load(adaptation_id)` cannot find a scaffolded adaptation and never could."""
    offenders = [
        (verb, argument)
        for verb, argument in _calls(module)
        if verb in CLI_ONLY and "adaptation_id" in argument
    ]
    assert not offenders, (
        f"{module.__name__} reaches an adaptation through {offenders}; "
        "`load`/`save` are the CLI layout at the workspace root, and an adaptation lives at "
        "forge/<id>/ — use read_draft/write_draft"
    )


def test_the_scan_can_see_the_calls_it_is_scanning():
    """**A scan over an empty list passes.** `tests/README.md` names this exactly, and this file
    is a loop over derived data, so the collection is asserted non-empty first."""
    for module in MODULES:
        verbs = {verb for verb, _ in _calls(module)}
        assert verbs, f"parsed no calls at all out of {module.__name__}"
    assert "read_draft" in {verb for verb, _ in _calls(forge_jobs)}, (
        "forge_jobs no longer reads a draft; this scan would pass on a module that stopped "
        "doing the thing it is about"
    )
