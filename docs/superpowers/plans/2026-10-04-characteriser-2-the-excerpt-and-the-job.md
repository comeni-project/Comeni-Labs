# Characteriser 2 — the excerpt and the job — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A sample nothing reads by its extension is read by the AI, end to end on the server. The upload decodes an excerpt and queues a job. The job makes the two calls through door 6 and records what was admitted as *read by AI*. A type the engine reads is handed back to its inspector when the browser sends the file again.

**Architecture:** One new service, `services/characterise.py`, holds the pure excerpt (`excerpt()`), the availability check (`available()`), and the reading itself (`read_sample()`, synchronous and testable without a queue). `authoring_jobs.characterise_sample` is its thin ARQ wrapper on the AI worker, which keeps no result for it. The reading's state lives on the question block (`Question.reading`), as phrasing does, so the existing poll carries it. `authoring.answer_with_reading` records an admitted reply through the same path a sample uses, with `FactSource.MODEL_READ`. The upload route starts a reading on `no_inspector`, and on a hand-back passes the recorded type to `inspect.inspect_sample`.

**Tech Stack:** Python `zlib`, FastAPI, ARQ (`arq.worker.func`), pydantic 2, pytest.

**Spec:** `docs/superpowers/specs/2026-10-04-the-characteriser-design.md` §4, §5, §7, §8, §10, §12. Part 14.7.7.2 of #135. Depends on plan 1 (`2026-10-04-characteriser-1-declarations.md`).

## Global Constraints

