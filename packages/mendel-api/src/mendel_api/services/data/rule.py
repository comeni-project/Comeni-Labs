"""How a folder's files are read into samples (#511): the reading rule, the fixes a person (or the
AI) applied, and what *Check these* finds.

- **The default rule** is the mate-token pairing (`pairing.pair`): every file is a sample, and
  two files that differ only in a mate token are one.
- **A pattern** names the parts of a file name: `{sample}` (one or more characters, not `/`) and
  `{read}` (`1` or `2`), with literal text between, e.g. `{sample}_R{read}.fastq.gz`. Files it does
  not fit are *unfit*: listed and counted, never silently dropped, and not samples.
- **Fixes** are applied after the rule, on every scan, so they survive a scan: `use_file` adds a
  file to a sample as its mate, `leave_out` keeps a sample listed but out of the analysis.
"""

import re
import statistics
from collections import Counter
from typing import Literal

from comeni_core.diagnostics import coded
from pydantic import BaseModel

from mendel_api.services.data import pairing

TOKEN = re.compile(r"\{(\w+)\}")


class Rule(BaseModel):
    pattern: str | None = None
    """`None` is the default mate-token pairing."""
    origin: Literal["rule", "you", "ai"] = "rule"
    confirmed: bool = False
    reason: str | None = None


class Fix(BaseModel):
    kind: Literal["use_file", "leave_out", "keep"]
    sample: str
    file: str | None = None
    """For `use_file`: the file's name in the same folder."""
    measurement: str | None = None
    """For `keep`: the measured value the person decided is fine for this sample."""
    by: Literal["you", "ai"] = "you"
    reason: str | None = None


def validate(fix: Fix, samples: list[dict], unfit: list[str]) -> None:
    """A fix that would do nothing is refused here (CLAUDE.md: validate offered ids at the
    receiving boundary): the sample must be one of this data's, and a mate must be a file that
    stands alone beside it."""
    names = {s["name"]: s for s in samples}
    if fix.sample not in names:
        raise ValueError(coded("MI0226", f"there is no sample {fix.sample!r} in this data"))
    if fix.kind == "use_file":
        lone = {_name(s["files"][0]) for s in samples
                if len(s["files"]) == 1 and s["name"] != fix.sample}
        if fix.file not in lone | set(unfit) or len(names[fix.sample]["files"]) != 1:
            raise ValueError(coded("MI0226", f"{fix.file!r} is not a file standing alone that "
                                             f"could be {fix.sample}'s mate"))
    if fix.kind == "keep" and not fix.measurement:
        raise ValueError(coded("MI0226", "say which measured value to keep"))


class Grouped(BaseModel):
    samples: list[tuple[str, list[int]]]
    unfit: list[int]
    examples: list[tuple[str, str, str | None]]


class Check(BaseModel):
    sample: str
    kind: Literal["missing_mate", "odd_fact"]
    detail: str
    fixes: list[Fix]
    measurement: str | None = None
    """For an odd fact: which measurement differs."""


def _compile(pattern: str) -> re.Pattern:
    tokens = TOKEN.findall(pattern)
    if (tokens.count("sample") != 1 or tokens.count("read") > 1
            or set(tokens) - {"sample", "read"}):
        raise ValueError(coded("MI0223", "a reading rule names {sample} once, and {read} at most "
                                         f"once, and nothing else: {pattern!r}"))
    parts, at = [], 0
    for found in TOKEN.finditer(pattern):
        parts.append(re.escape(pattern[at:found.start()]))
        parts.append(r"(?P<sample>[^/]+?)" if found[1] == "sample" else r"(?P<read>[12])")
        at = found.end()
    parts.append(re.escape(pattern[at:]))
    return re.compile("".join(parts))


def _by_pattern(names: list[str], pattern: str, taken: set[str]) -> Grouped:
    matcher = _compile(pattern)
    samples: dict[str, list[tuple[str, int]]] = {}
    unfit, examples = [], []
    for index, name in enumerate(names):
        found = matcher.fullmatch(name)
        if found is None:
            unfit.append(index)
            continue
        read = found.groupdict().get("read")
        samples.setdefault(found["sample"], []).append((read or "", index))
        if len(examples) < 3:
            examples.append((name, found["sample"], read))
    grouped = [(pairing.unique(sample[:256], taken), [i for _, i in sorted(files)])
               for sample, files in samples.items()]
    return Grouped(samples=grouped, unfit=unfit, examples=examples)


def _by_default(names: list[str], taken: set[str]) -> Grouped:
    grouped = pairing.pair(names, taken)
    examples = []
    for sample, indexes in grouped:
        for index in indexes:
            if len(examples) < 3:
                found = pairing._MATE.match(names[index])
                read = found["mate"][-1] if found and len(indexes) == 2 else None
                examples.append((names[index], sample, read))
    return Grouped(samples=grouped, unfit=[], examples=examples)


def group(names: list[str], rule: Rule, fixes: list[Fix],
          taken: set[str] | None = None) -> Grouped:
    """One folder's `names` as samples (indexes into `names`, read 1 first), with the files the
    rule does not fit and the first three fits as examples, and `fixes` applied."""
    taken = set() if taken is None else taken
    found = (_by_default(names, taken) if rule.pattern is None
             else _by_pattern(names, rule.pattern, taken))
    samples = dict(found.samples)
    unfit = list(found.unfit)
    for fix in fixes:
        if fix.kind != "use_file" or fix.sample not in samples or fix.file not in names:
            continue
        extra = names.index(fix.file)
        donor = next((s for s, files in samples.items() if extra in files and s != fix.sample),
                     None)
        if donor is not None:
            samples[donor] = [i for i in samples[donor] if i != extra]
            if not samples[donor]:
                del samples[donor]
        unfit = [i for i in unfit if i != extra]
        files = sorted({*samples.pop(fix.sample), extra}, key=lambda i: _read_order(names[i]))
        stem = pairing._MATE.match(names[files[0]])
        # The pair takes its shared stem, unless another sample here or in another folder has it.
        free = stem and stem["stem"] not in samples and stem["stem"] not in taken
        name = stem["stem"] if free else fix.sample
        taken.add(name)
        samples[name] = files
    return Grouped(samples=list(samples.items()), unfit=unfit, examples=found.examples)


