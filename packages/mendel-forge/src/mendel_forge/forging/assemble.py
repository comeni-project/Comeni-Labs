"""Approved items, written as a draft registry layer and proven with the builder's own code
(spec §4): it loads over the registry, and its contract conforms to the module's `main.nf`.

Nothing here writes into a registry. The draft is a folder of its own, rewritten whole each
time, so what is proven is exactly what is on disk.
"""

import shutil
from pathlib import Path

import yaml
from comeni_core.declared.contract import ModuleContract, Provenance
from comeni_core.declared.signature import join
from comeni_core.declared.tooltest import ToolTest
from comeni_core.diagnostics import coded
from comeni_vendor.ops import EXCLUDED, digest_of_module
from mendel_compiler import conformance, registry_lint
from mendel_compiler.modulespec import ModuleSpec
from mendel_resolver import layers
from pydantic import BaseModel, ConfigDict, JsonValue

from mendel_forge.forging.model import KEY, Piece
from mendel_forge.forging.values import contract_of, validate_value
from mendel_forge.model import Problem


class ModuleOrigin(BaseModel):
    """Where the module's source comes from: the catalogue's clone, at the snapshot commit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_dir: Path
    module_id: str
    """`nf-core/star/align`: the module key a contract's `nf_include` names."""
    repo: str
    sha: str
    path: str
    licence: str
    data_commit: str = ""
    """The `test-datasets` commit a test's files are pinned to (from the last good sync)."""


class Proof(BaseModel):
    loaded: bool
    conforms: bool
    problems: list[Problem]
    blames: Piece | None
    """The piece a failure re-opens, when there is one."""


