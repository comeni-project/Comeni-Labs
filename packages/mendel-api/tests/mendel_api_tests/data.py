"""Helpers for the data tests (#511): make a draft, write paired reads, tick folders, read the
analysis's data."""

from support.paths import ROOT

PAIR = sorted((ROOT / "registry/measurers/formats/fastq/piece/fixtures/pair_150").glob("*.gz"))


def draft(client) -> str:
    made = client.post("/api/pipeline/drafts", json={"graph": {"nodes": [], "edges": []}})
    return made.json()["id"]


def pairs(folder, *stems):
    folder.mkdir(parents=True, exist_ok=True)
    r1, r2 = PAIR
    for stem in stems:
        (folder / f"{stem}_R1.fq.gz").write_bytes(r1.read_bytes())
        (folder / f"{stem}_R2.fq.gz").write_bytes(r2.read_bytes())
    return folder


def tick(client, draft_id, *folders):
    return client.put(f"/api/data/{draft_id}/folders", json={"folders": [str(f) for f in folders]})


def view(client, draft_id):
    return client.get(f"/api/data/{draft_id}").json()


