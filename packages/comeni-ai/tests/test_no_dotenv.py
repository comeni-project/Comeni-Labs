"""Importing litellm through comeni_ai never loads a `.env` into the process (#602).

litellm runs `load_dotenv()` at import unless `LITELLM_MODE` says otherwise, so a developer's
`.env` (Wiener's token, the forge's GitHub token) reached every test after the first import, and
any service would read whatever `.env` sat in its working directory beside the settings store.
"""

import os
import subprocess
import sys


def test_importing_litellm_after_comeni_ai_reads_no_dotenv(tmp_path):
    (tmp_path / ".env").write_text("COMENI_LEAK_PROBE=from-the-dotenv\n")
    env = {k: v for k, v in os.environ.items() if k != "LITELLM_MODE"}
    script = ("import os, comeni_ai, litellm; "
              "print(os.environ.get('COMENI_LEAK_PROBE', 'absent'))")
    done = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "absent"


def test_a_mode_set_by_the_deployment_is_kept(tmp_path):
    env = {**os.environ, "LITELLM_MODE": "DEV"}
    done = subprocess.run([sys.executable, "-c", "import os, comeni_ai; "
                           "print(os.environ['LITELLM_MODE'])"],
                          cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    assert done.stdout.strip() == "DEV"
