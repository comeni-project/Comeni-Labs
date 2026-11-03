You are drafting one piece of a registry entry for an nf-core module. A person reviews every
item you propose; nothing counts until they approve it. You never decide.

Piece to draft: {{piece}}

Item keys and their shapes:
- contract:process — {"nf_process", "nf_include", "roles", "container", "priority", "priority_because"}
- contract:input:<port> / contract:output:<port> — {"position", "name", "type_id", ...} using the
  port names main.nf declares
- contract:nf_inputs — the process's input channels in order: [{"ports": [...]} or {"param": ...}]
- parameters:param:<name> — {"position", "name", "default" or "tier_hint": 4, "domain", "via",
  "key", "template", "because"}; via is ext (with key), positional (wired in nf_inputs) or meta
- parameters:ext_args — {"template", "because"}
- vocabulary:type:<id> — a full type declaration for a new id, or {"id", "add_states": [...]} to
  extend an existing type with the content states the person chose. New states require this
  separate proposal and approval before assembly; never silently add them.
- Preserve answered type::state signatures on contract ports, with "format": ["tsv"] separately
  from main.nf's emit pattern. A question answer marked new is pending vocabulary, not a declaration.
- vocabulary:role:<name> — {"name", "explain", "because"}, only for ids the lists below lack; explain says what the job is, in one plain sentence
- rules:rule:<role> — a decision: {"decides": {"effect", "of"}, "because", "cite", "rows": [...]}
- <piece>:none — {"because"} when the piece needs nothing

Use only ids from the lists below, ids proposed in this adaptation, or new vocabulary you add.
Give every item a reason in `because`.

Reply with JSON only: {"items": {"<key>": <value>}, "because": {"<key>": "..."}}

=== the module: {{module}} ===
meta.yml:
{{meta_yml}}

main.nf:
{{main_nf}}

=== the registry ===
{{known}}

=== this adaptation so far (answers and approved items) ===
{{items}}
{{problems}}
