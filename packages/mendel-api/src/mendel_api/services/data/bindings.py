"""A run's inputs, answered from the analysis's data (#508, #511): **no path is typed**.

Each channel the kept `pipeline.yml` declares is answered by type:

- a **per-sample** channel by the kept samples of its type. In a samplesheet pipeline they are
  the sheet's rows, in the artifact's column order. In a direct one they are sent as `stage`: the
  samples and their files, which Wiener links into the run's own folder and points the parameter
  at, so exactly these files are read, not whatever else shares their folder;
- a **study** channel by the reference of its type, or by the one sample file of that type;
- an optional channel nothing answers is sent empty, which runs without it.

Anything else is `missing`, with why, and the run is not sent. Built when the run is sent; never
written to the draft or to a table (invariant 15).
"""

import os
from typing import Any

from comeni_core.artifact.pipeline import InputForm, Pipeline
from pydantic import BaseModel

SAMPLE = "sample"
"""The samplesheet's first column, the sample's name (`build/Samplesheet.tsx`, Wiener's CSV)."""


class Missing(BaseModel):
    channel: str
    type_id: str
    why: str


class Bindings(BaseModel):
    params: dict[str, Any] = {}
    missing: list[Missing] = []
    summary: str = ""


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _gone(paths: list[str]) -> list[str]:
    return [os.path.basename(p) for p in paths if not os.path.exists(p)]


def bind(pipeline: Pipeline | None, samples: list[dict], references: list[dict],
         columns: dict[str, dict[str, str]] | None = None) -> Bindings:
    """`columns` are the person's (`{name: {sample: value}}`): a fact the pipeline's samplesheet
    asks for and nothing measured is taken from the column of that measurement's name."""
    columns = columns or {}
    if pipeline is None:
        return Bindings(missing=[Missing(channel="", type_id="",
                                         why="keep the pipeline first: a run is of a kept one")])
    kept = [s for s in samples if not s.get("left_out")]
    params: dict[str, Any] = {}
    missing: list[Missing] = []
    rows: dict[str, dict[str, str]] = {}
    used_refs: set[str] = set()
    for channel in pipeline.channels:
        if channel.table is not None:
            missing.append(Missing(channel=channel.name, type_id=channel.type_id,
                                   why="a table of several items is not answered from Data yet"))
            continue
        if channel.grain.value == "sample":
            mine = [s for s in kept if s.get("type_id") == channel.type_id]
            if not mine:
                if channel.optional:
                    params[channel.param] = ""
                else:
                    missing.append(Missing(channel=channel.name, type_id=channel.type_id,
                                           why=f"no kept sample is {channel.type_id}"))
                continue
            gone = [f for s in mine for f in _gone(s["files"])]
            if gone:
                missing.append(Missing(channel=channel.name, type_id=channel.type_id,
                                       why=f"file not found: {', '.join(gone[:3])}"))
                continue
            if pipeline.input_form is InputForm.SAMPLESHEET:
                for s in mine:
                    row = rows.setdefault(s["name"], {SAMPLE: s["name"]})
                    row.update(dict(zip(channel.columns, s["files"], strict=False)))
            elif len(channel.columns) == 2 and any(len(s["files"]) != 2 for s in mine):
                # `fromFilePairs` reads pairs only: a lone file would be dropped without a word.
                lone = [s["name"] for s in mine if len(s["files"]) != 2]
                missing.append(Missing(channel=channel.name, type_id=channel.type_id,
                                       why=f"this pipeline reads pairs; {', '.join(lone[:3])} "
                                           "has one file"))
            else:
                params[channel.param] = {"stage": [{"sample": s["name"], "files": s["files"]}
                                                   for s in mine]}
            continue
        ref = next((r for r in references if r["type_id"] == channel.type_id), None)
        if ref is not None:
            if _gone([ref["path"]]):
                missing.append(Missing(channel=channel.name, type_id=channel.type_id,
                                       why=f"file not found: {ref['name']}"))
                continue
            params[channel.param] = ref["path"]
            used_refs.add(ref["path"])
            continue
        single = [s for s in kept if s.get("type_id") == channel.type_id and len(s["files"]) == 1]
        if len(single) == 1 and not _gone(single[0]["files"]):
            params[channel.param] = single[0]["files"][0]
        elif channel.optional:
            params[channel.param] = ""
        else:
            missing.append(Missing(channel=channel.name, type_id=channel.type_id,
                                   why=f"no reference is {channel.type_id}"))
    if pipeline.input_form is InputForm.SAMPLESHEET and rows:
        by_name = {s["name"]: s for s in kept}
        # **Every row has every column**, blank where empty: Wiener writes the CSV's header from
        # the rows, and a short first row would drop a column for every sample (Checkpoint B).
        header = [SAMPLE, *[c for ch in pipeline.channels if ch.grain.value == "sample"
                            and ch.table is None for c in ch.columns]]
        for fact in pipeline.sheet_facts:
            if fact.from_row is not None:
                continue  # the row states it: its file cell is there or blank (Checkpoint B)
            header.append(fact.column)
            given = columns.get(fact.measurement, {})
            for name, row in rows.items():
                values = {f["measurement"]: f.get("value") for f in by_name[name]["facts"]}
                value = values.get(fact.measurement)
                if value is None and given.get(name, "").strip():
                    value = given[name].strip()
                if value is not None:
                    row[fact.column] = str(value).lower() if isinstance(value, bool) else str(value)
                elif fact.required:
                    missing.append(Missing(channel=fact.column, type_id=fact.describes,
                                           why=f"{name} has no {fact.measurement}: measure it or "
                                               f"give it in a column named {fact.measurement}"))
        params["input"] = [{column: row.get(column, "") for column in dict.fromkeys(header)}
                           for row in rows.values()]
    sample_count = len({s["name"] for s in kept})
    words = [_plural(sample_count, "sample")]
    if used_refs:
        words.append(_plural(len(used_refs), "reference"))
    return Bindings(params=params if not missing else {}, missing=missing,
                    summary=", ".join(words))
