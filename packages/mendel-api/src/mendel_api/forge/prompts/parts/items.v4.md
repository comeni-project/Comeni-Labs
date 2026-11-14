- contract:process — {"nf_process", "nf_include", "roles", "container", "priority", "priority_because"}
- contract:input:<port> — {"position", "name", "type_id", "required"}, using the port names
  main.nf declares. "required" is true unless the process runs without the input; write
  "required": false for an optional one. Nothing else: an input has no format.
  An input that takes several types (meta.yml's pattern lists formats of different types,
  such as FASTQ or BAM reads) has "accepts" instead of "type_id", most usual first:
  {"position": 0, "name": "reads", "accepts": [{"type_id": "fastq.reads"},
  {"type_id": "alignment.bam"}]}. Use only listed or pending type ids; a format with no type
  is a vocabulary question, never an invented id.
- contract:output:<port> — {"position", "name", "type_id", "format", "produced_when"}.
  "produced_when" is null when the output is always written, otherwise the condition under
  which it is, e.g. {"given.fasta": "present"} or {"param.save_output_fastqs": true}. Nothing
  else: no pattern, no optional, no description.
- contract:nf_inputs — the process's input channels in order: [{"ports": [...]} or {"param": ...}].
  Keep the tuples main.nf declares: an optional input inside a tuple with other files stays in
  that entry, and is passed as [] in its position when it is left out. An entry whose inputs
  are all optional also says "absent": the width of the empty tuple passed when every one is
  left out (2 for `tuple val(meta), path(x)`); an entry with a required input has no
  "absent". An entry of several ports says "join": "by_sample" when the later ports are per
  sample, "broadcast" when they are one file for the whole run, or a map giving each later
  port its own. gatk4/haplotypecaller's `tuple val(meta), path(input), path(input_index),
  path(intervals), path(dragstr_model)` is {"ports": ["input", "input_index", "intervals",
  "dragstr_model"], "join": {"input_index": "by_sample", "intervals": "broadcast",
  "dragstr_model": "by_sample"}}, with intervals and dragstr_model optional. If an entry's
  first port is optional, give one join for all its later ports.
- contract:constraint:row<n> (row1, row2, …) — {"when", "requires", "forbids", "because", "cite"}: what the tool
  allows between its inputs and params. "when" tests "given.<input>": "present",
  "param.<name>": <value>, or "type.<input>": <type id> for an input with "accepts" (also
  {"in": [...]} or {"not": ...}); "requires" and "forbids" name inputs or params. A mode the
  connected type selects is rows on "type.": salmon quant maps FASTQ reads against an index
  and quantifies BAM reads against the transcripts, so two rows:
  {"when": {"type.reads": "alignment.bam"}, "requires": ["transcript_fasta"],
   "forbids": ["index"], "because": "..."} and
  {"when": {"type.reads": "fastq.reads"}, "requires": ["index"], "because": "..."}.
  An input only some modes need is "required": false; the rows say when. A mode that changes
  the job is a separate tool, not rows. Example:
  {"when": {"given.gff": "present"}, "requires": ["fasta"],
   "because": "the script reads the GFF only against a reference"}. A constraint says what is
  possible, never what to choose.
- contract:group:group<n> (group1, …) — {"kind", "members", "because"}: kind is one_of (exactly one member),
  any_of (at least one) or all_or_none (together or not at all).
- parameters:param:<name> — {"position", "name", "default" or "tier_hint": 4, "domain", "via",
  "key", "template", "because"}; via is ext (with key), positional (wired in nf_inputs) or meta.
  "domain" is null or {"kind": "boolean" | "enum" | "integer" | "number", "values": [...]
  (for enum), "minimum", "maximum"}; a free-text setting such as a prefix has no domain
  A setting the module falls back on itself (`task.ext.prefix ?: "${meta.id}"`) has no
  "default" and no "tier_hint": leave both out. An ext "default" without a template is
  letters, digits and _ . : + - only; never `${...}`.
- parameters:ext_args — {"template", "because"}
- vocabulary:type:<id> — a full type declaration for a new id, or {"id", "add_states": [...]} to
  extend an existing type with the content states the person chose. New states require this
  separate proposal and approval before assembly; never silently add them. A full declaration
  is {"id", "states", "scope", "name", "explain", "entry_channel"}:
  - "scope" is "run" for a file shared by every sample (a reference, an annotation, a
    database) and "sample" for one per sample;
  - "name" is what a person calls it (at most 80 characters), and "explain" says what it is
    and where it usually comes from, in a sentence or two;
  - "entry_channel" reads it as a pipeline input, with params.{param} for the path. For a file
    give it the sample's name: "Channel.fromPath(params.{param}, checkIfExists: true).map { f
    -> [ [id: f.baseName], f ] }". Without it a tool that names outputs after meta.id writes
    "null".
- Preserve answered type::state signatures on contract ports. An output's "format" is the
  file format it writes, from its extension in main.nf: "format": ["tsv"] for
  ${prefix}.tsv. An output that is a directory (path("${prefix}") with no file
  extension) has "format": ["folder"]. A question answer marked new is pending vocabulary, not
  a declaration.
- Read the module for what is optional, and write it as evidence shows:
  - an emit marked `optional: true` gets "produced_when": the input or param that makes the
    process write it;
  - `def x = name ? "--flag $name" : ''` means `name` is optional;
  - an `error("… requires …")` line, or a meta.yml note that an input "has to contain at least
    a dummy value", is a constraint or an optional input;
  - an output on nf-core's versions topic is not a port.
- nf_include is the module's path under modules/, ending in main without .nf:
  modules/nf-core/<tool>/main, or modules/nf-core/<tool>/<subtool>/main. The pipeline
  includes it as ./modules/nf-core/<tool>/main, and the registry finds the module by it.
- vocabulary:family:<id> — {"id", "description"}; a family is the first dot-separated segment
  of a type ID (assembly.fasta belongs to assembly). Reuse listed or pending families.
  When declaring a type under a missing family, propose its family in Vocabulary too.
  Use one ID segment without dots and a short description (1–200 characters).
  Families require human approval before Assembly; never silently create them.
  Put the family's rationale in the reply's because map, not inside its declaration.
- vocabulary:role:<name> — {"name", "explain", "because"}, only for ids the lists below lack; explain says what the job is, in one plain sentence
- rules:rule:<role> — a decision: {"decides": {"effect", "of", "name", "when_implementation"},
  "hit", "because", "cite", "rows": [...]}. A row is {"when": {<fact>: <value or "op n">},
  "then": <value>, "because", "cite"}; the rows together must cover every case of the facts
  they test (or end with a catch-all {"when": {}} with a "cite"), and every row must decide
  some case. "hit" is "first" (the first matching row decides; the default) or "unique" (two
  matching rows are asked of a person; settings only). A setting may take a fact's value:
  "then": {"fact": "<measurement or derived fact>"}. A setting the module computes from the
  data is such a rule: STAR's --genomeSAindexNbases is
  "rules:derive:star_sa_index_nbases" and a catch-all row with
  "then": {"fact": "star_sa_index_nbases"} on {"effect": "param", "of": "index_building",
  "name": "sa_index_nbases", "when_implementation": ["nf-core/star/genomegenerate@2.7.11b"]}.
- rules:derive:<fact> — a fact computed from others: {"fact", "kind", "source", "transform",
  "because", "cite"}, or {"fact", "kind", "rows"} for rows with literal "then" values. A
  transform is a list of {"op", "by"} steps applied left to right to "source": add, subtract,
  multiply, divide, at_most, at_least (each with "by"), log2 and round (without). STAR's index
  size: {"fact": "star_sa_index_nbases", "kind": "integer", "source": "genome_length",
  "transform": [{"op": "log2"}, {"op": "divide", "by": 2}, {"op": "subtract", "by": 1},
  {"op": "at_most", "by": 14}, {"op": "round"}], "because": "...", "cite": "STAR manual"}.
- vocabulary:measurement:<id> — {"id", "kind", "values", "unit", "minimum", "maximum",
  "per_sample"}: a new measurement, only for ids the lists below lack; kind is boolean, enum
  (with values), integer or number
- tests:test:<name> — {"inputs", "setup", "params", "expect", "unchecked", "types"}: a run on
  nf-core's public test data; "expect" lists {"port", "pattern"} for each output it checks;
  "types" says which type the data is for an input with "accepts", e.g.
  "types": {"reads": "alignment.bam"} (left out, the input's first)
- <piece>:none — {"because"} when the piece needs nothing
