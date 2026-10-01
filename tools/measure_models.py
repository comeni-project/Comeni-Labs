"""Measure which local model serves each builder purpose — issue 187, part 14.7.5.7.

Drives the running stack through its own APIs. For each model it points every purpose in
Settings → Models at it, starts one builder session per sentence, answers the first question
with a fixed reply, waits for the session to settle, and reads every call it made. Prints, per
model and purpose: calls, admitted, refused, failed, and the median time and tokens.

    uv run python tools/measure_models.py --connection "Local Ollama" \\
        ollama_chat/gemma3:4b ollama_chat/qwen2.5:7b ollama_chat/gemma3:12b

**The purposes, not the default.** The default model may be pinned by `.env` (it is on the
operator's machine), and the five purposes are not; setting them reaches every builder call
without touching `.env`. Each purpose is put back as it was found, even after an error.

A measuring tool, run by hand; its numbers are recorded on issue 187.
"""

import argparse
import statistics
import sys
import time
from collections import defaultdict

import httpx

PURPOSES = ("want", "talk", "tier4", "readback", "forge")
"""Settings → Models, by key suffix (`models.<name>`)."""

SENTENCES = (
    "gene counts from my RNA-seq",
    "gene counts from paired-end RNA-seq, 150 bp reads, against the human reference genome",
    "variant calls from my exomes",
)
"""The walk's sentences (#194, #198): a short one, a full one, and one no type fits."""

REPLY = "I have it"
SETTLE_SECONDS = 15
CEILING_SECONDS = 600


def _settled(http: httpx.Client, session: str) -> bool:
    """Settled when nothing has changed for `SETTLE_SECONDS`, or the session failed."""
    last, since, started = None, time.monotonic(), time.monotonic()
    while time.monotonic() - started < CEILING_SECONDS:
        view = http.get(f"/api/pipeline/authoring/{session}").json()
        calls = len(http.get(f"/api/pipeline/authoring/{session}/calls").json())
        now = (view["row_version"], calls)
        if view["phase"] == "failed":
            return True
        if now != last:
            last, since = now, time.monotonic()
        elif time.monotonic() - since >= SETTLE_SECONDS:
            return True
        time.sleep(2)
    return False


def _session(http: httpx.Client, sentence: str) -> tuple[list[dict], bool]:
    started = http.post("/api/pipeline/authoring", json={"prompt": sentence}).json()
    session = started["session"]["id"]
    done = _settled(http, session)
    if done:
        http.post(f"/api/pipeline/authoring/{session}/messages", json={"text": REPLY})
        done = _settled(http, session)
    return http.get(f"/api/pipeline/authoring/{session}/calls").json(), done


def _median(rows: list[dict], key: str) -> float:
    return statistics.median([r[key] for r in rows if r[key] is not None] or [0])


def _table(model: str, calls: list[dict], timed_out: int) -> str:
    by = defaultdict(list)
    for call in calls:
        by[call["purpose"]].append(call)
    note = f"  ({timed_out} session(s) timed out)" if timed_out else ""
    lines = [
        f"\n## {model}{note}",
        "| purpose | calls | admitted | refused | failed | median ms | median in | median out |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for purpose, rows in sorted(by.items()):
        states = [r["state"] for r in rows]
        lines.append(
            f"| {purpose} | {len(rows)} | {states.count('succeeded')} | "
            f"{states.count('refused')} | {states.count('failed')} | "
            f"{_median(rows, 'duration_ms'):.0f} | {_median(rows, 'input'):.0f} | "
            f"{_median(rows, 'output'):.0f} |"
        )
    return "\n".join(lines)


def _point(http: httpx.Client, value: dict | None) -> None:
    for name in PURPOSES:
        http.put(f"/api/settings/models.{name}", json={"value": value}).raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="+")
    parser.add_argument("--connection", required=True)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()

    with httpx.Client(base_url=args.api, timeout=60) as http:
        menu = http.get("/api/settings").json()
        entries = {e["setting"]["key"]: e["shown"] for s in menu["sections"] for e in s["entries"]}
        locked = [n for n in PURPOSES if entries[f"models.{n}"]["locked"]]
        if locked:
            print(f"pinned by .env, cannot measure: {locked}", file=sys.stderr)
            return 2
        before = {n: entries[f"models.{n}"]["value"] for n in PURPOSES}
        listed = http.post(
            f"/api/settings/models.connections/items/{args.connection}/models"
        ).json()["values"]
        # Not a setting (spec §7): the family step is whatever the api's environment says.
        print("family step: MENDEL_FAMILY_STEP_FROM as set in .env (record its value with these)")
        try:
            for model in args.models:
                if model not in listed:
                    print(f"\n## {model}\nskipped: not on {args.connection} ({', '.join(listed)})")
                    continue
                _point(http, {"connection": args.connection, "model": model})
                calls, timed_out = [], 0
                for sentence in SENTENCES:
                    got, done = _session(http, sentence)
                    calls += got
                    timed_out += not done
                print(_table(model, calls, timed_out), flush=True)
        finally:
            for name, value in before.items():
                http.put(f"/api/settings/models.{name}", json={"value": value})
            print(f"\npurposes restored: {before}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
