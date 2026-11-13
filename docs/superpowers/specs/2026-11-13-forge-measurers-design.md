# The forge drafts measurers (#487, part 5.1 of #463)

## Why

The forge can import a tool such as `samtools faidx`. It cannot import the small parser that turns
the tool's output into a fact, such as the genome's length. Someone has to write that measurer by
hand in the registry (`registry/measurers/measures/genome_length_fai/`). Importing a tool easily
needs the forge to draft that parser too, for a person to approve, and to prove it on the tool's
real output before the tool is published.

## What a person sees

The forge gains a last step, **Measurers**, after Tests. When the person asks the AI to draft it,
the AI does one of two things:

- it says the tool needs none (`measurers:none`), which is the usual answer;
- it proposes a measurer for one of the tool's outputs that carries a fact. For example, QUAST's
  `report.tsv` carries the assembly's N50.

The person approves each part on its own, as with every other forge item:

- **the measurer** (`measurers:measurer:<id>`): which measurement it produces, which output it
  reads, its thresholds (`decided`), and its parser's code and tests, shown as code;
- **the measurement** (`measurers:measurement:<id>`), only when it is new, or when it exists and is
  `assertion_only`. In that case the draft re-declares it without the flag, because this tool now
  measures it.

After assembly, the forge's test run also runs each drafted parser over the tool's own output, in
the pipeline on Wiener. A test is green only when each parser reported a value for its
measurement. A parser that says "undetermined" fails the test with its reason, and the person
re-opens and changes it.

## Decisions

1. **The forge drafts only `by: tool` measurers.** A drafted measurer always has these values:
   - `by: tool`;
   - `uses:` the contract being forged;
   - `runs: [pipeline]`.

   The person never sets those three. It never runs on the server, so the trust question in #487
   (a model-written `by: code` measurer running on uploads) does not arise. Drafting `by: code`
   measurers is left for later.
2. **The parser never runs on Mendel's server.** No model-written code runs in Mendel's own
   process. That rules out the forge running the parser's unit tests there.
   - **The real proof is the test run on Wiener.** The tool's test pipeline gains the generated
     measuring step after the tool, as a built pipeline would. Wiener runs it in its plain Python
     container. The forge reads the result from Wiener's `/runs/{id}/measured`.
   - **The unit tests run in the registry's CI.** That CI gains a step that runs the pieces'
     tests.
3. **One check for allowed imports, everywhere.** The allowlist and banned calls now live only in
   `tests/guards/test_inspector_pieces.py`. They move into `mendel lint` as a registry rule, so
   one function checks every piece in four places:
   - the guard;
   - the forge's assembly, which re-opens Measurers when it fails;
   - the forge's publish check;
   - the registry's CI.
4. **The model writes from what it already sees:** `main.nf`, `meta.yml` and the nf-test, plus
   its knowledge of the tool's output format. It is not shown the real output. If its parser is
   wrong, the test run says so. Showing it a sample of the real output is left for later.
5. **The measurer's other fields are derived, not drafted:**
   - `id` is the item's name;
   - `version` is `1.0.0`;
   - `entry` is `piece/<id>.py`;
   - the tests file is `piece/test_<id>.py`.

   The model drafts these:
   - `measures`;
   - `output` (an output port of the forged contract);
   - `decided` (default `{}`);
   - `code`;
   - `tests`;
   - `explain` (one line saying what is parsed).
6. **Publishing may drop `assertion_only`.** Changing a shared file is refused today (MF0517). One
   change is now allowed: a measurement whose draft differs from the registry's only by dropping
   `assertion_only` and `assertion_only_because`. Any other change to an existing measurement is
   still refused. A measurer folder that already exists and differs is refused as a shared file.
7. **The vocabulary step's measurements are written too** (#490). They were approved and then
   dropped. `write_layer` writes both `vocabulary:measurement` and `measurers:measurement` items to
   `vocabulary/measurements/<id>.yml`. The same id from both steps is refused at assembly
   (MF0511).

## Constraints

- **Parser code keeps the pieces' rules**, as the guard enforces them today:
  - imports from the allowlist only;
  - no file access, no network, no processes;
  - it never raises and never guesses.

  A draft that breaks one is refused at assembly with the lint's message.
- **Everything is recorded.** The AI's draft stays in the item's history beside the person's
  decision, as for every other item. The pull request's record lists the measurer items with who
  drafted and who decided each.
- No sample data crosses to the model. The model sees the module's public files only, as today.

## Risks

- **Wiener might read facts too early.** Wiener reads a run's facts when the run completes. If
  `completed` can arrive before the outputs are published (#488, still to verify), a parser could
  look like it reported nothing. The browser check at the end of #463 covers this.
- **Re-forging can collide with the registry.** Re-forging a tool whose measurer the registry
  already has drafts it afresh. If the result differs from the registry's, publishing refuses it as
  a changed shared file.

## Not in this part

- Drafting `by: code` measurers.
- Showing the model the tool's real output.
- Re-forging an existing measurer to a new version.
- Running the parser's unit tests anywhere but the registry's CI and `make check`.

## Done when

- A forge adaptation of a tool can draft, approve, assemble, test and publish a `by: tool`
  measurer.
- The test run proves the parser on the tool's real output.
- A parser that imports something it may not import is refused at assembly with the lint's
  message.
- A fixture forge adaptation of `samtools faidx` re-creates the `genome_length_fai` measurer end to
  end. The test run uses a fake runner reporting a measured value, as the forge's test-run tests
  already do.
