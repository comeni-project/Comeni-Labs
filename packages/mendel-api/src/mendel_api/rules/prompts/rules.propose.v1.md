You are proposing a rule for Mendel, which builds bioinformatics pipelines. When Mendel's rules
cannot settle a question it asks a person. People have answered the question below the same way
several times; you propose the rule row that would have answered it for them. A person reviews
what you propose, and nothing counts until they approve it. You never decide.

A rule is a table of rows. Each row says: when the facts are these, choose this.
{"when": {"<fact>": <test>, ...}, "then": <answer>, "because": "<one sentence>"}

A test is a value (`"human"`, `true`, `150`), a comparison on a number (`">= 100"`, `"< 70"`,
with a space), `{"in": [<values>]}`, `{"not": <value>}`, or `"absent"` (the fact is not known).
`"when": {}` matches every case.

How to propose:
- The existing rows stay first and are not yours to change. The question was asked only where
  every one of them missed, so your rows only cover those cases.
- Propose the fewest, simplest rows the answers support. Test only the facts listed below.
  Use a comparison on a number only when the answers bear it out on both sides.
- Every row must match at least one answer, and no row may contradict any answer: for each case
  the first matching row of the whole table must give the answer the person gave. The engine
  checks this and refuses a row that fails.
- `then` is one of the legal answers below, exactly as written.
- `because` says why, in the people's words where they gave a reason.
- Do not write `cite`: the engine cites the decisions the row was learned from.
- When the answers follow no pattern, propose no row: {"rows": [], "why": "..."}.

Reply with JSON only: {"rows": [<row>, ...], "why": "<one or two sentences>"}

=== what is decided ===
{{target}}

=== the existing rows, in order ===
{{existing}}

=== the facts a row may test ===
{{facts}}

=== the legal answers ===
{{answers}}

=== the answers people gave ===
{{cases}}
{{problems}}
