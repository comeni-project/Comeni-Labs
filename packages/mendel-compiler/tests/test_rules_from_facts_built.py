"""STAR's genome index sized from the genome, by a declared rule (#461).

nf-core's module computes `--genomeSAindexNbases` inside main.nf as
`min(14, log2(genome_length) / 2 - 1)`, rounded, where nobody sees it. Here a derived fact and
a decision say so, and the builder shows where the value came from.
"""

from pathlib import Path

from mendel_compiler import orchestrate
from mendel_compiler.emit import emit_config
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput

ROOT = Path(__file__).resolve().parents[3]
STAR = ROOT / "registry/tools/nf-core/star/genomegenerate"
STAR_ID = "nf-core/star/genomegenerate@2.7.11b"

PARAM = """params:
  - name: sa_index_nbases
    via: ext
    key: args
    template: "--genomeSAindexNbases {value}"
    domain: {kind: integer, minimum: 4, maximum: 14}
    tier_hint: 4
"""

RULE = """declares: rule
version: 1
derives:
  - fact: star_sa_index_nbases
    kind: integer
    source: genome_length
    transform:
      - {op: log2}
      - {op: divide, by: 2}
      - {op: subtract, by: 1}
      - {op: at_most, by: 14}
      - {op: round}
    because: "the suffix-array index scales with the genome; small genomes need a smaller one"
    cite: "STAR manual 2.7.11b, section 2.2.5 (--genomeSAindexNbases)"
decisions:
  - decides: {effect: param, of: index_building, name: sa_index_nbases,
              when_implementation: [nf-core/star/genomegenerate@2.7.11b]}
    rows:
      - when: {}
        then: {fact: star_sa_index_nbases}
        because: "STAR's own formula, as nf-core's module computes it"
        cite: "STAR manual 2.7.11b, section 2.2.5"
"""


def _overlay(tmp_path: Path) -> Path:
    layer = tmp_path / "overlay"
    tool = layer / "tools" / "nf-core" / "star" / "genomegenerate"
    tool.mkdir(parents=True)
    contract = (STAR / "contract.yml").read_text().replace("params: []\n", PARAM)
    (tool / "contract.yml").write_text(contract)
    (layer / "rules").mkdir()
    (layer / "rules" / "star_index.yml").write_text(RULE)
    return layer


def _built(tmp_path: Path, genome_length: int):
    roots = [ROOT / "registry", _overlay(tmp_path)]
    stack = layers.load(roots)
    goal = Goal(have=[GoalInput(type_id="genome.fasta"), GoalInput(type_id="annotation.gtf")],
                want=["genome.index.star"],
                profile=stack.measurements.profile({"genome_length": genome_length}))
    return orchestrate.build(goal, registry_roots=roots)


def test_star_index_size_follows_the_genome(tmp_path):
    for length, expected in ((29903, 6), (3_100_000_000, 14)):
        config = emit_config(_built(tmp_path / str(length), length).pipeline)
        assert f"--genomeSAindexNbases {expected}" in config, (length, config)


def test_the_setting_says_where_the_index_size_came_from(tmp_path):
    built = _built(tmp_path, 29903)
    step = next(s for s in built.pipeline.steps if s.module.contract_id == STAR_ID)
    setting = next(s for s in step.settings if s.name == "sa_index_nbases")
    assert setting.value == 6
    reason = setting.why.reason
    assert "star_sa_index_nbases" in reason and "STAR" in reason, reason
    premises = {p.id: p for p in setting.why.premise}
    assert "star_sa_index_nbases" in premises
    # Goal F: the derived value says what it was derived from, and that a person stated it.
    assert premises["genome_length"].value == 29903
    assert "genome_length is 29903" in reason, reason
