"""What can a contract's fields be read off its module, and what cannot?

Not a guard. This is the measurement behind the forge's hole list, kept as a test so it
re-runs and cannot quietly become false. If it fails, the derivability table in
notes/audits/2026-08-16-forge-derivability.md is stale and the forge's holes are wrong.
"""

from pathlib import Path

from comeni_core.declared.contract import ModuleContract
from comeni_core.spell.routes import Via
from mendel_compiler.conformance import module_path
from mendel_compiler.modulespec import ModuleSpec
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "vendor"


def _pairs() -> list[tuple[ModuleContract, ModuleSpec]]:
    """Every shipped contract whose module is vendored, so the two can be compared.

    `module_path` rather than a second spelling of `module_root / f"{nf_include}.nf"`:
    the survey measures the compiler's idea of where a module lives, not its own.
    """
    stack = layers.load(ROOT / "registry")
    found = []
    for contract in stack.registry.all():
        main_nf = module_path(contract, VENDOR)
        if main_nf.exists():
            found.append((contract, ModuleSpec.parse(main_nf)))
    return found


def test_the_survey_found_modules_to_survey():
    pairs = _pairs()
    assert len(pairs) >= 5, f"only {len(pairs)} contract/module pairs; the survey is not surveying"


def test_process_name_is_derivable():
    for contract, spec in _pairs():
        assert contract.nf_process == spec.process, contract.id


def test_container_is_derivable():
    missing = [c.id for c, s in _pairs() if c.container and s.container != c.container]
    assert missing == [], f"container disagrees with the module for: {missing}"


def test_output_port_names_come_from_emits():
    wrong = []
    for contract, spec in _pairs():
        for port in contract.produces:
            if port.name not in spec.emits:
                wrong.append(f"{contract.id}:{port.name} not in {spec.emits}")
    assert wrong == [], f"output port names are not module emits: {wrong}"


def test_input_channel_count_is_derivable():
    wrong = []
    for contract, spec in _pairs():
        if len(contract.input_signature()) != len(spec.inputs):
            wrong.append(f"{contract.id}: {len(contract.input_signature())} vs {len(spec.inputs)}")
    assert wrong == [], f"nf_inputs arity disagrees with the module: {wrong}"


def test_semantic_fields_are_not_in_the_module_at_all():
    """The negative half, and the one that justifies holes existing.

    A module declares no type_id, no state, no role. If this ever fails, the forge can
    derive more than it does and the hole list should shrink.
    """
    for contract, _spec in _pairs():
        text = module_path(contract, VENDOR).read_text()
        for port in contract.produces:
            assert port.type_id not in text, (
                f"{contract.id}: {port.type_id} appears in main.nf — it may be derivable"
            )


def test_input_port_names_are_a_choice_and_not_a_reading():
    """The row the plan guessed wrong, held as a golden set.

    A contract's input port name is *not* the module's channel name. Four of twelve
    shipped contracts rename: `SAMTOOLS_INDEX`'s channel is `input` and the port is
    `bam`; `SUBREAD_FEATURECOUNTS`'s is `bams`; both MultiQC contracts call the
    `multiqc_files` channel something that says what it carries. So the forge can offer
    the module's channel names as *candidates* and cannot fill the field.

    If this list shrinks, naming has become more mechanical and the hole may narrow. If
    it grows, it has become less so. Either way the derivability table is stale.
    """
    renamed = []
    for contract, spec in _pairs():
        known = {n for slot in spec.inputs for n in slot.names}
        known |= {doc.name for doc in spec.documented}
        for port in contract.consumes:
            if port.name not in known:
                renamed.append(f"{contract.id}:{port.name}")
    assert sorted(renamed) == [
        "comeni/profile/collect@0.1.0:measurements",
        "nf-core/multiqc@1.35:reports",
        "nf-core/samtools/index@1.21.0:bam",
        "nf-core/subread/featurecounts@2.0.6:bam",
    ], (
        "input port naming changed; re-read "
        f"notes/audits/2026-08-16-forge-derivability.md: {renamed}"
    )


def test_a_contract_declares_one_output_of_the_many_a_module_emits():
    """Why `produces[].name` is a candidate list and not a derived value.

    `STAR_ALIGN` emits nineteen channels and the contract names one. The set is
    readable; which member of it the pipeline wants is a judgement about what the tool
    is *for*, which is nowhere in `main.nf`.
    """
    for contract, spec in _pairs():
        assert len(contract.produces) <= len(spec.emits), contract.id
    widest = max((len(s.emits), c.id) for c, s in _pairs())
    assert widest[0] >= 10, (
        f"no module offers a wide emit list any more (widest is {widest}); the argument "
        "that choosing an output is a hole rested on that width"
    )


def test_positional_params_are_named_by_the_module_and_ext_params_are_not():
    """The param row splits in two, and the split is mechanical.

    A `via: positional` param *is* an input channel, so its name is read off the module.
    A `via: ext` param is a flag the author invented a name for — `min_mqs` is nowhere
    in featureCounts' `main.nf`, because the module only knows `task.ext.args`.
    """
    for contract, spec in _pairs():
        known = {n for slot in spec.inputs for n in slot.names}
        for param in contract.params:
            if param.via is Via.POSITIONAL:
                assert param.name in known, (
                    f"{contract.id}:{param.name} is positional but names no channel"
                )
            else:
                assert param.name not in known, (
                    f"{contract.id}:{param.name} is via={param.via.value} yet names a "
                    "channel — the positional/ext split may be derivable after all"
                )
