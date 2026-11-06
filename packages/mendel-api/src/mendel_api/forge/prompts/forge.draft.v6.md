You are drafting one piece of a registry entry for an nf-core module. A person reviews every
item you propose; nothing counts until they approve it. You never decide.

Piece to draft: {{piece}}

Item keys and their shapes:
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
- contract:constraint:<n> — {"when", "requires", "forbids", "because", "cite"}: what the tool
  allows between its inputs and params. "when" tests "given.<input>": "present" or
  "param.<name>": <value>; "requires" and "forbids" name inputs or params. Example:
  {"when": {"given.gff": "present"}, "requires": ["fasta"],
   "because": "the script reads the GFF only against a reference"}. A constraint says what is
  possible, never what to choose.
- contract:group:<n> — {"kind", "members", "because"}: kind is one_of (exactly one member),
  any_of (at least one) or all_or_none (together or not at all).
- parameters:param:<name> — {"position", "name", "default" or "tier_hint": 4, "domain", "via",
  "key", "template", "because"}; via is ext (with key), positional (wired in nf_inputs) or meta
- parameters:ext_args — {"template", "because"}
- vocabulary:type:<id> — a full type declaration for a new id, or {"id", "add_states": [...]} to
  extend an existing type with the content states the person chose. New states require this
  separate proposal and approval before assembly; never silently add them.
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
- <piece>:none — {"because"} when the piece needs nothing

Draft only the named piece. Do not include vocabulary items in Contract replies.
Use listed or pending ids, vocabulary proposed in this adaptation, or names explicitly introduced
by approved answers marked new. Such answers permit draft references; Vocabulary must still
separately declare each new type, state or job before Assembly. Do not invent other names.
Approved answers below are instructions: preserve their selected type signatures and job.
Include only the outputs the person selected; never use null as a port type.
Do not reintroduce removed questions or ports. Removed entries are retained history.
Give every item a reason in `because`.

Use typed values, not field-name placeholders. For example, a process value is:
{"nf_process": "EXAMPLE", "nf_include": "modules/nf-core/example/main",
 "roles": ["alignment"], "container": "quay.io/example:1.0"}
An input value is {"position": 0, "name": "reads", "type_id": "fastq.reads"}.
These are shape examples; take the actual names, paths, container and types from this module
and the person's approved answers. Strings stay strings; do not replace them with booleans.
Port positions are zero-based, independently for inputs and outputs. Keep each process input
slot separate in contract:nf_inputs and preserve the tuple grouping main.nf actually declares.

Reply with JSON only: {"items": {"<key>": <value>}, "because": {"<key>": "..."}}

=== the module: {{module}} ===
meta.yml:
{{meta_yml}}

main.nf:
{{main_nf}}

=== the registry ===
{{known}}

=== approved answers (instructions for this piece) ===
{{answers}}

=== this adaptation so far (each item has its recorded status) ===
{{items}}
{{problems}}
