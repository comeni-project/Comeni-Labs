"""The forge's checks parse a module's source once while it stands still (#576)."""

import os
import shutil

from mendel_api.services import forge_checks
from support.paths import ROOT

MODULE = ROOT / "registry/tools/nf-core/cat/fastq/module"


def test_a_module_is_parsed_again_only_when_its_files_change(tmp_path, monkeypatch):
    """`forging.read` is polled every 2 s while a forging drafts or asks, and each read parsed
    the module's `main.nf` and `meta.yml` again (5 to 20 ms). They are parsed once for the
    files' sizes, modification times and inodes; an edit is parsed again."""
    folder = tmp_path / "fastq"
    shutil.copytree(MODULE, folder)
    parsed, real = [0], forge_checks.parse_module

    def counted(*args, **kwargs):
        parsed[0] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(forge_checks, "parse_module", counted)
    first = forge_checks.module_source(folder, "cat/fastq", "nf-core")
    again = forge_checks.module_source(folder, "cat/fastq", "nf-core")
    assert parsed[0] == 1 and again == first
    assert first.channels, "no input channel parsed: this would compare nothing"

    main_nf = folder / "main.nf"
    main_nf.write_text(main_nf.read_text() + "\n// edited\n")
    later = os.stat(main_nf).st_mtime_ns + 1_000_000_000
    os.utime(main_nf, ns=(later, later))
    edited = forge_checks.module_source(folder, "cat/fastq", "nf-core")
    assert parsed[0] == 2 and edited.text.endswith("// edited\n")
