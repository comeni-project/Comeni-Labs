"""Importing the forge must not import a model client.

**`forge fill --model` is opt-in, and this is what makes that structurally true** rather than
merely documented. CLAUDE.md says the forge's default *is* the no-AI lane; before this, every
import of `mendel_forge.ops` pulled litellm — measured at 110MB, and 152MB with its stack, of a
285MB virtualenv in the image — for a path the served API cannot execute at all.

The same argument as `--no-ai` not being a flag: a default nobody can quietly change beats a
default somebody has to remember.
"""

import subprocess
import sys


def test_importing_ops_does_not_import_a_model_client():
    """A subprocess, because `mendel_ai` is almost certainly already in this process's
    `sys.modules` from another test — asserting in-process would pass for the wrong reason."""
    code = (
        "import mendel_forge.ops, sys; "
        "print('mendel_ai' in sys.modules or 'litellm' in sys.modules)"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "False", f"the forge pulled a model client: {done.stdout}"


def test_importing_the_cli_does_not_either():
    """`forge --help` pays every import, and the CLI floor was 350ms."""
    code = (
        "import mendel_forge.cli, sys; "
        "print('mendel_ai' in sys.modules or 'litellm' in sys.modules)"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "False", f"the CLI pulled a model client: {done.stdout}"


def test_the_model_path_still_works():
    """The half that must fail otherwise: an import moved so far it broke the feature.

    `filler` IS the model path, so importing it pulling `mendel_ai` is correct — that import is
    the opt-in.
    """
    from mendel_forge.filler import ModelFiller

    assert ModelFiller is not None
