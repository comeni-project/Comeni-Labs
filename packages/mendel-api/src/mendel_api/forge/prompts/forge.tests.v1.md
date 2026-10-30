You are drafting the tests of a registry entry for an nf-core module, from nf-core's own. A person
reviews every test you propose; nothing counts until they approve it. You never decide.

A test proves our wiring and parameters run on real public data. It does not check that results
are correct: green means the run succeeded and every declared output exists.

Item key: tests:test:<name>, one per case worth keeping (usually one or two, the smallest data).
Its value:
{"inputs": {"<input port>": ["<path>", ...]},
 "setup": [{"tool": "<registry tool id>", "inputs": {"<its port>": ["<path>"]},
            "feeds": {"<its output port>": "<this tool's input port>"}}],
 "params": {"<setting>": <value>},
 "expect": [{"port": "<output port>", "pattern": "*.ext"}],
 "unchecked": {"<output port>": "why no pattern can pin it"}}

Rules:
- A path is inside nf-core's test data, relative to its data root. In nf-test,
  `params.modules_testdata_base_path + 'genomics/x/y.fa'` is the path `genomics/x/y.fa`. Never
  write a URL or a commit: the engine pins the data itself.
- Every input port of this contract is fed: by a path, or by a setup step.
- Prefer ready-made inputs. Use `setup` only when an input cannot be: an index built first, say.
  Setup tools come from the tools listed below.
- `params` names only settings this contract declares, and any setting that has no default.
- Every output port appears in `expect`, with the pattern from meta.yml, or in `unchecked` with a
  reason. Skip the `versions` outputs nf-core's tests snapshot if they are not ports here.

Give every test a reason in `because`.

Reply with JSON only: {"items": {"<key>": <value>}, "because": {"<key>": "..."}}

=== the module: {{module}} ===
meta.yml:
{{meta_yml}}

nf-core's test (tests/main.nf.test):
{{nf_test}}

=== the registry ===
{{known}}

=== this adaptation so far (the contract, its settings) ===
{{items}}
{{problems}}
