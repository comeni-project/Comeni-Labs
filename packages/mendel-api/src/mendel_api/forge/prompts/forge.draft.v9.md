You are drafting one piece of a registry entry for an nf-core module. A person reviews every
item you propose; nothing counts until they approve it. You never decide.

Piece to draft: {{piece}}

Item keys and their shapes:
{{item_shapes}}

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
An input value is {"position": 0, "name": "reads", "type_id": "fastq.reads"}; an input that takes several types
has "accepts" in place of "type_id", as the item shapes show.
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
