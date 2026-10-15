"""The Python builder receives every workspace package and its build metadata.

Replay its COPY instructions through Docker so coverage follows actual context filtering,
including directory copies, rather than requiring a hand-maintained COPY per package.
"""

import shutil
import subprocess
import tomllib

import pytest
from support.paths import ROOT

pytestmark = pytest.mark.slow


def _members():
    return {p.name for p in (ROOT / "packages").iterdir() if (p / "pyproject.toml").is_file()}


@pytest.fixture(scope="module")
def builder_inputs(tmp_path_factory):
    if shutil.which("docker") is None:
        pytest.skip("Docker is unavailable")
    temporary = tmp_path_factory.mktemp("builder-inputs")
    instructions = []
    builder = False
    for line in (ROOT / "Dockerfile").read_text().splitlines():
        if line.startswith("FROM "):
            builder = line.endswith(" AS builder")
        elif builder and line.startswith("COPY "):
            instructions.append(line)
    assert instructions, "no builder COPY instructions were found"
    dockerfile = temporary / "Probe.Dockerfile"
    dockerfile.write_text("FROM scratch\nWORKDIR /app\n" + "\n".join(instructions) + "\n")
    output = temporary / "output"
    result = subprocess.run(
        [
            "docker",
            "buildx",
            "build",
            "--network=none",
            "-f",
            str(dockerfile),
            "--output",
            f"type=local,dest={output}",
            str(ROOT),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return output / "app"


def test_every_workspace_member_reaches_the_image(builder_inputs):
    missing = [
        name
        for name in _members()
        if not (builder_inputs / "packages" / name / "pyproject.toml").is_file()
    ]
    assert missing == []


def test_the_dockerfile_names_no_package_that_does_not_exist(builder_inputs):
    copied = {p.parent.name for p in (builder_inputs / "packages").glob("*/pyproject.toml")}
    assert copied == _members()


def test_the_scan_found_something(builder_inputs):
    assert _members()
    assert (builder_inputs / "pyproject.toml").is_file()
    assert (builder_inputs / "uv.lock").is_file()


def test_a_package_that_needs_its_readme_gets_it(builder_inputs):
    for name in _members():
        source = ROOT / "packages" / name
        copied = builder_inputs / "packages" / name
        metadata = tomllib.loads((source / "pyproject.toml").read_text())["project"]
        readme = metadata.get("readme")
        filename = readme.get("file") if isinstance(readme, dict) else readme
        if filename:
            assert (copied / filename).read_bytes() == (source / filename).read_bytes(), name
        for pattern in metadata.get("license-files", []):
            licences = list(source.glob(pattern))
            assert licences, (name, pattern)
            for licence in licences:
                assert (copied / licence.relative_to(source)).read_bytes() == licence.read_bytes()