def write_layer(
    values: dict[str, JsonValue], contract_id: str, provenance: Provenance,
    origin: ModuleOrigin, *, base: Path, out: Path,
) -> list[Path]:
    """Write the draft layer to `out` (replacing what was there). Returns the files written.
    `ValueError` with `MF0511` when the layer could not be written as it would load."""
    contract = contract_of(values, contract_id, provenance)
    licence = base / "LICENSES" / f"{origin.licence}.txt"
    if not licence.is_file():
        raise ValueError(coded("MF0511", f"the registry has no text for licence "
                               f"{origin.licence!r} (LICENSES/{origin.licence}.txt), so the "
                               "module cannot be vendored under it"))
    for key in values:
        if not KEY.match(key):
            raise ValueError(coded("MF0511", f"{key!r} is not an item key"))
    tests = sorted(k for k in values if k.startswith("tests:test:"))
    if tests and not origin.data_commit:
        raise ValueError(coded("MF0511", "no `test-datasets` commit is known yet, so a test's "
                               "files cannot be pinned: sync the catalogue first"))
    if out.exists():
        shutil.rmtree(out)
    tool = out / "tools" / origin.module_id
    written: list[Path] = []

    def put(path: Path, text: str) -> None:
        if not path.resolve().is_relative_to(out.resolve()):
            raise ValueError(coded("MF0511", f"{path} is outside the draft layer"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        written.append(path)

    put(out / "registry.yml", "name: forge-draft\nrequires_format: 2\n")
    put(out / "LICENSES" / licence.name, licence.read_text())
    shutil.copytree(origin.source_dir, tool / "module",
                    ignore=shutil.ignore_patterns(*EXCLUDED))
    written += sorted(p for p in (tool / "module").rglob("*") if p.is_file())
    put(tool / "module.yml", _yaml({
        "declares": "module", "id": origin.module_id, "licence": origin.licence,
        "upstream": {"repo": origin.repo, "sha": origin.sha, "path": origin.path},
        "excluded": list(EXCLUDED), "digest": digest_of_module(tool / "module"),
    }))
    put(tool / "contract.yml",
        _yaml({"declares": "contract", **contract_file(
            contract, ModuleSpec.parse(tool / "module" / "main.nf").emit_formats)}))
    for key, value in sorted(values.items()):
        if key.startswith("vocabulary:type:"):
            declared = validate_value(key, value).model_dump(mode="json", exclude_defaults=True)
            put(out / "vocabulary" / "types" / f"{declared['id']}.yml",
                _yaml({"declares": "vocabulary", **declared}))
    for key, value in sorted(values.items()):
        if key.startswith("vocabulary:family:"):
            declared = validate_value(key, value).model_dump(mode="json")
            put(out / "vocabulary" / "families" / f"{declared['id']}.yml",
                _yaml({"declares": "family", **declared}))
    drafted = [validate_value(k, v) for k, v in values.items() if k.startswith("vocabulary:role:")]
    roles = [{"id": r.name, "explain": r.explain} for r in sorted(drafted, key=lambda r: r.name)]
    if roles:
        put(out / "vocabulary" / "roles" / "forge.yml", _yaml({"declares": "role", "roles": roles}))
    for key, value in sorted(values.items()):
        if key.startswith("rules:rule:"):
            decision = validate_value(key, value).model_dump(mode="json", exclude_defaults=True)
            put(out / "rules" / f"{key.removeprefix('rules:rule:')}.yml",
                _yaml({"declares": "rule", "version": 1, "decisions": [decision]}))
    for key, value in sorted(values.items()):
        if key.startswith("rules:derive:"):
            # A fact a decision reads or takes (`then: {fact:}`, #461), one file per fact: the
            # layer stacks derivations by fact, so a file per fact never collides with another
            # tool's at publishing unless the fact itself does.
            derived = validate_value(key, value).model_dump(mode="json", exclude_defaults=True)
            put(out / "rules" / "derived" / f"{derived['fact']}.yml",
                _yaml({"declares": "rule", "version": 1, "derives": [derived]}))
    measurements: dict[str, str] = {}
    for key, value in sorted(values.items()):
        if key.startswith(("vocabulary:measurement:", "measurers:measurement:")):
            declared = validate_value(key, value).model_dump(mode="json", exclude_defaults=True)
            if declared["id"] in measurements:
                raise ValueError(coded("MF0511", f"measurement {declared['id']!r} is drafted "
                                       f"twice, as {measurements[declared['id']]} and {key}: "
                                       "keep one"))
            measurements[declared["id"]] = key
            put(out / "vocabulary" / "measurements" / f"{declared['id']}.yml",
                _yaml({"declares": "measurement", **declared}))
    for key, value in sorted(values.items()):
        if key.startswith("measurers:measurer:"):
            _measurer(put, out, key.removeprefix("measurers:measurer:"),
                      validate_value(key, value), contract_id)
    for key in tests:
        name = key.removeprefix("tests:test:")
        test = ToolTest(**values[key], contract=contract_id, name=name,
                        data_commit=origin.data_commit)
        put(tool / "tests" / f"{name}.yml",
            _yaml({"declares": "test", **test.model_dump(mode="json", exclude_defaults=True)}))
    return written


def _measurer(put, out: Path, name: str, draft, contract_id: str) -> None:
    """A drafted `by: tool` measurer as the registry lays one out (#487): what only the
    engine decides is fixed here, never drafted."""
    folder = out / "measurers" / "measures" / name
    declared = {"declares": "measurer", "id": name, "version": "1.0.0",
                "measures": draft.measures, "by": "tool", "uses": contract_id,
                "output": draft.output, "entry": f"piece/{name}.py", "runs": ["pipeline"]}
    if draft.decided:
        declared["decided"] = draft.decided
    explain = " ".join(draft.explain.split())
    put(folder / "measurer.yml", f"# {explain}\n" + _yaml(declared))
    put(folder / "piece" / f"{name}.py", draft.code)
    put(folder / "piece" / f"test_{name}.py", draft.tests)


def _in_type(port: dict, field: str) -> dict:
    """A dumped port with its states written in its type."""
    states = frozenset(port.pop(field, ()))
    return {**port, "type_id": join(port["type_id"], states)}


def contract_file(contract: ModuleContract, formats: dict[str, list[str]]) -> dict:
    """A contract as it is written: states in the type, and each output's formats from the
    module, so a person never has to state what `main.nf` already says."""
    produces = [port.model_copy(update={"format": frozenset(formats.get(port.name, ()))})
                for port in contract.produces]
    data = contract.model_copy(update={"produces": produces}).model_dump(
        mode="json", exclude_defaults=True)
    data["produces"] = [_in_type(port, "state") for port in data.get("produces", [])]
    for port in data.get("consumes", []):
        if "accepts" in port:
            port["accepts"] = [_in_type(a, "states") for a in port["accepts"]]
    data["consumes"] = [_in_type(port, "state_required") if "type_id" in port else port
                        for port in data.get("consumes", [])]
    return data


def _yaml(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def prove(base: Path, below: list[Path], draft: Path) -> Proof:
    """Load `draft` over `base` (and the pending drafts `below`) and hold its contract to its
    module. A load failure blames the piece its message names; a conformance failure, the
    contract."""
    try:
        stack = layers.load([base, *below, draft])
    except (ValueError, KeyError) as error:
        said = str(error)
        return Proof(loaded=False, conforms=False, blames=_blamed(said),
                     problems=[Problem(code="MF0511", says=f"the draft does not load: {said}")])
    # The draft's own contracts, read from its files: it cannot load alone, since its types
    # are the registry's.
    contracts = {yaml.safe_load(p.read_text())["id"] for p in draft.rglob("contract.yml")}
    found = [d for d in conformance.blocking(
                 conformance.check(stack.registry, stack.modules, stack.measurements))
             if d.where in contracts]
    if found:
        return Proof(loaded=True, conforms=False, blames=Piece.CONTRACT, problems=[
            Problem(code="MF0512", says=f"{d.code}: {d.summary}") for d in found])
    reached = registry_lint.pieces(draft)
    if reached:
        return Proof(loaded=True, conforms=False, blames=Piece.MEASURERS, problems=[
            Problem(code="MF0512", says=f"{d.code} {d.where}: {d.summary}") for d in reached])
    return Proof(loaded=True, conforms=True, blames=None, problems=[])


def _blamed(message: str) -> Piece:
    """The piece a load message is about: by the file it names, else by its words, a rule's
    before a measurer's, since a rule's message may name the measurer it lacks."""
    lowered = message.lower()
    for folder, piece in (("rules/", Piece.RULES), ("measurers/", Piece.MEASURERS),
                          ("vocabulary/", Piece.VOCABULARY)):
        if folder in lowered:
            return piece
    if "md0027" in lowered:
        return Piece.MEASURERS
    if "rule" in lowered or "decision" in lowered:
        return Piece.RULES
    if "measurer" in lowered:
        return Piece.MEASURERS
    if any(word in lowered for word in ("type", "state", "role", "measurement", "family")):
        return Piece.VOCABULARY
    return Piece.CONTRACT
