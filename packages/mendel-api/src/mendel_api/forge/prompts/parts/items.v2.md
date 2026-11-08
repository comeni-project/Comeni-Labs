- contract:process — {"nf_process", "nf_include", "roles", "container", "priority", "priority_because"}
- contract:input:<port> — {"position", "name", "type_id", "required"}, using the port names
  main.nf declares. "required" is true unless the process runs without the input; write
  "required": false for an optional one. Nothing else: an input has no format.
- contract:output:<port> — {"position", "name", "type_id", "format", "produced_when"}.
  "produced_when" is null when the output is always written, otherwise the condition under
  which it is, e.g. {"given.fasta": "present"} or {"param.save_output_fastqs": true}. Nothing
  else: no pattern, no optional, no description.
- contract:nf_inputs — the process's input channels in order: [{"ports": [...]} or {"param": ...}].
  An entry whose inputs are all optional also says "absent": the width of the empty tuple
  passed when they are left out (2 for `tuple val(meta), path(x)`). Several optional inputs
  share an entry only when a group says they go together.
- contract:constraint:row<n> (row1, row2, …) — {"when", "requires", "forbids", "because", "cite"}: what the tool
  allows between its inputs and params. "when" tests "given.<input>": "present" or
  "param.<name>": <value>; "requires" and "forbids" name inputs or params. Example:
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
- rules:rule:<role> — a decision: {"decides": {"effect", "of"}, "because", "cite", "rows": [...]}
- vocabulary:measurement:<id> — {"id", "kind", "values", "unit", "minimum", "maximum",
  "per_sample"}: a new measurement, only for ids the lists below lack; kind is boolean, enum
  (with values), integer or number
- tests:test:<name> — {"inputs", "setup", "params", "expect", "unchecked"}: a run on nf-core's
  public test data; "expect" lists {"port", "pattern"} for each output it checks
- <piece>:none — {"because"} when the piece needs nothing
