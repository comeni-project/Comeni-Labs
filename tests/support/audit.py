"""Fixtures the audit regressions share.

Split out of `tests/test_audit_regressions.py` when that file became seven, so a
helper is written once and every file that needs it says so in an import.
"""

import pathlib
from pathlib import Path

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body


def _published_pipeline(tmp_path, root, name="published"):
    """Build and certify a pipeline, and hand back the file that names it.

    `publish` stopped writing an artifact of its own in Plan 1.10 Task 10 — the directory is
    the artifact — so this is `build` then `publish`, and what comes back is `pipeline.yml`.
    """
    from mendel_compiler.cli import main

    out = tmp_path / name
    assert main(["build", "--goal", str(root / "examples" / "rnaseq-goal.yml"),
                 "--out", str(out), "--root", str(root)]) == 0
    assert main(["publish", str(out / "pipeline.yml"), "--root", str(root)]) == 0
    return out / "pipeline.yml"


def _stacked(tmp_path):
    """A base registry with a param rule, and a lab overlay that displaces two things.

    The base keeps its own `registry.yml`, so it is named `comeni-registry-examples`
    wherever it is copied to — A12's fix. The overlay has no manifest and falls back to
    its basename, which is what a lab building one by hand actually gets.
    """
    import shutil

    base = tmp_path / "base"
    shutil.copytree("registry", base)
    # The shipped registry has no param decision left to displace — the strandedness
    # block was deleted in Plan 1.5 — so the base gets one, and the overlay replaces it.
    (base / "rules" / "platform.yml").write_text(
        _declared(base / "rules" / "platform.yml", "version: 1\n"
        "decisions:\n"
        "  - decides: {effect: param, of: alignment, name: seq_platform}\n"
        "    because: 'the base registry sequences on Illumina'\n"
        "    rows:\n"
        "      - {when: {read_length: '>= 70'}, then: ILLUMINA}\n"
        # The complementary branch. `MD0311` refuses a table with a hole: a profile
        # below the boundary would match nothing and demote to tier 4 silently.
        "      - {when: {read_length: '< 70'}, then: ILLUMINA}\n")
    )

    lab = tmp_path / "lab-registry"
    (lab / "contracts").mkdir(parents=True)
    (lab / "rules").mkdir(parents=True)
    # A *different module key*, so this is not a shadow and no ShadowRecord is written.
    # Priority 99 beats nf-core/samtools/sort@1.21.0 at 0 outright, so it is not a tie
    # either and invariant 8 never fires. That is the whole of A5.
    (lab / "contracts" / "rival-sorter.yml").write_text(
        _declared(lab / "contracts" / "rival-sorter.yml", "id: lab/rival/sorter@9.9.9\n"
        "nf_process: RIVAL_SORT\n"
        "nf_include: modules/lab/rival/main\n"
        "consumes: [{name: bam, type_id: alignment.bam, state_required: []}]\n"
        "produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted]}]\n"
        "params: []\n"
        "priority: 99\n"
        "nf_inputs: [{ports: [bam]}]\n"
        "container: example.invalid/rival:1\n"
        "provenance: {source: lab, drafted_by: lab, approved_by: lab, approved_at: '2026-08-06'}\n")
    )
    (lab / "rules" / "platform.yml").write_text(
        _declared(lab / "rules" / "platform.yml", "version: 1\n"
        "decisions:\n"
        "  - decides: {effect: param, of: alignment, name: seq_platform}\n"
        "    because: 'this lab runs BGI'\n"
        "    rows:\n"
        "      - {when: {read_length: '>= 70'}, then: BGI}\n"
        "      - {when: {read_length: '< 70'}, then: BGI}\n")
    )
    return base, lab


def _resolve_stacked_from(loaded):
    import yaml
    from comeni_core.declared.layer import layer_name
    from comeni_core.goal.asked import Goal
    from mendel_resolver.resolve import resolve

    goal = Goal.model_validate(yaml.safe_load(Path("examples/rnaseq-goal.yml").read_text()))
    return resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        layer_names=[layer_name(p) for p in loaded.paths],
    )


def _pipe(ir, loaded):
    """Materialise an IR for the emitter.

    `emit` takes one argument since Plan 1.10 Task 5 — everything it used to look up in the
    registry, vocabulary and measurements now lives on the `Pipeline`.

    `goal` is keyword-only and required since Task 6. An empty one is honest here: these
    fixtures start from an IR and never had a goal to record.
    """
    from comeni_core.artifact.pipeline import Pipeline
    from comeni_core.goal.asked import Goal

    return Pipeline.of(ir, loaded.registry, loaded.vocabulary, loaded.measurements, goal=Goal())
