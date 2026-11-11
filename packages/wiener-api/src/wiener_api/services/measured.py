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
                facts |= {f.measurement for f in setting.at_run.facts}
                decided.add((step.id, setting.name))
    return processes, facts, decided


def _inside(results: Path, path: Path) -> bool:
    """A real file or folder under the results, never one a link leads elsewhere to."""
    try:
        return not path.is_symlink() and path.resolve().is_relative_to(results.resolve())
    except OSError:
        return False


def _small(results: Path, path: Path) -> str | None:
    if not _inside(results, path) or not path.is_file():
        return None
    try:
        if path.stat().st_size > MAX_BYTES:
            log.warning("measured: a report over %d bytes was skipped", MAX_BYTES)
            return None
        return path.read_text(errors="replace")
    except OSError as error:
        log.warning("measured: a report could not be read: %s", type(error).__name__)
        return None


def _facts_in(text: str, sample: str, wanted: set[str]) -> list[MeasuredFact]:
    """One report's facts. Whatever it holds, it raises nothing: a file a step wrote must
    never stop the run's own record being written (Task 9 review)."""
    try:
        report = json.loads(text)
    except (ValueError, RecursionError):
        log.warning("measured: a report that is not JSON was skipped")
        return []
    found = report.get("facts") if isinstance(report, dict) else None
    if not isinstance(found, dict):
        return []
    facts = []
    for measurement, fact in sorted(found.items()):
        if measurement not in wanted or not isinstance(fact, dict):
            continue
        try:
            facts.append(MeasuredFact(
                measurement=measurement, sample=sample,
                value=fact.get("value"), undetermined=fact.get("undetermined"),
                coverage=fact.get("coverage"), by=fact.get("by") or [],
            ))
        except (ValidationError, TypeError) as error:
            log.warning("measured: a %s fact was refused: %s", measurement,
                        type(error).__name__)
    return facts


def read(results: Path, pipeline) -> tuple[list[MeasuredFact], list[DecidedValue]]:
    """Every fact and decided value the run published that its pipeline declares. Never
    raises: anything it cannot read is skipped, and logged without its name, which may be a
    sample's."""
    processes, wanted, decisions = _allowed(pipeline)
    facts: list[MeasuredFact] = []
    for process in sorted(processes):
        folder = results / process
        if not _inside(results, folder) or not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.measured.json")):
            text = _small(results, path)
            if text is not None:
                facts += _facts_in(text, path.name.removesuffix(".measured.json"), wanted)
    decided: list[DecidedValue] = []
    for step, setting in sorted(decisions):
        text = _small(results, results / "decided" / f"{step}.{setting}.tsv")
        for line in sorted((text or "").splitlines()):
            sample, sep, value = line.partition("\t")
            if not sep:
                continue
            try:
                decided.append(DecidedValue(step=step, setting=setting, sample=sample,
                                            value=value))
            except ValidationError:
                log.warning("measured: a value of %s.%s was refused", step, setting)
    return facts, decided