- **The excerpt is never stored by Comeni Labs.** It lives in the request, then in the job's arguments in Redis until the worker takes it, and the job keeps no result (spec §5).
- **Gzip is recognised by its first bytes, `1f 8b`, never by the extension; decompression stops at 64 KB of output** (spec §5).
- **The excerpt is the first stretch of readable text at least 200 bytes long, cut at 8 KB or 200 lines**; fewer than 200 readable bytes means nothing is sent (spec §5).
- **Door 6 is asked (`Crossing.DOOR_6`) before the payload is built**; `Crossing.CHARACTERISE` is asked before an excerpt is taken (spec §4).
- **On a hand-back, only the type the session recorded can claim a file**, never anything the browser sends (spec §8).
- **The person's word stands**; a difference is shown, never written over (spec §7).
- **The job never raises for a refusal**: a refused or failed call ends as a reading state the card shows (`authoring_jobs`' rule).
- Diagnostics are declared in `diagnostics.yml` and emitted with `coded()`; the page is regenerated.
- Python tests always run with `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel` on the command line, from the repository root. Never bare `pytest`.
- Run `make check` on its own before each commit.

## Rulings against the spec, for the operator

1. **The upload is offered on an input gap whenever the AI can read.** Today `_gap_options` offers *I have it, and I'll upload a sample* only when a trusted format reads the input's type, which is only `fastq.reads`. So a BAM, FASTA or GTF could never reach the characteriser. The spec's §1 (*no longer a dead end*) needs the offer. This plan makes it: at level 0 with a model configured, every input gap offers the upload. Measurement gaps keep today's rule. Cost if wrong: the offer is narrowed again in one function.
2. **A hand-back's type is recorded as `MEASURED`, not `MODEL_READ`.** The format's `confirms()` checked the content, which is what *measured* means for a type today. The card still says *type read by AI* (plan 3), from the reading state. Cost if wrong: one fact's source.
3. **The job keeps no result, through `arq.worker.func(…, keep_result=0)` for this job only**, not lane-wide. Other AI jobs are unchanged. Two tests that read `f.__name__` from the worker's list learn to unwrap a `Function`. Cost if wrong: none to behaviour.
4. **A reading that never finishes is shown as *the AI didn't answer* once it is older than the AI job timeout plus a minute.** This happens when a reading is read, without writing anything. A worker killed mid-job otherwise leaves the card waiting forever. Cost if wrong: a different threshold.

## Review Focus

1. **A truncated gzip** (the 4 MB head cut mid-member): the excerpt is taken from what decompressed, never an exception. Pinned in Task 1.
2. **A FASTA whose first line is 9 KB** (one long sequence line): the excerpt is cut at 8192 bytes mid-line, still within the type's bound. Pinned in Task 1.
3. **Two uploads on one question while a reading is out**: the second is refused with MI0215, and nothing is queued twice. Pinned in Task 5.
4. **The job delivered twice, or after the person answered the question by a click**: the second delivery, or a stale one, spends no call. Pinned in Task 4.
5. **A hand-back whose re-sent file fails the format's content check**: `unreadable`, and the recorded type is dropped, so a third upload is not claimed by it. Pinned in Task 5.

---

## File structure

| File | Responsibility |
|---|---|
| Create `packages/mendel-api/src/mendel_api/services/characterise.py` | `excerpt()`, `Excerpt`, `available()`, `read_sample()` |
| Modify `packages/mendel-api/src/mendel_api/authoring/types.py` | `SampleReading`; `Question.reading` |
| Modify `packages/mendel-api/src/mendel_api/services/authoring.py` | `start_reading`, `reading_failed`, `answer_with_reading`, the shared recording, MI0215, `_words_coming`, the stale view, the upload offer, `ai_for` |
| Modify `packages/mendel-api/src/mendel_api/services/authoring_jobs.py` | `CHARACTERISE`, `enqueue_characterise`, `characterise_sample` |
| Modify `packages/mendel-api/src/mendel_api/ai_worker.py` | the job, keeping no result |
| Modify `packages/mendel-api/src/mendel_api/services/inspect.py` | `match(…, claimed=)`, `inspect_sample(…, claimed=)` |
| Modify `packages/mendel-api/src/mendel_api/routes/authoring.py` | `reading` outcome; the hand-back |
| Modify `packages/mendel-api/src/mendel_api/authoring/protocol.py` | the branch marked built |
| Modify `packages/comeni-core/src/comeni_core/diagnostics.yml` | MI0215 |
| Tests: `packages/mendel-api/tests/test_characterise_excerpt.py` (new), `test_characterise_reading.py` (new), `test_authoring_upload_route.py`, `test_inspect.py`, `test_authoring_protocol.py`, `test_forge_jobs.py`, `test_authoring_routes.py` | |

---

### Task 1: The excerpt

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/characterise.py`
- Test: `packages/mendel-api/tests/test_characterise_excerpt.py`

**Interfaces:**
- Consumes: `comeni_core.spell.marks.EXCERPT_BYTES`, `EXCERPT_LINES` (plan 1, Task 3).
- Produces: `characterise.Excerpt(text: str, binary_before: bool)` (a `NamedTuple`); `characterise.excerpt(head: bytes) -> Excerpt | None`; `DECODED_CAP = 64 * 1024`; `MIN_TEXT = 200`.

- [x] **Step 1: Write the failing tests**

```python
"""The excerpt a model is shown (spec §5): readable text, bounded, never more."""

import gzip
import struct
import zlib

from comeni_core.artifact.egress import CharacteriseRequest
from comeni_core.spell.marks import EXCERPT_BYTES, EXCERPT_LINES
from mendel_api.services.characterise import DECODED_CAP, MIN_TEXT, excerpt

HEADER = (
    "@HD\tVN:1.6\tSO:coordinate\n"
    + "".join(f"@SQ\tSN:chr{i}\tLN:{1000 * i}\n" for i in range(1, 30))
    + "@PG\tID:bwa\tPN:bwa\tVN:0.7.17\n"
)


def _bam(header: str = HEADER) -> bytes:
    """A BAM's first block as BGZF writes it: gzip around `BAM\\1`, a length, the header."""
    raw = b"BAM\x01" + struct.pack("<i", len(header)) + header.encode() + b"\x00" * 64
    return gzip.compress(raw)


def test_a_bams_header_is_read_after_its_binary_start():
    got = excerpt(_bam())
    assert got is not None and got.binary_before
    assert got.text.startswith("@HD\tVN:1.6\tSO:coordinate")


def test_gzip_is_recognised_by_its_first_bytes_not_its_name():
    assert excerpt(gzip.compress(b"@r1\nACGT\n+\nIIII\n" * 40)).text.startswith("@r1")


def test_a_fasta_is_text_from_its_first_byte():
    got = excerpt(b">chr1 test\n" + b"ACGT" * 100 + b"\n")
    assert got is not None and not got.binary_before and got.text.startswith(">chr1")


def test_a_very_long_first_line_is_cut_at_the_byte_bound():
    got = excerpt(b">chr1\n" + b"A" * 20_000)
    assert got is not None and len(got.text.encode()) <= EXCERPT_BYTES
    CharacteriseRequest(excerpt=got.text)  # the type agrees


def test_many_lines_are_cut_at_the_line_bound():
    got = excerpt(b"chr1\t.\tgene\t1\t100\t.\t+\t.\tgene_id \"g\";\n" * 1000)
    assert got is not None and len(got.text.splitlines()) == EXCERPT_LINES


def test_a_file_with_no_stretch_of_text_sends_nothing():
    assert excerpt(bytes(range(256)) * 400) is None


def test_too_little_text_sends_nothing():
    assert excerpt(b"\x00\x01" + b"a" * (MIN_TEXT - 1) + b"\x00") is None


def test_a_bomb_stops_at_the_decoded_cap():
    bomb = gzip.compress(b"\x00" * (50 * 2**20))
    assert excerpt(bomb) is None  # 64 KB of zeros decoded, and no text in it


def test_a_truncated_gzip_is_read_as_far_as_it_goes():
    whole = gzip.compress((HEADER * 20).encode())
    got = excerpt(whole[: len(whole) // 2])
    assert got is not None and got.text.startswith("@HD")


def test_several_gzip_members_are_read_through():
    two = gzip.compress(b"\x00" * 10) + gzip.compress(HEADER.encode())
    got = excerpt(two)
    assert got is not None and got.binary_before and got.text.startswith("@HD")


def test_never_more_than_the_cap_is_decoded():
    calls = []
    real = zlib.decompressobj

    class Watching:
        def __init__(self, *a):
            self.inner = real(*a)

        def decompress(self, data, max_length=0):
            calls.append(max_length)
            return self.inner.decompress(data, max_length)

        def __getattr__(self, name):
            return getattr(self.inner, name)

    import mendel_api.services.characterise as c

    c.zlib.decompressobj = Watching
    try:
        excerpt(gzip.compress(b"a" * (5 * 2**20)))
    finally:
        c.zlib.decompressobj = real
    assert calls and all(0 < n <= DECODED_CAP for n in calls)
```

- [x] **Step 2: Run them to verify they fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_characterise_excerpt.py -q`
Expected: FAIL with `ModuleNotFoundError: mendel_api.services.characterise`.

- [x] **Step 3: Implement**

```python
"""The characteriser (14.7.7): what a model is shown of a sample, whether one may read it, and
the reading itself.

**The excerpt is the smallest thing that can leave** (spec §5): the first stretch of readable
text in the decoded head, at most 8 KB and 200 lines. Nothing here writes it anywhere; the job
that carries it to the worker keeps no result.
"""

import zlib
from typing import NamedTuple

from comeni_core.spell.marks import EXCERPT_BYTES, EXCERPT_LINES

DECODED_CAP = 64 * 1024
"""The most decompressed before looking for text, so a bomb costs 64 KB (spec §5)."""
MIN_TEXT = 200
"""Fewer readable bytes than this in a row, and there is nothing worth sending."""
_GZIP = b"\x1f\x8b"


class Excerpt(NamedTuple):
    text: str
    binary_before: bool
    """Binary bytes came before the text: a BAM's header, not a SAM file."""


def _decoded(head: bytes) -> bytes:
    """The head, gunzipped when its first bytes say gzip — through every member, never past
    `DECODED_CAP`, and as far as a truncated member goes."""
    if not head.startswith(_GZIP):
        return head[:DECODED_CAP]
    out = bytearray()
    rest = head
    while rest.startswith(_GZIP) and len(out) < DECODED_CAP:
        member = zlib.decompressobj(wbits=31)
        try:
            out += member.decompress(rest, DECODED_CAP - len(out))
        except zlib.error:
            break
        if not member.eof:
            break  # truncated, or the cap reached
        rest = member.unused_data
    return bytes(out)


def _texty(byte: int) -> bool:
    return byte in (9, 10, 13) or 32 <= byte < 127 or byte >= 128


def _first_text(data: bytes) -> tuple[int, bytes] | None:
    start = None
    for i, byte in enumerate(data):
        if _texty(byte):
            if start is None:
                start = i
        else:
            if start is not None and i - start >= MIN_TEXT:
                return start, data[start:i]
            start = None
    if start is not None and len(data) - start >= MIN_TEXT:
        return start, data[start:]
    return None


def _bounded(text: bytes) -> str:
    """Whole lines while they fit; a first line longer than the bound is cut at it."""
    kept, size = [], 0
    for line in text.splitlines(keepends=True)[:EXCERPT_LINES]:
        if size + len(line) > EXCERPT_BYTES:
            if not kept:
                kept.append(line[:EXCERPT_BYTES])
            break
        kept.append(line)
        size += len(line)
    decoded = b"".join(kept).decode("utf-8", errors="ignore")
    while len(decoded.encode()) > EXCERPT_BYTES:  # never, with `ignore`; the bound is the type's
        decoded = decoded[:-1]
    return decoded


def excerpt(head: bytes) -> Excerpt | None:
    """What a model may be shown of a sample's head, or `None`: nothing worth sending."""
    found = _first_text(_decoded(head))
    if found is None:
        return None
    start, text = found
    return Excerpt(text=_bounded(text), binary_before=start > 0)
```

- [x] **Step 4: Run them to verify they pass**

Run the Step 2 command.
Expected: PASS. If `test_many_lines_are_cut_at_the_line_bound` gets fewer than 200 lines, the byte bound came first; lengthen nothing and shorten the test's line instead. The bounds are the spec's.

- [x] **Step 5: Check, then commit**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel make check`

```bash
git add packages/mendel-api/src/mendel_api/services/characterise.py packages/mendel-api/tests/test_characterise_excerpt.py
git commit -m "feat(api): the excerpt — readable text from a sample's head, gzip by its bytes, bounded (#135)"
```

---

### Task 2: A reading on the question, and the upload offered where the AI can read

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py` (`Question`, about line 287)
- Modify: `packages/mendel-api/src/mendel_api/services/characterise.py` (`available()`)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring.py` (`_words_coming` ~234; `read()` ~223; `_gap_options` ~1399; `_sample_refusal` ~1980; new `start_reading`, `reading_failed`)
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (MI0215, after MI0214)
- Test: `packages/mendel-api/tests/test_characterise_reading.py` (new)

**Interfaces:**
- Produces:
  - `types.SampleReading(state: Literal["pending", "read", "could_not_tell", "refused", "no_answer", "hand_back", "handed"], attempt: int = 1, started_at: datetime | None = None, type_id: str | None = None, states: list[str] = [], recorded: list[str] = [], kept: list[str] = [], disagreed: list[str] = [], code: str | None = None)`;
  - `Question.reading: SampleReading | None = None`;
  - `characterise.available() -> bool`;
  - `authoring.start_reading(proposal_id: str) -> int` (the attempt, from 1);
  - `authoring.reading_failed(proposal_id: str, attempt: int, state: str, code: str | None) -> None`;
  - `authoring.reading_of(proposal_id: str) -> SampleReading | None`;
  - `authoring.STALE_AFTER` (seconds).

- [x] **Step 1: Write the failing tests**

Create `packages/mendel-api/tests/test_characterise_reading.py`:

```python
"""A reading on a question (14.7.7): started, waited on, refused while out, aged, offered."""

from datetime import UTC, datetime, timedelta

import pytest
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal
from mendel_api.services import authoring, characterise
from test_authoring_samples import (  # noqa: F401
    _database_is_reachable,
    _gathering,
    _payload,
    _pending_for,
    clean,
)

pytestmark = pytest.mark.skipif(not _database_is_reachable(), reason="no database")


@pytest.fixture
def readable(monkeypatch):
    """Level 0 and a model configured: the characteriser is available."""
    monkeypatch.setattr(characterise, "available", lambda: True)


def _at(subject):
    sid = _gathering(["counts.matrix"])
    return sid, _pending_for(sid, subject)


def test_an_input_nothing_reads_offers_an_upload_when_the_ai_can_read(clean, readable):
    _, pid = _at("genome.fasta")
    assert "upload" in _payload(pid)["options"]


def test_without_the_ai_an_input_nothing_reads_offers_no_upload(clean, monkeypatch):
    monkeypatch.setattr(characterise, "available", lambda: False)
    _, pid = _at("genome.fasta")
    assert "upload" not in _payload(pid)["options"]


def test_a_reading_is_pending_on_the_question_and_keeps_the_poll_running(clean, readable):
    sid, pid = _at("genome.fasta")
    assert authoring.start_reading(pid) == 1
    picture = authoring.read(sid)
    assert picture["pending_proposal"]["payload"]["block"]["reading"]["state"] == "pending"
    assert picture["usage"]["in_flight"]


def test_a_second_upload_while_one_is_read_is_refused(clean, readable):
    _, pid = _at("genome.fasta")
    authoring.start_reading(pid)
    with pytest.raises(ValueError, match="MI0215"):
        authoring.check_sample_question(pid)


def test_a_reading_older_than_the_job_could_run_reads_as_no_answer(clean, readable):
    sid, pid = _at("genome.fasta")
    authoring.start_reading(pid)
    with session_scope() as db:
        row = db.get(PipelineAuthoringProposal, pid)
        payload = dict(row.payload)
        block = dict(payload["block"])
        old = datetime.now(UTC) - timedelta(seconds=authoring.STALE_AFTER + 1)
        block["reading"] = {**block["reading"], "started_at": old.isoformat()}
        payload["block"] = block
        row.payload = payload
    reading = authoring.read(sid)["pending_proposal"]["payload"]["block"]["reading"]
    assert reading["state"] == "no_answer"
    authoring.check_sample_question(pid)  # and the person may try again


def test_a_failed_reading_says_so_and_frees_the_question(clean, readable):
    sid, pid = _at("genome.fasta")
    attempt = authoring.start_reading(pid)
    authoring.reading_failed(pid, attempt, "no_answer", "MA0007")
    reading = authoring.reading_of(pid)
    assert reading.state == "no_answer" and reading.code == "MA0007"
    assert authoring.start_reading(pid) == 2


def test_a_late_failure_for_an_old_attempt_changes_nothing(clean, readable):
    _, pid = _at("genome.fasta")
    authoring.start_reading(pid)
    authoring.reading_failed(pid, 1, "no_answer", "MA0007")
    authoring.start_reading(pid)
    authoring.reading_failed(pid, 1, "refused", "MI0204")
    assert authoring.reading_of(pid).state == "pending"


def test_available_needs_the_level_and_a_model(monkeypatch):
    from mendel_api.services import protection
    import mendel_api.settings as s

    monkeypatch.setattr(protection, "allows", lambda crossing: True)
    monkeypatch.setattr(s, "model_access", lambda *a, **k: None)
    assert not characterise.available()
    monkeypatch.setattr(s, "model_access", lambda *a, **k: object())
    assert characterise.available()
    monkeypatch.setattr(protection, "allows", lambda crossing: False)
    assert not characterise.available()
```

- [x] **Step 2: Run them to verify they fail**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest packages/mendel-api/tests/test_characterise_reading.py -q`
Expected: FAIL (`available` and `start_reading` do not exist).

- [x] **Step 3: Declare MI0215**

In `diagnostics.yml`, after MI0214:

```yaml
MI0215:
  emitted_by: api
  concern: workflow
  says: "a sample is already being read for this question"
  fires_on: [authoring]
  refuses: true
  fix: |
    Wait for the AI's reading to arrive on the card. If it says the AI didn't answer, measure
    again.
  explanation: |
    A sample nothing here reads is read by the AI on the AI worker, which takes a while. One
    reading per question at a time keeps two answers from racing, as a sample being measured
    holds the question's other answers.
```

Run `uv run python tools/generate_diagnostics_doc.py`.

- [x] **Step 4: Implement**

`types.py`, before `Question`:

```python
class SampleReading(_Shape):
    """The AI reading a sample nothing here reads (14.7.7), as the question's card shows it.

    `pending` while the job is out; `read` when what it admitted was recorded; `could_not_tell`
    when it named no family or no type; `refused` when an id it named is undeclared (`code`);
    `no_answer` when no model answered, or the job never came back; `hand_back` when it named a
    type the engine reads, so the browser sends the file again; `handed` once it has.
    `attempt` keys the job, so a retry is a new job and a late answer to an old one is ignored.
    """

    state: Literal[
        "pending", "read", "could_not_tell", "refused", "no_answer", "hand_back", "handed"
    ]
    attempt: int = 1
    started_at: datetime | None = None
    type_id: str | None = None
    states: list[str] = []
    recorded: list[str] = []
    kept: list[str] = []
    disagreed: list[str] = []
    code: str | None = None
```

(import `datetime` from `datetime`). In `Question`, after `phrasing`:

```python
    reading: SampleReading | None = None
    """The AI reading a sample for this question (14.7.7). The page keeps its one poll running
    while it is `pending`."""
```

`characterise.py`:

```python
def available() -> bool:
    """Whether a model may read a sample here: the level allows it, and a model answers it.
    The one seam a test replaces."""
    from mendel_api.services import protection
    from mendel_api.settings import model_access

    return (
        protection.allows(protection.Crossing.CHARACTERISE)
        and model_access("builder", "characterise") is not None
    )
```

`authoring.py`:

1. `_gap_options`, the input branch. Replace `if gap.subject in read:` with:

```python
        # A sample nothing here reads is read by the AI (14.7.7), so the upload is offered
        # wherever the AI may read one — not only where a format reads the type.
        if gap.subject in read or _characterisable():
```

and add beside `_model_configured`:

```python
def _characterisable() -> bool:
    """Whether the AI may read a sample here (14.7.7). The seam is `characterise.available`."""
    from mendel_api.services import characterise

    return characterise.available()
```

2. `STALE_AFTER` and the reading helpers, after `answer_with_sample`:

```python
STALE_AFTER = settings.ai_job_timeout_seconds + 60
"""A reading older than the job could run reads as `no_answer` (ruling 4 of 14.7.7.2's plan):
a worker killed mid-job never writes back, and the card must not wait forever."""


def _reading(block: dict) -> dict | None:
    reading = block.get("reading")
    if not reading or reading.get("state") != "pending" or not reading.get("started_at"):
        return reading
    started = datetime.fromisoformat(reading["started_at"])
    if (_now() - started).total_seconds() > STALE_AFTER:
        return {**reading, "state": "no_answer", "code": "MA0007"}
    return reading


def _set_reading(db, proposal, reading: SampleReading | None) -> None:
    payload = dict(proposal.payload)
    block = dict(payload["block"])
    block["reading"] = None if reading is None else reading.model_dump(mode="json")
    payload["block"] = block
    proposal.payload = payload


def reading_of(proposal_id: str) -> SampleReading | None:
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        found = _reading((proposal.payload or {}).get("block") or {}) if proposal else None
    return None if found is None else SampleReading.model_validate(found)


def start_reading(proposal_id: str) -> int:
    """Mark the question as being read by the AI; the attempt that keys the job."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id, with_for_update=True)
        if proposal is None:
            raise KeyError(proposal_id)
        before = (proposal.payload.get("block") or {}).get("reading") or {}
        attempt = int(before.get("attempt", 0)) + 1
        _set_reading(
            db, proposal, SampleReading(state="pending", attempt=attempt, started_at=_now())
        )
    return attempt


def reading_failed(proposal_id: str, attempt: int, state: str, code: str | None) -> None:
    """End a reading without recording anything, if it is still this attempt's."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id, with_for_update=True)
        if proposal is None:
            return
        reading = (proposal.payload.get("block") or {}).get("reading") or {}
        if reading.get("attempt") != attempt or reading.get("state") != "pending":
            return
        _set_reading(
            db, proposal,
            SampleReading.model_validate({**reading, "state": state, "code": code}),
        )
```

(`_now()` exists in this module; import `settings` from `mendel_api.settings` and `SampleReading` from `mendel_api.authoring.types`. If `_now()` returns a naive datetime, compare like with like: use it on both sides.)

3. `_sample_refusal`: before the `return st.settle(…)`, add:

```python
    reading = _reading((proposal.payload or {}).get("block") or {}) or {}
    if reading.get("state") == "pending":
        return coded("MI0215", "a sample is already being read for this question")
```

4. `_words_coming`: return also `True` when `_reading(block)` is pending:

```python
    reading = _reading(block) or {}
    return (
        block.get("phrasing") == "pending"
        or bool(block.get("readback_pending"))
        or reading.get("state") == "pending"
    )
```

5. `read()`: in `"pending_proposal"`, show an aged reading as it reads. Replace `"payload": pending.payload,` with `"payload": _aged(pending.payload),` and add:

```python
def _aged(payload: dict) -> dict:
    """The payload with a reading the job never finished shown as `no_answer` (nothing written)."""
    block = payload.get("block") or {}
    if not block.get("reading"):
        return payload
    return {**payload, "block": {**block, "reading": _reading(block)}}
```

- [x] **Step 5: Run them to verify they pass**

Run the Step 2 command, then `MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api -q`.
Expected: PASS. If an existing test asserts an input gap's options exactly, that test ran with no model: `characterise.available()` is false there, and the options are unchanged. If one fails, it had a model configured; monkeypatch `available` to `False` in it and say why in a comment.

- [x] **Step 6: Check, then commit**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel make check`

```bash
git add packages/mendel-api packages/comeni-core/src/comeni_core/diagnostics.yml docs/handbook/reference/diagnostics.md
git commit -m "feat(api): a reading on the question — pending, refused while out, aged; the upload offered where the AI reads (#135)"
```

---

### Task 3: Recording what the AI read

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/authoring.py` (`answer_with_sample` ~2006; new `_record_found`, `answer_with_reading`)
- Test: `packages/mendel-api/tests/test_characterise_reading.py`

**Interfaces:**
- Consumes: `CharacteriseReply` (plan 1); `SampleReading`, `start_reading` (Task 2).
- Produces: `authoring.answer_with_reading(proposal_id: str, attempt: int, reply: CharacteriseReply, *, by: str, handed_back: bool) -> SampleAnswer | None`. `None` means the attempt is no longer current and nothing was recorded. `handed_back=True` records nothing and sets the reading to `hand_back` with the type.

- [x] **Step 1: Write the failing tests**

Append to `test_characterise_reading.py`:

```python
from mendel_api.authoring.types import CharacteriseReply, ReadMeasurement


def _facts(sid):
    with session_scope() as db:
        from mendel_api.models import PipelineAuthoringSession
        return list(db.get(PipelineAuthoringSession, sid).facts)


def test_a_reading_answers_an_input_gap_and_is_marked_read_by_ai(clean, readable):
    sid, pid = _at("genome.fasta")
    attempt = authoring.start_reading(pid)
    answer = authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="genome.fasta"), by="ana", handed_back=False
    )
    assert answer.recorded == ["genome.fasta"]
    fact = next(f for f in _facts(sid) if f["subject"] == "genome.fasta")
    assert fact["source"] == "model_read" and fact["kind"] == "input"
    assert authoring.pending_id(sid) != pid, "the gap closed"


def test_a_reading_of_another_type_is_recorded_and_the_question_stays(clean, readable):
    sid, pid = _at("genome.fasta")
    attempt = authoring.start_reading(pid)
    reply = CharacteriseReply(type_id="alignment.bam", states=["coordinate_sorted"])
    answer = authoring.answer_with_reading(pid, attempt, reply, by="ana", handed_back=False)
    assert answer.recorded == ["alignment.bam"]
    bam = next(f for f in _facts(sid) if f["subject"] == "alignment.bam")
    assert bam["states"] == ["coordinate_sorted"] and bam["source"] == "model_read"
    assert authoring.pending_id(sid) == pid
    reading = authoring.reading_of(pid)
    assert reading.state == "read" and reading.recorded == ["alignment.bam"]


def test_the_persons_word_stands_over_a_reading(clean, readable):
    sid, pid = _at("paired")
    from mendel_api.models import PipelineAuthoringSession
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        row.facts = [*row.facts, {"kind": "measurement", "subject": "quality_encoding",
                                  "value": "phred33", "source": "person_said"}]
    attempt = authoring.start_reading(pid)
    reply = CharacteriseReply(
        type_id="fastq.reads",
        measurements=[ReadMeasurement(id="quality_encoding", value="phred64")],
    )
    answer = authoring.answer_with_reading(pid, attempt, reply, by="ana", handed_back=False)
    assert answer.disagreed == ["quality_encoding"]
    said = next(f for f in _facts(sid) if f["subject"] == "quality_encoding")
    assert said["value"] == "phred33"


def test_a_type_the_engine_reads_is_handed_back_and_nothing_is_recorded(clean, readable):
    sid, pid = _at("genome.fasta")
    before = _facts(sid)
    attempt = authoring.start_reading(pid)
    answer = authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="fastq.reads"), by="ana", handed_back=True
    )
    assert answer is not None and answer.recorded == []
    assert _facts(sid) == before
    reading = authoring.reading_of(pid)
    assert reading.state == "hand_back" and reading.type_id == "fastq.reads"


def test_a_reading_for_an_old_attempt_records_nothing(clean, readable):
    sid, pid = _at("genome.fasta")
    authoring.start_reading(pid)
    authoring.reading_failed(pid, 1, "no_answer", "MA0007")
    authoring.start_reading(pid)
    late = authoring.answer_with_reading(
        pid, 1, CharacteriseReply(type_id="genome.fasta"), by="ana", handed_back=False
    )
    assert late is None and authoring.pending_id(sid) == pid


def test_a_reading_after_the_question_was_answered_by_a_click_records_nothing(clean, readable):
    sid, pid = _at("genome.fasta")
    attempt = authoring.start_reading(pid)
    authoring.answer_gap(pid, "have_it", None, by="ana")
    late = authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="genome.fasta"), by="ana", handed_back=False
    )
    assert late is None
```

If `answer_gap` refuses because the reading is pending (MI0215 now guards samples only, not clicks, so it should not), keep the test: a click while the AI reads is allowed, and the reading then lands on a settled question and is ignored.

- [x] **Step 2: Run them to verify they fail**

Run: `MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api/tests/test_characterise_reading.py -q`
Expected: the new tests FAIL (`answer_with_reading` does not exist).

- [x] **Step 3: Extract the shared recording, then use it twice**

In `answer_with_sample`, the block from `decided = {…}` to the `_swap(…)` call records an input and measurements. Move it into:

```python
class _Found(NamedTuple):
    measurement: str
    value: object
    pieces: list[str] = []
    evidence: dict | None = None


def _record_found(
    db, proposal, row, *, type_id: str | None, states: list[str], found: list[_Found],
    source: FactSource, by: str, stack,
) -> tuple[list[str], list[str], list[str], bool]:
    """Record a sample's type and facts as `source`, the person's word standing; settle the
    proposal when its subject was recorded. Returns `(recorded, kept, disagreed, answered)`."""
    session_id = proposal.session_id
    subject = proposal.payload["subject"]
    decided = {f.measurement for f in found if f.value is not None}
    facts = [
        f
        for f in row.facts or []
        if not (f.get("source") == FactSource.OPEN.value and f["subject"] in decided)
    ]
    known = {f["subject"]: f for f in facts}
    recorded, kept, disagreed = [], [], []
    if type_id:
        if type_id in known:
            kept.append(type_id)
        else:
            facts.append(
                Fact(kind=FactKind.INPUT, subject=type_id, states=sorted(states), source=source)
                .model_dump(mode="json")
            )
            recorded.append(type_id)
    for item in found:
        if item.value is None:
            continue
        try:
            stack.measurements.check(item.measurement, item.value)
        except (ValueError, KeyError):
            continue
        if item.measurement in known:
            kept.append(item.measurement)
            if known[item.measurement].get("value") != item.value:
                disagreed.append(item.measurement)
            continue
        facts.append(
            Fact(
                kind=FactKind.MEASUREMENT,
                subject=item.measurement,
                value=item.value,
                source=source,
                pieces=item.pieces,
                evidence=_counts(item.evidence or {}) or None,
            ).model_dump(mode="json")
        )
        recorded.append(item.measurement)
    answered = subject in recorded
    target = Phase(row.phase)
    if answered:
        proposal.state = ProposalState.ACCEPTED.value
        proposal.by = by
        proposal.chosen_option = UPLOAD
        proposal.settled_at = _now()
        target = st.advance(target, st.Event.FACT_ADDED)
    if answered or facts != (row.facts or []):
        _swap(db, session_id, row.row_version, phase=target, facts=facts)
    return recorded, kept, disagreed, answered
```

Rewrite `answer_with_sample`'s body to call it:

```python
        row = db.get(PipelineAuthoringSession, proposal.session_id)
        measured = inspection.outcome == "measured"
        found = [
            _Found(f.measurement, f.value, f.pieces, f.evidence)
            for f in (inspection.facts if measured else [])
            if f.undetermined is None
        ]
        recorded, kept, disagreed, answered = _record_found(
            db, proposal, row,
            type_id=inspection.type_id if measured else None, states=[], found=found,
            source=FactSource.MEASURED, by=by, stack=stack,
        )
        session_id = proposal.session_id
```

**Run the existing sample tests now, before adding anything:**
`MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api/tests/test_authoring_samples.py packages/mendel-api/tests/test_authoring_upload_route.py -q`
Expected: PASS, unchanged. The extraction must move nothing.

Then add `answer_with_reading`:

```python
def answer_with_reading(
    proposal_id: str, attempt: int, reply, *, by: str, handed_back: bool
) -> SampleAnswer | None:
    """What the AI read of a sample, recorded as *read by AI* (14.7.7), or handed back.

    `None` when the reading is no longer this attempt's or the question was settled meanwhile:
    a late answer records nothing. `handed_back`: the type is one the engine reads, so nothing
    is recorded and the browser sends the file again (spec §8).
    """
    stack = registry.stack()
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id, with_for_update=True)
        if proposal is None or proposal.state != ProposalState.PENDING.value:
            return None
        reading = (proposal.payload.get("block") or {}).get("reading") or {}
        if reading.get("attempt") != attempt or reading.get("state") != "pending":
            return None
        row = db.get(PipelineAuthoringSession, proposal.session_id)
        session_id = proposal.session_id
        if handed_back:
            _set_reading(db, proposal, SampleReading(
                state="hand_back", attempt=attempt, type_id=reply.type_id,
                states=list(reply.states),
            ))
            recorded, kept, disagreed, answered = [], [], [], False
        else:
            found = [_Found(m.id, m.value) for m in reply.measurements]
            recorded, kept, disagreed, answered = _record_found(
                db, proposal, row, type_id=reply.type_id, states=list(reply.states),
                found=found, source=FactSource.MODEL_READ, by=by, stack=stack,
            )
            if not answered:
                _set_reading(db, proposal, SampleReading(
                    state="read", attempt=attempt, type_id=reply.type_id,
                    states=list(reply.states), recorded=recorded, kept=kept,
                    disagreed=disagreed,
                ))
    if answered:
        offer_next_gap(session_id)
    return SampleAnswer(
        phase=current_phase(session_id), recorded=recorded, kept=kept, disagreed=disagreed
    )
```

- [x] **Step 4: Run them to verify they pass**

Run the Step 2 command, then the whole `packages/mendel-api` suite.
Expected: PASS.

- [x] **Step 5: Check, then commit**

```bash
git add packages/mendel-api
git commit -m "feat(api): what the AI read is recorded as read by AI, the person's word standing; a type the engine reads is handed back (#135)"
```

---

### Task 4: The job

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/characterise.py` (`read_sample`)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_jobs.py`
- Modify: `packages/mendel-api/src/mendel_api/ai_worker.py`
- Modify: `packages/mendel-api/tests/test_forge_jobs.py:689-726`, `packages/mendel-api/tests/test_authoring_routes.py:426-434`
- Test: `packages/mendel-api/tests/test_characterise_reading.py`

**Interfaces:**
- Consumes: `authoring_ai.compose_characterise`, `characterise_families`, `characterise` (plan 1); `answer_with_reading`, `reading_failed` (Tasks 2–3); `authoring._inspectable(stack)` (existing: `(measured, read)`).
- Produces:
  - `characterise.read_sample(session_id: str, proposal_id: str, attempt: int, text: str, binary_before: bool, *, client_for) -> str`, which returns the reading's final state. `client_for(purpose) -> Client | None` is `authoring_jobs._client`.
  - `authoring_jobs.CHARACTERISE = "characterise_sample"`;
  - `authoring_jobs.enqueue_characterise(session_id, proposal_id, attempt, excerpt: characterise.Excerpt) -> bool`;
  - `async authoring_jobs.characterise_sample(ctx, session_id, proposal_id, attempt, text, binary_before) -> str`.

- [x] **Step 1: Write the failing tests**

Append to `test_characterise_reading.py`:

```python
import json

from comeni_ai import Client, ModelAccess, ModelUnavailableError
from mendel_api.services import protection


class _Answers:
    def __init__(self, *bodies):
        self.bodies, self.sent = list(bodies), []

    def send(self, access, prompt):
        self.sent.append(prompt)
        body = self.bodies.pop(0)
        if isinstance(body, Exception):
            raise body
        return body


def _clients(*bodies):
    answers = _Answers(*bodies)
    client = Client(ModelAccess(model="fake/test", base_url="http://localhost:1"),
                    transport=answers)
    return (lambda purpose: client), answers


FASTA = ">chr1 a reference\n" + "ACGT" * 60 + "\n"


def _read(pid, sid, *bodies):
    client_for, answers = _clients(*bodies)
    attempt = authoring.start_reading(pid)
    state = characterise.read_sample(sid, pid, attempt, FASTA, False, client_for=client_for)
    return state, answers


def test_the_job_reads_families_then_the_type_and_records_it(clean, readable):
    sid, pid = _at("genome.fasta")
    state, answers = _read(
        pid, sid,
        json.dumps({"families": ["genome"]}),
        json.dumps({"type_id": "genome.fasta", "states": [], "measurements": [],
                    "undetermined": [], "unmatched": []}),
    )
    assert state == "read" and len(answers.sent) == 2
    assert authoring.pending_id(sid) != pid


def test_no_family_ends_as_could_not_tell_with_one_call(clean, readable):
    sid, pid = _at("genome.fasta")
    state, answers = _read(pid, sid, json.dumps({"families": []}))
    assert state == "could_not_tell" and len(answers.sent) == 1
    assert authoring.reading_of(pid).state == "could_not_tell"


def test_an_undeclared_id_ends_as_refused_with_its_code(clean, readable):
    sid, pid = _at("genome.fasta")
    _read(pid, sid, json.dumps({"families": ["variants"]}))
    reading = authoring.reading_of(pid)
    assert reading.state == "refused" and reading.code == "MI0204"


def test_a_provider_that_does_not_answer_ends_as_no_answer(clean, readable):
    sid, pid = _at("genome.fasta")
    state, _ = _read(pid, sid, ModelUnavailableError("down"))
    assert state == "no_answer" and authoring.reading_of(pid).code == "MA0007"


def test_a_type_the_engine_reads_is_handed_back(clean, readable):
    sid, pid = _at("genome.fasta")
    state, _ = _read(
        pid, sid,
        json.dumps({"families": ["fastq"]}),
        json.dumps({"type_id": "fastq.reads", "states": [], "measurements": [],
                    "undetermined": [], "unmatched": []}),
    )
    assert state == "hand_back"


def test_above_level_0_door_6_refuses_before_composing(clean, readable, monkeypatch):
    sid, pid = _at("genome.fasta")
    monkeypatch.setattr(protection, "allows", lambda crossing: False)
    state, answers = _read(pid, sid, json.dumps({"families": ["genome"]}))
    assert state == "refused" and answers.sent == []
    assert authoring.reading_of(pid).code == "MI0213"


def test_a_stale_delivery_spends_no_call(clean, readable):
    sid, pid = _at("genome.fasta")
    client_for, answers = _clients(json.dumps({"families": ["genome"]}))
    authoring.start_reading(pid)
    authoring.reading_failed(pid, 1, "no_answer", "MA0007")
    characterise.read_sample(sid, pid, 1, FASTA, False, client_for=client_for)
    assert answers.sent == []


def test_with_the_family_step_off_one_call_reads_the_type(clean, readable, monkeypatch):
    from mendel_api.settings import settings
    monkeypatch.setattr(settings, "family_step_from", 10_000)
    sid, pid = _at("genome.fasta")
    state, answers = _read(
        pid, sid,
        json.dumps({"type_id": "genome.fasta", "states": [], "measurements": [],
                    "undetermined": [], "unmatched": []}),
    )
    assert state == "read" and len(answers.sent) == 1


def test_the_job_keeps_no_result_so_the_excerpt_leaves_redis_with_it():
    from mendel_api import ai_worker
    from mendel_api.services import authoring_jobs

    [entry] = [f for f in ai_worker.AIWorkerSettings.functions
               if getattr(f, "name", None) == authoring_jobs.CHARACTERISE]
    assert entry.keep_result == 0
```

In `test_forge_jobs.py` and `test_authoring_routes.py`, wherever a test reads `f.__name__` or `f.__code__` from a worker's `functions`, unwrap first with `fn = getattr(f, "coroutine", f)`. That makes `test_the_two_worker_function_lists_are_disjoint` and the stub test read a `Function` correctly.

- [x] **Step 2: Run them to verify they fail**

Run: `MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api/tests/test_characterise_reading.py -q`
Expected: the new tests FAIL (`read_sample`, `CHARACTERISE`).

- [x] **Step 3: Implement the reading**

In `characterise.py`:

```python
def read_sample(
    session_id: str, proposal_id: str, attempt: int, text: str, binary_before: bool, *,
    client_for,
) -> str:
    """Read one sample through door 6: families, then the type; record what was admitted.
    **Never raises for a refusal**; every way out is a reading state the card shows. Returns it.
    """
    from mendel_api import identity
    from mendel_api.services import authoring, authoring_ai, protection, registry
    from mendel_api.settings import settings

    current = authoring.reading_of(proposal_id)
    if current is None or current.attempt != attempt or current.state != "pending":
        return "stale"
    if not protection.allows(protection.Crossing.DOOR_6):
        refusal = protection.refuse(protection.Crossing.DOOR_6)
        authoring.reading_failed(proposal_id, attempt, "refused", "MI0213")
        return "refused"

    stack = registry.stack()
    request = authoring_ai.compose_characterise(
        text, binary_before=binary_before, registry=registry.digest()
    )
    families = None
    if len(stack.vocabulary.types) >= settings.family_step_from:
        first = authoring_ai.characterise_families(
            request, stack=stack, session_id=session_id,
            client=client_for(authoring_ai.Purpose.CHARACTERISE_FAMILY),
        )
        if not first.admitted:
            return _failed(proposal_id, attempt, first)
        if not first.reply.families:
            authoring.reading_failed(proposal_id, attempt, "could_not_tell", None)
            return "could_not_tell"
        families = first.reply.families
    second = authoring_ai.characterise(
        request, stack=stack, families=families, session_id=session_id,
        client=client_for(authoring_ai.Purpose.CHARACTERISE),
    )
    if not second.admitted:
        return _failed(proposal_id, attempt, second)
    if second.reply.type_id is None:
        authoring.reading_failed(proposal_id, attempt, "could_not_tell", None)
        return "could_not_tell"
    _, read_by_engine = authoring._inspectable(stack)
    handed = second.reply.type_id in read_by_engine
    authoring.answer_with_reading(
        proposal_id, attempt, second.reply, by=identity.default_author(), handed_back=handed
    )
    return "hand_back" if handed else "read"


_NO_ANSWER = frozenset({"MI0106", "MA0002", "MA0003", "MA0007"})


def _failed(proposal_id: str, attempt: int, outcome) -> str:
    from mendel_api.services import authoring

    state = "no_answer" if outcome.code in _NO_ANSWER or outcome.code is None else "refused"
    authoring.reading_failed(proposal_id, attempt, state, outcome.code)
    return state
```

Drop the unused `refusal` local if the linter flags it. `protection.refuse` is only needed for the log; `reading_failed` carries the code.

`authoring_jobs.py`:

```python
CHARACTERISE = "characterise_sample"
```

Add it to `AI_JOBS`, and after `enqueue_phrasing`:

```python
async def enqueue_characterise(session_id: str, proposal_id: str, attempt: int, excerpt) -> bool:
    """Queue the AI reading a sample (14.7.7). **The excerpt rides in the job's arguments**,
    in Redis until the worker takes it, and the job keeps no result (`ai_worker`). Keyed on the
    attempt, so a retry is a new job and a double delivery of one is the same."""
    return await jobs.enqueue(
        CHARACTERISE,
        session_id,
        proposal_id,
        attempt,
        excerpt.text,
        excerpt.binary_before,
        job_id=jobs.job_id_for("builder", "characterise", proposal_id, str(attempt)),
        queue=jobs.AI_QUEUE,
    )


async def characterise_sample(
    ctx: dict, session_id: str, proposal_id: str, attempt: int, text: str, binary_before: bool
) -> str:
    """Read a sample nothing here reads, through door 6 (14.7.7). A failure is a reading state."""
    from mendel_api.services import characterise

    state = characterise.read_sample(
        session_id, proposal_id, attempt, text, binary_before, client_for=_client
    )
    return f"{proposal_id}:{attempt}:{state}"
```

`ai_worker.py`: `from arq.worker import func`, and in `functions` after `read_back_authoring_goal`:

```python
        # The characteriser (14.7.7) crosses door 6 carrying part of a person's file. **It keeps
        # no result**: ARQ stores a job's arguments with its result, and the excerpt must leave
        # Redis when the job does.
        func(authoring_jobs.characterise_sample, keep_result=0),
```

- [x] **Step 4: Run them to verify they pass**

Run the Step 2 command, then `MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api -q`.
Expected: PASS. `test_the_two_worker_function_lists_are_disjoint` now also holds `characterise_sample` to `authoring_jobs.AI_JOBS`.

- [x] **Step 5: Check, then commit**

```bash
git add packages/mendel-api
git commit -m "feat(api): the characteriser's job — two calls through door 6, every way out a reading state, no result kept (#135)"
```

---

### Task 5: The upload starts a reading, and takes a hand-back

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/inspect.py` (`match` ~116, `inspect_sample` ~177)
- Modify: `packages/mendel-api/src/mendel_api/routes/authoring.py` (`SampleInspected` ~615, `upload_sample` ~663)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring.py` (`ai_for` ~1298; `end_hand_back`)
- Test: `packages/mendel-api/tests/test_inspect.py`, `packages/mendel-api/tests/test_authoring_upload_route.py`

**Interfaces:**
- Consumes: `characterise.excerpt`, `characterise.available`, `authoring.start_reading`, `authoring.reading_of`, `authoring_jobs.enqueue_characterise`.
- Produces:
  - `inspect.match(names, pieces, claimed: str | None = None)`;
  - `inspect.inspect_sample(files, stack, claimed: str | None = None)`;
  - `SampleInspected.outcome` gains `"reading"`;
  - `authoring.end_hand_back(proposal_id: str, *, confirmed: bool) -> None`.

- [x] **Step 1: Write the failing tests**

In `test_inspect.py`, using its existing catalogue fixture (read the file first; use the same `pieces`/`stack` it builds):

```python
def test_a_type_recorded_for_the_file_claims_it_when_no_extension_does(pieces):
    codec, formats = inspect.match(["reads.txt"], pieces, claimed="fastq.reads")
    assert [f.id for f in formats] == ["fastq"] and codec is None


def test_a_gzipped_file_keeps_its_codec_when_claimed_by_type(pieces):
    codec, formats = inspect.match(["reads.txt.gz"], pieces, claimed="fastq.reads")
    assert codec is not None and codec.id == "gzip" and [f.id for f in formats] == ["fastq"]


def test_without_a_claim_an_unknown_extension_is_claimed_by_nothing(pieces):
    assert inspect.match(["reads.txt"], pieces) == (None, [])
```

In `test_authoring_upload_route.py`:

```python
import gzip
import struct

from mendel_api.services import authoring_jobs, characterise


@pytest.fixture
def readable(monkeypatch):
    monkeypatch.setattr(characterise, "available", lambda: True)
    queued = []

    async def enqueue(session_id, proposal_id, attempt, excerpt):
        queued.append((session_id, proposal_id, attempt, excerpt))
        return True

    monkeypatch.setattr(authoring_jobs, "enqueue_characterise", enqueue)
    return queued


def _bam():
    header = "@HD\tVN:1.6\tSO:coordinate\n" + "@SQ\tSN:chr1\tLN:1000\n" * 20
    return gzip.compress(b"BAM\x01" + struct.pack("<i", len(header)) + header.encode())


@needs_db
def test_a_type_nothing_reads_is_queued_for_the_ai(client, clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    got = _post(client, sid, pid, [("files", ("x.bam", _bam()))])
    assert got.status_code == 200, got.text
    assert got.json()["outcome"] == "reading"
    [(q_sid, q_pid, attempt, excerpt)] = readable
    assert (q_sid, q_pid, attempt) == (sid, pid, 1)
    assert excerpt.binary_before and excerpt.text.startswith("@HD")
    block = got.json()["session"]["pending_proposal"]["payload"]["block"]
    assert block["reading"]["state"] == "pending"


@needs_db
def test_without_the_ai_a_type_nothing_reads_is_as_today(client, clean, monkeypatch):  # noqa: F811
    sid, pid = _at("paired")
    monkeypatch.setattr(characterise, "available", lambda: False)
    got = _post(client, sid, pid, [("files", ("x.bam", _bam()))])
    assert got.json()["outcome"] == "no_inspector"


@needs_db
def test_a_file_with_no_text_is_never_queued(client, clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    got = _post(client, sid, pid, [("files", ("x.bin", bytes(range(256)) * 50))])
    assert got.json()["outcome"] == "no_inspector" and readable == []


@needs_db
def test_a_second_upload_while_reading_is_refused(client, clean, readable):  # noqa: F811
    sid, pid = _at("genome.fasta")
    _post(client, sid, pid, [("files", ("x.bam", _bam()))])
    again = _post(client, sid, pid, [("files", ("x.bam", _bam()))])
    assert again.status_code == 409 and "MI0215" in again.text
    assert len(readable) == 1


@needs_db
def test_a_hand_back_is_claimed_by_the_recorded_type_and_measured(client, clean, readable):  # noqa: F811
    from mendel_api.authoring.types import CharacteriseReply

    sid, pid = _at("paired")
    attempt = authoring.start_reading(pid)
    authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="fastq.reads"), by="ana", handed_back=True
    )
    files = [("files", (p.name.replace(".fq.gz", ".txt.gz"), p.read_bytes()))
             for p in sorted(PAIR.glob("*.gz"))]
    got = _post(client, sid, pid, files)
    assert got.json()["outcome"] == "measured", got.text
    assert "paired" in got.json()["recorded"]


@needs_db
def test_a_browser_cannot_claim_a_type_the_session_did_not_record(client, clean, readable):  # noqa: F811
    sid, pid = _at("paired")
    files = [("files", (p.name.replace(".fq.gz", ".txt.gz"), p.read_bytes()))
             for p in sorted(PAIR.glob("*.gz"))]
    got = client.post(
        f"/api/pipeline/authoring/{sid}/samples",
        data={"proposal_id": pid, "claimed": "fastq.reads"}, files=files,
    )
    assert got.json()["outcome"] != "measured"


@needs_db
def test_a_hand_back_that_fails_the_content_check_drops_the_type(client, clean, readable):  # noqa: F811
    from mendel_api.authoring.types import CharacteriseReply

    sid, pid = _at("paired")
    attempt = authoring.start_reading(pid)
    authoring.answer_with_reading(
        pid, attempt, CharacteriseReply(type_id="fastq.reads"), by="ana", handed_back=True
    )
    got = _post(client, sid, pid, [("files", ("x.txt", b">not a fastq\nACGT\n" * 50))])
    assert got.json()["outcome"] == "unreadable"
    assert authoring.reading_of(pid) is None
```

Read how the route maps a `ValueError` with MI0215 to a status today: `check_sample_question`'s MI0203 maps through the app's coded-error handler. Assert whatever status MI0203 gets in `test_a_sample_on_a_settled_gap_is_refused`, so the two match.

- [x] **Step 2: Run them to verify they fail**

Run: `MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api/tests/test_inspect.py packages/mendel-api/tests/test_authoring_upload_route.py -q`
Expected: the new tests FAIL.

- [x] **Step 3: Claim by type in `inspect`**

In `match`, add the parameter `claimed: str | None = None`, and change the per-file formats line to:

```python
        formats = tuple(
            sorted(f.id for f in pieces.formats.values() if _ends(rest, f.extensions))
        ) or tuple(
            # A hand-back (14.7.7): no extension claims it, and the session recorded the AI
            # naming a type a format reads. The format's `confirms()` still decides.
            sorted(f.id for f in pieces.formats.values() if claimed and claimed in f.reads)
        )
```

In `inspect_sample`, add `claimed: str | None = None` and pass it to `match`. When `claimed` is given, add the step `f"claimed as {claimed}, the type the AI named"` after the first step.

- [x] **Step 4: Start a reading, and take a hand-back, in the route**

`SampleInspected.outcome`: `Literal["measured", "unreadable", "no_inspector", "tie", "reading"]`.

In `upload_sample`, replace the line `inspection = await run_in_threadpool(inspect.inspect_sample, heads.files, registry.stack())` and what follows up to `view = …` with:

```python
    reading = await run_in_threadpool(authoring.reading_of, proposal_id)
    claimed = reading.type_id if reading is not None and reading.state == "hand_back" else None
    inspection = await run_in_threadpool(
        inspect.inspect_sample, heads.files, registry.stack(), claimed
    )
    if claimed is not None:
        await run_in_threadpool(
            authoring.end_hand_back, proposal_id, confirmed=inspection.outcome == "measured"
        )
    if inspection.outcome == "no_inspector" and characterise.available():
        found = characterise.excerpt(heads.files[0][1])
        if found is not None:
            attempt = await run_in_threadpool(authoring.start_reading, proposal_id)
            await authoring_jobs.enqueue_characterise(session_id, proposal_id, attempt, found)
            view = await run_in_threadpool(_view, session_id)
            return SampleInspected(
                outcome="reading", type_id=None, facts=[], reason=None,
                steps=[*inspection.steps, "nothing here reads its type: the AI is reading it"],
                recorded=[], kept=[], disagreed=[], session=view,
            )
    answer = await run_in_threadpool(
        authoring.answer_with_sample, proposal_id, inspection, by=identity.default_author()
    )
```

(import `characterise` with the other services). The browser's own form fields beyond `proposal_id` are never read; `claimed` comes only from `reading_of`.

In `authoring.py`:

```python
def end_hand_back(proposal_id: str, *, confirmed: bool) -> None:
    """After the re-sent file was inspected (spec §8): `handed` when its format confirmed it,
    and the recorded type dropped when not, so nothing the AI said stays."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id, with_for_update=True)
        if proposal is None or proposal.state != ProposalState.PENDING.value:
            return
        reading = (proposal.payload.get("block") or {}).get("reading") or {}
        if reading.get("state") != "hand_back":
            return
        _set_reading(
            db, proposal,
            SampleReading.model_validate({**reading, "state": "handed"}) if confirmed else None,
        )
```

If the proposal was settled by the measured answer, the reading is on a settled proposal's payload. Only a pending one is updated, and that is right.

`ai_for`: when `characterise.available()` is true, `available` gains `AiPoint.CHARACTERISE`. Determine `used` from the draft's session: `ai_for_draft` has the draft id. Add a parameter `characterised: bool = False` to `ai_for`, have `ai_for_draft` pass `any(f.get("source") == "model_read" for f in row.facts or [])` for the session owning the draft, and append `AiPoint.CHARACTERISE` to `used` when true. Add a test beside the existing `ai_for` test (`grep -n "def test.*ai_for" packages/mendel-api/tests/*.py`) asserting a session with a `model_read` fact yields `characterise` in `used`.

- [x] **Step 5: Run them to verify they pass**

Run the Step 2 command, then the whole `packages/mendel-api` suite.
Expected: PASS.

- [x] **Step 6: Mark the branch built**

In `protocol.py`, change each of `door`, `excerpt`, `families`, `types`, `ai_admit`, `ai_stamped`, `hand_back` from `_n(…)` to `_built(…, _G)`, and each new edge from Plan 1 Task 1 to `built=True`. Remove `", at 14.7.7"` from the `claim → door` label. Delete the now-superseded built edge `_e("claim", "nothing", "none", built=True)`: a file no extension claims goes to `door` now, and `door → nothing` and `excerpt → nothing` draw today's outcome. In `PROTOCOL`, mark `read_ai` `_built(…, _P.GATHERING)` and its three edges `built=True`.

In `test_authoring_protocol.py`, rename `test_the_upload_branch_is_built_and_the_characteriser_is_not` to `test_the_upload_branch_and_the_characteriser_are_built` and assert `nodes["read_ai"].built`. Change `test_the_characteriser_is_drawn_step_by_step_and_planned` to assert that every node in `CHARACTERISER` is built. Run the protocol tests and `uv run python tools/generate_protocol_doc.py`, then `--check`.

- [x] **Step 7: Check, then commit**

Run: `MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel make check`

```bash
git add packages/mendel-api docs/design/diagrams
git commit -m "feat(api): an upload nothing reads is read by the AI; a type the engine reads is handed back by the session's record (#135)"
```

Then regenerate the client for plan 3: `make client`. Commit `frontend/src/api/schema.d.ts` and `frontend/openapi.json` in their own commit: `chore(client): reading on the question, the reading outcome (#135)`.

---

## Execution record

Executed 2026-10-04, in one hand. The fixes from plan 1's review (#237) landed first, in c4dc07d7. They include line counting, which `excerpt()` follows: lines are what `\n` separates.

- **Task 1** (bd3efdb3): `excerpt()`; 11 tests. *Ruling:* the zlib spy takes keyword arguments, and the dead re-trim loop was removed.
- **Task 2** (33503329): `SampleReading` on the question, MI0215, readings past `STALE_AFTER` shown as *the AI didn't answer*, and the upload offered wherever the AI may read. 8 tests.
- **Task 3** (4167bbd9): `_record_found` extracted, with the 28 existing sample tests unchanged before anything was added; `answer_with_reading`. 14 tests.
- **Task 4** (f179d17f): `read_sample`, the job, and `func(…, keep_result=0)`. 23 tests.
  - *Ruling:* `conftest` switches the family step off for every test, and the `readable` fixture switches it back on.
  - *Ruling:* ARQ's field is `keep_result_s`. A job that exhausts its tries goes through `finish_failed_job`, which keeps the result, with the excerpt among its arguments, for the worker's default of an hour. This is rare (retries happen only on cancellation), and it is recorded for plan 4's loosening text.
- **Task 5** (a7d1ca55, client 5db75701): claim by recorded type, the `reading` outcome, `end_hand_back`, `ai_for` with `characterised`, and the branch marked built. `make check` 3406 passed.
  - *Ruling:* MI0215 maps to 422, as MI0203 does.
  - *Ruling:* the upload reader refuses an extra form field outright.
  - *Ruling:* a Keep test's `available` list gained `characterise`.

**Final review** (a fresh reviewer, opus):
- **Fixed in cc2a9d55 (#241)**, with eight tests that failed first:
  - three Important findings: a click did not stop the job; an answered reading stayed pending; a failed enqueue or a crashed job locked the question;
  - two Minors re-graded to Important because they concern a person's data: the excerpt reached ARQ's start log (it is now a `Sealed` string, whose `repr` is redacted), and the excerpt outlived the reading in Redis (the job now expires at `STALE_AFTER`).
- **Deferred minors → #242.**

