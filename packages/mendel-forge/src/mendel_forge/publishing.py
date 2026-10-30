"""A proven draft on its way to `comeni-registry` (forge MVP 5, spec §2–3).

`place` puts it in the registry's own layout, `check` holds it to the registry's own checks, and
`describe` writes the pull request's record. Nothing here reaches GitHub: `RegistryPublisher` is
what does, and only the forge's publish service holds one.

A draft **adds**: its tool's folder is replaced, and anything outside it must be new or identical.
A shared file it would change is refused with its path, not overwritten.
"""

import contextlib
import filecmp
import io
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml
from comeni_core.diagnostics import coded
from mendel_compiler import conformance, registry_lint
from mendel_compiler.cli import layer_verbs
from mendel_resolver import layers
from pydantic import BaseModel, ConfigDict


GITHUB_API = "https://api.github.com"


class PublishUnavailable(Exception):
    """GitHub could not be reached or refused. The message is safe to show a person."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolFacts(_Frozen):
    """What a new tool's `tool.yml` says, from the catalogue."""

    id: str
    name: str
    description: str
    homepage: str | None = None


class Change(_Frozen):
    branch: str
    title: str
    body: str
    author: str


class PullRequest(_Frozen):
    number: int
    url: str
    branch: str


class PullRequestState(_Frozen):
    state: str
    """`open`, `merged` or `closed`."""
    head: str
    checks: str
    """`green`, `pending` or `red`."""
    says: str | None = None


class RegistryPublisher(Protocol):
    def checkout(self) -> Path:
        """A clean working copy of `main`."""
        ...

    def open_pull_request(self, change: Change) -> PullRequest:
        """Commit the working copy to `change.branch`, push it and open the pull request."""
        ...

    def state(self, number: int) -> PullRequestState:
        ...

    def merge(self, number: int, head: str) -> None:
        """Merge exactly `head`: the commit whose checks were read."""
        ...

    def close(self, number: int) -> None:
        ...


def checks_of(runs: list[dict]) -> tuple[str, str | None]:
    """All of them, read as one: none yet is pending, not green."""
    if not runs:
        return "pending", "registry CI has not started"
    unfinished = [r["name"] for r in runs if r["status"] != "completed"]
    failed = [r["name"] for r in runs
              if r["status"] == "completed" and r["conclusion"] not in ("success", "skipped")]
    if failed:
        return "red", f"failed: {', '.join(sorted(failed))}"
    if unfinished:
        return "pending", f"still running: {', '.join(sorted(unfinished))}"
    return "green", None


def tool_id(module_id: str) -> str:
    """`nf-core/star/align` → `nf-core/star`: a tool holds its subtools."""
    return "/".join(module_id.split("/")[:2])


_REPLACED = ("module", "tests")


def place(draft: Path, checkout: Path, module_id: str, tool: ToolFacts) -> list[Path]:
    """Copy `draft` into `checkout` in the registry's layout. `ValueError` with `MF0517` for a
    shared file it would change."""
    source, target = draft / "tools" / module_id, checkout / "tools" / module_id
    for folder in _REPLACED:
        shutil.rmtree(target / folder, ignore_errors=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    placed = sorted(p for p in target.rglob("*") if p.is_file())
    for path in sorted(p for p in draft.rglob("*") if p.is_file()):
        relative = path.relative_to(draft)
        if relative == Path("registry.yml") or path.is_relative_to(source):
            continue
        if relative == Path("vocabulary/roles/forge.yml"):
            placed += _roles(path, checkout)
        else:
            placed += _shared(path, checkout / relative, relative)
    placed += _tool_yml(checkout, tool)
    return placed


def _shared(source: Path, target: Path, relative: Path) -> list[Path]:
    if target.exists():
        if filecmp.cmp(source, target, shallow=False):
            return []
        raise ValueError(coded("MF0517", f"the draft would change a shared file, {relative}: "
                               "change that file by hand in comeni-registry"))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, target)
    return [target]


def _roles(path: Path, checkout: Path) -> list[Path]:
    placed = []
    for role in yaml.safe_load(path.read_text())["roles"]:
        target = checkout / "vocabulary" / "roles" / f"{role}.yml"
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(yaml.safe_dump({"declares": "role", "roles": [role]}))
            placed.append(target)
    return placed


def _tool_yml(checkout: Path, tool: ToolFacts) -> list[Path]:
    target = checkout / "tools" / tool.id / "tool.yml"
    if target.exists():
        return []
    facts = tool.model_dump(exclude_none=True)
    target.write_text(yaml.safe_dump({"declares": "tool", **facts}, sort_keys=False))
    return [target]


def fragment(checkout: Path, module_id: str, version: str, summary: str) -> Path:
    """One changelog fragment per pull request, collected into the release notes."""
    path = checkout / "changelog.d" / f"{module_id.replace('/', '-')}.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text(f"- `{module_id}@{version}`: {summary}\n")
    return path


def check(checkout: Path) -> list[str]:
    """The registry's CI, run here: what it would refuse, in its words. Empty means it passes.
    Writes each tool's generated page, which a pull request must carry."""
    try:
        stack = layers.load([checkout])
    except ValueError as error:
        return [str(error)]
    found = [f"{d.code} {d.where}: {d.summary}"
             for d in conformance.check(stack.registry, stack.modules, stack.measurements)
             if d.code != "MD0100"]
    with contextlib.redirect_stdout(io.StringIO()) as printed:
        if layer_verbs._docs_verb([checkout], None, False, in_place=True) != 0:
            found.append(f"the tool pages could not be written: {printed.getvalue()}")
    return [*found, *(f"{d.code} {d.where}: {d.summary}" for d in registry_lint.lint(checkout))]


@dataclass(frozen=True)
class Decided:
    item: str
    drafted_by: str
    decided_by: str


@dataclass(frozen=True)
class Record:
    module_id: str
    version: str
    digest: str
    opened_by: str
    decided: list[Decided] = field(default_factory=list)
    tests: list[tuple[str, str]] = field(default_factory=list)


def describe(record: Record) -> str:
    """The pull request's description: a record, written by the engine, so it stays exact."""
    decisions = "\n".join(f"| `{d.item}` | {d.drafted_by} | {d.decided_by} |"
                          for d in sorted(record.decided, key=lambda d: d.item))
    runs = "\n".join(f"- `{name}`: Wiener run `{run}`" for name, run in record.tests)
    return f"""Adds `{record.module_id}@{record.version}`, forged in Comeni.

## Decisions

| Item | Drafted by | Decided by |
|---|---|---|
{decisions}

## Tests

{runs}

Each run succeeded and every declared output exists. That shows the tool runs through Comeni's
wiring and settings; it does not show its results are correct.

Draft digest `{record.digest}`. Opened by {record.opened_by}.
"""