def _words(measurement: str) -> str:
    """A measurement's id as words: `read_length` → *Read length*."""
    return measurement.replace("_", " ").capitalize()


def _plain(value: object) -> str:
    """A value as a person reads it: `true`, `101`, `phred33`."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int | float) and abs(value) >= 10_000:
        return f"{round(value):,}"  # 2,814,816 rather than 2814816 (walk 2026-11-16)
    return str(value)


def _read_order(name: str) -> tuple[str, str]:
    found = pairing._MATE.match(name)
    return (found["mate"][-1] if found else "", name)


def _name(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _far_from_median(measurement: str, values: list[tuple[str, object]],
                     kept: set[tuple[str, str]]) -> list[Check]:
    numbers = [(s, v) for s, v in values if isinstance(v, int | float) and not isinstance(v, bool)]
    if len(numbers) < 3 or len(numbers) != len(values):
        return []
    median = statistics.median(v for _, v in numbers)
    if median <= 0:
        return []
    return [Check(sample=sample, kind="odd_fact", measurement=measurement,
                  detail=f"{_words(measurement)} is {_plain(value)}; the median is "
                         f"{_plain(int(median) if median == int(median) else median)}",
                  fixes=[Fix(kind="leave_out", sample=sample)])
            for sample, value in numbers
            if (sample, measurement) not in kept
            and (value > median * 10 or value * 10 < median)]


def to_check(found: list[Check]) -> int:
    """How many samples need a look: one flagged for two measurements is one (walk 2026-11-16)."""
    return len({c.sample for c in found})


def checks(samples: list[dict], unfit: list[str], fixes: list[Fix] = ()) -> list[Check]:
    """What *Check these* lists: a sample without its mate where most files are in pairs, with
    the nearby file that looks like it; and a sample whose measured value differs from the one
    most samples share. Left-out samples are not checked again."""
    kept = [s for s in samples if not s.get("left_out")]
    found: list[Check] = []
    # Paired data: more of its files sit in pairs than alone.
    paired = sum(len(s["files"]) for s in kept if len(s["files"]) == 2) > sum(
        len(s["files"]) == 1 for s in kept)
    # Only the kind of data that comes in pairs is missing a mate: a genome among reads is not.
    paired_kinds = {s.get("type_id") for s in kept if len(s["files"]) == 2}
    if paired:
        lone = {s["name"]: _name(s["files"][0]) for s in kept
                if len(s["files"]) == 1 and s.get("type_id") in paired_kinds}
        claimed: set[str] = set()
        # Read 1 first, so two lone halves of one pair are one check, raised on read 1.
        for sample, file in sorted(lone.items(), key=lambda item: _read_order(item[1])):
            if file in claimed:
                continue
            mate = pairing._MATE.match(file)
            nearby = [f for s, f in lone.items() if s != sample and mate
                      and (other := pairing._MATE.match(f)) and other["stem"] == mate["stem"]
                      and other["mate"][-1] != mate["mate"][-1]]
            nearby += [f for f in unfit if mate and (other := pairing._MATE.match(f))
                       and other["stem"] == mate["stem"]]
            claimed.update(nearby[:1])
            fixes = [Fix(kind="use_file", sample=sample, file=f) for f in nearby[:1]]
            found.append(Check(sample=sample, kind="missing_mate",
                               detail=f"{file} has no mate" + (f"; {nearby[0]} looks like it"
                                                               if nearby else ""),
                               fixes=[*fixes, Fix(kind="leave_out", sample=sample)]))
    # A lone half, and the file suggested as its mate, differ because they are halves: that is the
    # missing mate, said once, not again as odd facts.
    flagged = {c.sample for c in found} | {
        s["name"] for s in kept if len(s["files"]) == 1
        and any(f.file == _name(s["files"][0]) for c in found for f in c.fixes)}
    measured: dict[str, list[tuple[str, object]]] = {}
    for s in kept:
        if s["name"] in flagged:
            continue
        for fact in s.get("facts", []):
            measured.setdefault(fact["measurement"], []).append((s["name"], fact.get("value")))
    kept_values = {(f.sample, f.measurement) for f in fixes if f.kind == "keep"}
    for measurement, values in sorted(measured.items()):
        common, count = Counter(_plain(v) for _, v in values).most_common(1)[0]
        if count <= len(values) / 2:
            # No value most samples share, as with counts: a number ten times above or below
            # the median is the odd one (walk 2026-11-16: an assembly in 65 pieces among 1-24).
            found += _far_from_median(measurement, values, kept_values)
            continue
        if count == len(values):
            continue
        for sample, value in values:
            if (sample, measurement) in kept_values:
                continue  # the person decided this value is fine
            if _plain(value) != common:
                found.append(Check(sample=sample, kind="odd_fact", measurement=measurement,
                                   detail=f"{_words(measurement)} is {_plain(value)}; most "
                                          f"samples have {common}",
                                   fixes=[Fix(kind="leave_out", sample=sample)]))
    return found

