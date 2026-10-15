#!/usr/bin/env python3
"""Run Make recipes with Compose's dotenv semantics, without evaluating values as Make code.

Only the Compose CLI is used; loading configuration starts no services. Values stay in the
child environment. This also supplies validated non-secret settings needed while Make parses.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=", re.MULTILINE)
SETTINGS = {"WIKI_HOST_PORT", "OLLAMA_GPU", "AI_MODEL", "DOCKER_UID", "DOCKER_GID"}


def environment(root: Path, inherited=None) -> dict[str, str]:
    """Load dotenv through Compose; existing process variables retain precedence."""
    result = dict(os.environ if inherited is None else inherited)
    dotenv = root / ".env"
    if not dotenv.exists():
        return result
    names = sorted(set(KEY.findall(dotenv.read_text())))
    model = {
        "services": {
            "configuration": {
                "image": "scratch",
                "environment": {key: "${" + key + "}" for key in names},
            }
        }
    }
    try:
        run = subprocess.run(
            [
                "docker",
                "compose",
                "--project-directory",
                str(root),
                "--env-file",
                str(dotenv),
                "--project-name",
                "comeni-command-env",
                "-f",
                "-",
                "config",
                "--format",
                "json",
            ],
            input=json.dumps(model),
            env=result,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(
            "Docker Compose CLI is required to read .env for Make commands"
        ) from error
    if run.returncode:
        # Compose diagnostics may quote an invalid value; do not echo credential-bearing input.
        raise RuntimeError("Cannot read .env with Compose; check its syntax and interpolation")
    values = json.loads(run.stdout)["services"]["configuration"].get("environment", {})
    # Compose serializes literal dollar signs doubled so its output can be read as Compose again.
    result.update(
        {key: str(value).replace("$$", "$") for key, value in values.items() if value is not None}
    )
    return result


def main() -> int:
    env = environment(ROOT)
    if len(sys.argv) == 4 and sys.argv[1] == "--setting":
        name, default = sys.argv[2:]
        if name not in SETTINGS:
            raise ValueError("only public Make settings may be printed")
        value = env.get(name) or default
        if name == "WIKI_HOST_PORT":
            if not value.isdecimal() or not 1 <= int(value) <= 65535:
                raise ValueError("WIKI_HOST_PORT must be a port number")
        elif name in {"DOCKER_UID", "DOCKER_GID"}:
            if not value.isdecimal() or not 0 <= int(value) < 2**31:
                raise ValueError(f"{name} must be a numeric Unix identity")
        elif not re.fullmatch(r"[A-Za-z0-9_./:@+-]*", value):
            raise ValueError(f"{name} contains unsupported characters")
        print(value)
        return 0
    os.execvpe("/bin/sh", ["/bin/sh", *sys.argv[1:]], env)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(2) from None
