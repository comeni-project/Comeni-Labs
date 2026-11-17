"""Data roots (#511, #508): Comeni reads a person's files where they are, and only under the
folders the installation names. Every path a request carries is resolved and checked here."""

import os

import pytest
from fastapi.testclient import TestClient
from mendel_api.main import create_app
from mendel_api.services.data import roots
from mendel_api.settings import settings


@pytest.fixture
def root(tmp_path):
    base = tmp_path / "data"
    (base / "liver" / "october").mkdir(parents=True)
    (base / "liver" / "L01_R1.fastq.gz").write_bytes(b"@r\nA\n+\nI\n")
    (base / "liver" / "L01_R2.fastq.gz").write_bytes(b"@r\nA\n+\nI\n")
    (base / "assemblies").mkdir()
    (base / ".hidden").mkdir()
    return base


def test_a_path_inside_a_root_resolves(root):
    assert roots.inside_roots(root / "liver" / ".." / "liver", [root]) == (root / "liver").resolve()


def test_dotdot_out_of_a_root_is_refused(root):
    with pytest.raises(ValueError, match="MI0221"):
        roots.inside_roots(root / ".." , [root])


def test_a_symlink_pointing_outside_is_refused(root, tmp_path):
    outside = tmp_path / "secrets"
    outside.mkdir()
    os.symlink(outside, root / "escape")
    with pytest.raises(ValueError, match="MI0221"):
        roots.inside_roots(root / "escape", [root])


def test_a_path_that_does_not_exist_is_refused(root):
    with pytest.raises(ValueError, match="MI0221"):
        roots.inside_roots(root / "missing", [root])


def test_no_roots_configured_is_refused_with_its_own_code(root):
    with pytest.raises(ValueError, match="MI0222"):
        roots.inside_roots(root, [])


def test_listing_counts_files_and_lists_subfolders_sorted(root):
    listing = roots.list_folder(root, [root])
    assert listing.files == 0
    assert [f.name for f in listing.folders] == ["assemblies", "liver"]
    liver = listing.folders[1]
    assert liver.files == 2
    assert liver.path == str((root / "liver").resolve())


def test_listing_without_a_path_lists_the_roots(root):
    listing = roots.list_folder(None, [root])
    assert listing.path is None
    assert [f.path for f in listing.folders] == [str(root.resolve())]


def test_tree_route_without_path_lists_the_roots(root, monkeypatch):
    monkeypatch.setattr(settings, "data_roots", [root])
    client = TestClient(create_app())
    body = client.get("/api/data/tree").json()
    assert [f["path"] for f in body["folders"]] == [str(root.resolve())]
    inside = client.get("/api/data/tree", params={"path": str(root / "liver")}).json()
    assert inside["files"] == 2 and [f["name"] for f in inside["folders"]] == ["october"]
    refused = client.get("/api/data/tree", params={"path": "/etc"})
    assert refused.status_code in (400, 422) and "MI0221" in refused.text


def test_a_symlinked_folder_out_of_the_root_is_not_listed(root, tmp_path):
    """Checkpoint A, finding 2: no path or count from outside the roots reaches the tree."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x")
    os.symlink(outside, root / "escape")
    names = [f.name for f in roots.list_folder(root, [root]).folders]
    assert "escape" not in names


def test_listing_a_file_is_refused_not_a_crash(root):
    with pytest.raises(ValueError, match="MI0221"):
        roots.list_folder(root / "liver" / "L01_R1.fastq.gz", [root])


def test_a_folder_says_how_many_subfolders_it_has(root):
    listing = roots.list_folder(root, [root])
    by_name = {f.name: f for f in listing.folders}
    assert by_name["liver"].folders == 1 and by_name["assemblies"].folders == 0


def test_each_folder_says_what_it_looks_like_by_its_files_kinds(root, monkeypatch):
    """The Data page's folder picker (board 2026-11-16): before anything is ticked, a folder says
    '2 sequencing read files' or 'a genome, an annotation', from its files' extensions as the
    registry's readers and study-wide types name them. A reference folder's FASTA is a genome."""
    (root / "reference").mkdir()
    (root / "reference" / "genome.fna").write_text(">c\nA\n")
    (root / "reference" / "genes.gtf").write_text("x\n")
    (root / "assemblies" / "BAC47.fna").write_text(">c\nA\n")
    (root / "notes").mkdir()
    (root / "notes" / "readme.txt").write_text("x\n")
    monkeypatch.setattr(settings, "data_roots", [root])
    client = TestClient(create_app())
    body = client.get("/api/data/tree", params={"path": str(root)}).json()
    looks = {f["name"]: f["looks_like"] for f in body["folders"]}
    assert looks["liver"] == [{"type_id": "fastq.reads", "count": 2}]
    assert looks["assemblies"] == [{"type_id": "assembly.fasta", "count": 1}]
    assert looks["reference"] == [{"type_id": "annotation.gtf", "count": 1},
                                  {"type_id": "genome.fasta", "count": 1}]
    assert looks["notes"] == []


def test_readers_say_what_they_read_and_measure(monkeypatch):
    client = TestClient(create_app())
    readers = {r["id"]: r for r in client.get("/api/data/readers").json()}
    assert readers, "the registry declares format readers"
    fastq = readers["fastq"]
    assert fastq["type_id"] == "fastq.reads" and ".fastq" in fastq["extensions"]
    assert ".gz" in fastq["compressed"]
    assert "read_length" in fastq["measures"]
    assert {"contigs", "n50"} <= set(readers["fasta"]["measures"])


def test_each_reader_says_what_it_measures_what_decides_by_it_and_its_tests(monkeypatch):
    """Registry · Measurers (board 7b): one entry a reader — the FASTQ and FASTA readers and the
    samtools faidx output — each fact with its unit, the rules and settings that read it, and the
    cases its tests check."""
    client = TestClient(create_app())
    readers = {r["id"]: r for r in client.get("/api/data/readers").json()}
    fastq = readers["fastq"]
    assert fastq["by"] == "code" and fastq["runs"] == ["server", "pipeline"]
    facts = {f["measurement"]: f for f in fastq["facts"]}
    assert set(facts) == {"paired", "quality_encoding", "read_length"}
    read_length = facts["read_length"]
    assert read_length["unit"] == "bp"
    assert any(r["role"] == "alignment" and r["rows"] for r in read_length["rules"])
    assert read_length["tests"], "the measurer's test cases are listed"
    faidx = readers["genome_length_fai"]
    assert faidx["by"] == "tool" and faidx["runs"] == ["pipeline"] and faidx["type_id"] == "fai"
    [genome] = faidx["facts"]
    assert genome["settings"] == [{"name": "star_sa_index_nbases",
                                   "formula": "round(min(14, log₂(genome length) / 2 − 1))"}]
