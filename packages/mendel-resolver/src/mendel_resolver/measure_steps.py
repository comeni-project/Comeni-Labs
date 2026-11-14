"""Pipeline measurers as generated steps (#465).

A measurer that runs in the `pipeline` becomes a step: a contract whose outputs are the
`measurement.<id>` types, so the router routes measuring like any other work and a build that
wants a fact reaches the step that measures it. Two shapes:

- **one step per format**, for every `by: code` measurer of that format's record: the file is
  read once and every fact comes out of the same pass, as on the server;
- **one step per `by: tool` measurer**, over the tool's output port: the tool is an ordinary step
  and the parser follows it.

The contracts are built here, purely, from declarations. They join only the registry a build
routes with (`Registry.with_contracts`), never the loaded one, so the registry browser, the docs
and conformance list what a layer declares and nothing generated. The step's code (the runner
and the pieces) is written by the compiler when it stages the pipeline.
"""

from dataclasses import dataclass

from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.inspection import CodecPiece, FormatPiece, InspectionCatalogue, Measurer
from comeni_core.declared.registry import Registry

PREFIX = "comeni/measure/"
"""Every generated measuring step's contract id starts here."""

RUNNER_IMAGE = (
    "python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b"
)
"""The plain Python image every measuring step runs on, pinned by digest (2026-11-10, from
`docker buildx imagetools inspect python:3.12-slim`). The runner needs the standard library only."""


@dataclass(frozen=True)
class MeasureStep:
    """One generated step: its contract, and the pieces the compiler stages with it."""

    contract: ModuleContract
    format: FormatPiece | None
    """For a step of our code: the format whose records the measurers read."""
    codecs: tuple[CodecPiece, ...]
    """Every codec, sorted by id: the runner picks one by the file's name, as the server does."""
    measurers: tuple[Measurer, ...]
    """Sorted by id. One, for a tool's parser."""

    @property
    def name(self) -> str:
        """The step's folder and process stem: the format's id, or the tool measurer's."""
        return self.contract.id.removeprefix(PREFIX).rsplit("@", 1)[0]


def _contract(name: str, version: str, consumes: str, measurers: list[Measurer],
              pinned: list[str]) -> ModuleContract:
    return ModuleContract.model_validate({
        "id": f"{PREFIX}{name}@{version}",
        "nf_process": f"MEASURE_{name.upper()}",
        "nf_include": f"modules/comeni/measure/{name}/main",
        "consumes": [{"name": "data", "type_id": consumes}],
        "produces": [
            {"name": m.measures, "type_id": f"measurement.{m.measures}"} for m in measurers
        ],
        "roles": ["measurement"],
        "nf_inputs": [{"ports": ["data"]}],
        "container": RUNNER_IMAGE,
        "provenance": {
            # The pieces, pinned: a new version of any of them is a new contract digest, so a
            # pipeline's lockfile moves when the code its step runs does.
            "source": "generated from " + " + ".join(pinned),
            "drafted_by": "generated",
            "approved_by": "the measurers' own review",
            "approved_at": "",
        },
    })


def steps_for(catalogue: InspectionCatalogue, registry: Registry) -> list[MeasureStep]:
    """Every generated step this catalogue's pipeline measurers make, sorted by contract id."""
    codecs = tuple(sorted(catalogue.codecs.values(), key=lambda c: c.id))
    pipeline = sorted(
        (m for m in catalogue.measurers.values() if m.runs_on("pipeline")), key=lambda m: m.id
    )
    steps = []
    for fmt in sorted(catalogue.formats.values(), key=lambda f: f.id):
        mine = [m for m in pipeline if m.by == "code" and m.record == fmt.record]
        if not mine:
            continue
        pinned = [f"{fmt.id}@{fmt.version}", *(f"{m.id}@{m.version}" for m in mine)]
        steps.append(MeasureStep(
            contract=_contract(fmt.id, fmt.version, fmt.reads[0], mine, pinned),
            format=fmt, codecs=codecs, measurers=tuple(mine),
        ))
    for measurer in (m for m in pipeline if m.by == "tool"):
        tool = registry.get(measurer.uses)
        (port,) = [p for p in tool.produces if p.name == measurer.output]
        steps.append(MeasureStep(
            contract=_contract(measurer.id, measurer.version, port.type_id, [measurer],
                               [f"{measurer.id}@{measurer.version}", measurer.uses]),
            format=None, codecs=(), measurers=(measurer,),
        ))
    return sorted(steps, key=lambda s: s.contract.id)


def contracts_for(catalogue: InspectionCatalogue, registry: Registry) -> list[ModuleContract]:
    """The generated steps' contracts, for `Registry.with_contracts`."""
    return [step.contract for step in steps_for(catalogue, registry)]
