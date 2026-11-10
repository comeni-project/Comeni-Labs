"""Read what a completed run measured into its record (#465, #217).

A pipeline Mendel built may measure facts in the run: its measuring steps publish one report
per sample under `{results}/<process>/<sample>.measured.json`, and each run-time setting a record
of the value it took under `{results}/decided/<step>.<setting>.tsv`. When the run completes,
this reads them, **closed**: only the processes, measurements and settings the run's own
`pipeline.yml` declares, files of at most `MAX_BYTES`, and payloads that validate. Anything else
is skipped with a logged reason, never admitted, so a file a pipeline step wrote in the results
cannot speak for the run (Review Focus 5).
"""

import json
import logging
from pathlib import Path

from pydantic import ValidationError
from wiener_core.measured import DecidedValue, MeasuredFact

log = logging.getLogger(__name__)

MAX_BYTES = 64 * 1024
"""A report is a few hundred bytes; anything far larger is not one."""
MEASURING = "comeni/measure/"


def _allowed(pipeline) -> tuple[set[str], set[str], set[tuple[str, str]]]:
    processes = {step.process.lower() for step in pipeline.steps
                 if step.module.contract_id.startswith(MEASURING)}
    facts = {confirm.measurement for confirm in pipeline.confirms}
    decided = set()
    for step in pipeline.steps:
        for setting in step.settings:
            if setting.at_run is not None:
                facts.add(setting.at_run.fact)
                decided.add((step.id, setting.name))
    return processes, facts, decided


def _small(path: Path) -> str | None:
    if not path.is_file() or path.is_symlink():
        return None
    if path.stat().st_size > MAX_BYTES:
        log.warning("measured: %s is %d bytes, over %d; skipped", path, path.stat().st_size,
                    MAX_BYTES)
        return None
    return path.read_text(errors="replace")


def read(results: Path, pipeline) -> tuple[list[MeasuredFact], list[DecidedValue]]:
    """Every fact and decided value the run published that its pipeline declares."""
    processes, wanted, decisions = _allowed(pipeline)
    facts: list[MeasuredFact] = []
    for process in sorted(processes):
        for path in sorted((results / process).glob("*.measured.json")):
            text = _small(path)
            if text is None:
                continue
            try:
                report = json.loads(text)
            except ValueError:
                log.warning("measured: %s is not JSON; skipped", path)
                continue
            found = report.get("facts") if isinstance(report, dict) else None
            for measurement, fact in sorted((found or {}).items()):
                if measurement not in wanted or not isinstance(fact, dict):
                    continue
                try:
                    facts.append(MeasuredFact(
                        measurement=measurement,
                        sample=path.name.removesuffix(".measured.json"),
                        value=fact.get("value"), undetermined=fact.get("undetermined"),
                        coverage=fact.get("coverage"), by=fact.get("by") or [],
                    ))
                except ValidationError as error:
                    log.warning("measured: %s %s refused: %s", path, measurement,
                                error.errors()[0]["msg"])
    decided: list[DecidedValue] = []
    for step, setting in sorted(decisions):
        text = _small(results / "decided" / f"{step}.{setting}.tsv")
        for line in sorted((text or "").splitlines()):
            sample, sep, value = line.partition("\t")
            if not sep:
                continue
            try:
                decided.append(DecidedValue(step=step, setting=setting, sample=sample,
                                            value=value))
            except ValidationError as error:
                log.warning("measured: %s.%s %r refused: %s", step, setting, sample,
                            error.errors()[0]["msg"])
    return facts, decided
