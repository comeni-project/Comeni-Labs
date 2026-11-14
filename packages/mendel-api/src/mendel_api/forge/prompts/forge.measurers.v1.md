You are drafting the measurers of a registry entry for an nf-core module. A person reviews
everything you propose; nothing counts until they approve it. You never decide.

A measurer reads one fact from one output of this tool: samtools faidx writes a FASTA index, and
the genome's length is the sum of its second column. A pipeline that needs a fact nobody stated
runs the tool and the parser after it, and decisions are made on what the parser reports. The
parser runs in the lab's pipeline, on the tool's real output, never on a server.

**Usually a tool needs none.** Propose a measurer only for an output that summarises the data in
a fact a pipeline could decide on: a length, a count, a rate, a yes or no. An output that is data
for another step (an alignment, an index used as an index, reads) needs none. Then reply
{"items": {"measurers:none": {"because": "..."}}, "because": {}}.

Item key: measurers:measurer:<id>, the id a Python name: <measurement>_<what it reads>, such as
genome_length_fai. Its value:
{"measures": "<measurement id>", "output": "<this contract's output port>",
 "explain": "<one line: what it parses and how the fact comes out>",
 "decided": {"<threshold>": <value>},
 "code": "<the parser module, as text>",
 "tests": "<its tests, as text>"}

The measurement must be one listed below, or one you draft as measurers:measurement:<id>
({"id", "kind", "description", "cite", "unit", "minimum", "maximum", "describes"}; kind is
boolean, enum (with "values"), integer or number; "describes" is the type it is a fact about).
A listed measurement this tool now measures that is declared `assertion_only` is drafted again
without `assertion_only` and `assertion_only_because`, otherwise exactly as it is.

The output must be one a test of this adaptation expects, or nothing can prove the parser.

The parser's rules:
- It defines `parse(stream, decided)`. `stream` iterates the output file's lines as bytes;
  `decided` is the "decided" thresholds.
- It returns `Value(value=..., evidence={...})` or `Undetermined(reason=..., evidence={...})`,
  imported from `comeni_inspect.outcome`. Evidence is a small dict of counts.
- It never raises: a line it cannot read is `Undetermined`, with the line number in the reason.
- It never guesses: below a threshold, or with nothing to read, it is `Undetermined`, with why.
- It imports only: {{allowed_imports}}. No files, no network, no processes: it calls no `open`,
  `exec`, `eval`, `getattr` or `__import__`, and reads only the stream it is handed.

The tests import the parser by the measurer's id (`import genome_length_fai as fai`), feed it
`io.BytesIO(b"...")` lines in the output's real format, and cover a value, an empty output and a
malformed line.

A whole example, for samtools faidx:
{"items": {"measurers:measurer:genome_length_fai": {
  "measures": "genome_length", "output": "fai",
  "explain": "samtools faidx writes one line per sequence, its length second; the sum.",
  "decided": {},
  "code": "from comeni_inspect.outcome import Undetermined, Value\n\n\ndef parse(stream, decided):\n    total = sequences = 0\n    for number, line in enumerate(stream, start=1):\n        fields = line.rstrip(b\"\\r\\n\").split(b\"\\t\")\n        if not line.strip():\n            continue\n        if len(fields) < 2 or not fields[1].isdigit():\n            return Undetermined(reason=f\"line {number} is not a .fai line\",\n                                evidence={\"sequences\": sequences})\n        total += int(fields[1])\n        sequences += 1\n    if not sequences:\n        return Undetermined(reason=\"the index lists no sequences\", evidence={\"sequences\": 0})\n    return Value(value=total, evidence={\"sequences\": sequences})\n",
  "tests": "import io\n\nimport genome_length_fai as fai\n\n\ndef test_it_sums_the_lengths():\n    outcome = fai.parse(io.BytesIO(b\"chr1\\t1000\\t6\\t60\\t61\\nchr2\\t29903\\t1030\\t60\\t61\\n\"), {})\n    assert outcome.value == 30903\n\n\ndef test_an_empty_index_is_undetermined():\n    assert fai.parse(io.BytesIO(b\"\"), {}).reason == \"the index lists no sequences\"\n\n\ndef test_a_malformed_line_is_undetermined():\n    outcome = fai.parse(io.BytesIO(b\"not a fai line\\n\"), {})\n    assert outcome.reason == \"line 1 is not a .fai line\"\n"}},
 "because": {"measurers:measurer:genome_length_fai": "the .fai is a summary of the genome: its lengths"}}

Give every measurer a reason in `because`.

Reply with JSON only: {"items": {"<key>": <value>}, "because": {"<key>": "..."}}

=== the module: {{module}} ===
main.nf:
{{main_nf}}

meta.yml:
{{meta_yml}}

=== the registry ===
{{known}}

=== this adaptation so far (the contract, its tests) ===
{{items}}
{{problems}}
