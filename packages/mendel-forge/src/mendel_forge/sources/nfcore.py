"""nf-core modules: the source that ships its own Nextflow.

Largely `ModuleSpec` read **forwards**. The same regex parser `conformance.py` uses to check
a contract against a module is used here to propose one — one parser, so a syntax nf-core
adopts that this cannot read fails loudly in both directions rather than in one.

**What it does not derive is the point.** A module declares an output as `type: file` with a
filename pattern; "sorted" exists only in an English description. The semantic overlay —
`type_id`, `state`, `roles` — is the missing ~40% and is every hole this source produces.
"""

from pathlib import Path

from comeni_core import yaml_strict
from comeni_core.declared.module import Module
from mendel_compiler.modulespec import ModuleSpec

from mendel_forge.observe import Excerpt, Fact, Observation
from mendel_forge.sources import ToolRef, register


class NfCoreSource:
    name = "nf-core"

    def discover(self, root: Path) -> list[ToolRef]:
        """Every nf-core module the **layer** carries, read out of the declarations.

        `root` was `vendor/` in the engine's repository until Plan 5A and is the registry layer
        now. **Both halves of the forge's `root` moved together** — `--source-root` is the
        layer — and the forge is otherwise untouched, which is spec §5's rule for this plan.

        FORGE-REWORK — Plan 5A repointed this at the layer. Issue #64 (check against
        *upstream* rather than the vendored copy) and issue #77 (a real catalogue total) both
        live here, and `comeni-vendor` now owns fetching, which is most of what a `Source`
        was for.

        **It reads `module.yml`, not a path.** The obvious translation was to glob
        `tools/nf-core/*/module/main.nf`, and that would have written the curated registry's
        *convention* into the engine: invariant 11 says a layer's layout is the author's
        business, and a laboratory arranging its overlay differently would have discovered
        nothing while `mendel build` resolved against it perfectly. A module says where it is
        by being declared, which is comeni-registry#1's whole argument applied one kind later.

        Issue #77 is unchanged by any of this: discovery reads what somebody already vendored,
        which is not the size of the known world.
        """
        return sorted(
            (
                ToolRef(source=self.name, ident=key.removeprefix(f"{self.name}/"))
                for key in self._modules(root)
            ),
            key=lambda r: r.ident,
        )

    def ingest(self, ref: ToolRef, root: Path) -> Observation:
        found = self._modules(root).get(f"{self.name}/{ref.ident}")
        if found is None or found.source is None:
            raise FileNotFoundError(
                f"no layer under {root} declares module {self.name}/{ref.ident}"
            )
        module_dir = found.source
        main_nf = module_dir / "main.nf"
        spec = ModuleSpec.parse(main_nf)
        # **Relative to the source root, never absolute.** An absolute locator carries the
        # machine it was read on into every draft and every golden file — the same defect
        # issue #46 found in `digest_of_directory`, where walking `.git` made a layer digest
        # depend on the checkout path while `make verify` stayed green. A locator has to name
        # a file a reviewer on another machine can open.
        at = str(main_nf.relative_to(root))
        source_lines = main_nf.read_text().splitlines()

        def fact(value: object, position: str | None = None) -> Fact:
            """`position` is a key into `ModuleSpec.lines`.

            **`None` means derived rather than read.** Citing a line for a value nothing read
            from that line is a false citation, and worse than a vague one — a reviewer who
            follows it finds text that does not support the claim, and has no way to tell that
            from a claim that is simply wrong.
            """
            line = spec.lines.get(position) if position else None
            if line is None:
                return Fact(value=value, evidence=Excerpt(locator=at, text=f"read from {at}"))
            # A block fact quotes the whole block. `input:` and `output:` are headers; what
            # they declare underneath is the evidence, and a citation reading `text: "output:"`
            # names a real line while teaching a reader nothing.
            end = spec.lines.get(f"{position}.end", line)
            quoted = [text.strip() for text in source_lines[line - 1 : end]]
            # A block match runs to the blank line before the next keyword, so the span ends
            # in whitespace. Quoting it would cite a line that says nothing and put a stray
            # newline in every golden file.
            while len(quoted) > 1 and not quoted[-1]:
                quoted.pop()
            end = line + len(quoted) - 1
            locator = f"{at}:{line}" if end == line else f"{at}:{line}-{end}"
            return Fact(value=value, evidence=Excerpt(locator=locator, text="\n".join(quoted)))

        facts = {
            "process": fact(spec.process, "process"),
            "emits": fact(list(spec.emits), "outputs"),
            "input_arity": fact(len(spec.inputs), "inputs"),
            "input_names": fact([slot.names for slot in spec.inputs], "inputs"),
            # The input block, not the first read: the fact is the *set* of keys, and citing
            # one of them would claim the others came from there too.
            "meta_reads": fact(sorted({read.key for read in spec.meta_reads}), "inputs"),
            "reads_ext_args": fact(spec.reads_ext_args, "reads_ext_args"),
            "reads_ext_prefix": fact(spec.reads_ext_prefix, "reads_ext_prefix"),
            "nf_include": fact(f"modules/nf-core/{ref.ident}/main"),
        }
        if spec.container:
            facts["container"] = fact(spec.container, "container")
        if spec.documented:
            facts["documented_inputs"] = fact([d.name for d in spec.documented])

        return Observation(
            source=self.name, ref_id=str(ref), facts=facts, prose=_prose(module_dir, root)
        )

    @staticmethod
    def _modules(root: Path) -> dict[str, Module]:
        """The layer's modules, by key. Stacked, so an overlay's copy wins — the same answer
        `mendel build`'s conformance gets, rather than a second walk that could disagree."""
        return dict(Module.load(root).entries)


def _prose(module_dir: Path, root: Path) -> list[Excerpt]:
    """`meta.yml` is a scaffold, not a contract — it declares outputs as `type: file` with a
    filename pattern. Its English is still the best evidence a reviewer has for what a port
    *means*, which is exactly the judgement a hole asks for.

    **One excerpt per port, in English.** This used to emit `text=str(entry)` for the whole
    `input:` and `output:` blocks — a Python `repr` of parsed YAML, nested quotes and `\\n`
    escapes and Groovy-map noise, with the one useful sentence buried inside it. Two things
    were wrong with that and both were measured rather than argued:

    - **A reader learns nothing from it.** `'FastQC report'` and `pattern: *.html` are in
      there, and no model picked them out — every output port of `fastqc` was answered
      `fastq.reads`, the tool's *input* type, which is what the description mentions.
    - **It is enormous.** `star/align` declares nineteen emit channels, so its `output:` repr
      ran to ~13,000 characters. The prompt built from it buried its own instruction, and the
      model answered by *explaining the YAML* instead of choosing: twenty-nine holes, twenty-nine
      declines, fifty minutes.

    Locators are per port — `meta.yml:output.html` — so a caller asking about one port can
    select the evidence for that port rather than sending all of them.
    """
    meta = module_dir / "meta.yml"
    if not meta.exists():
        return []
    data = yaml_strict.load(meta)
    if not isinstance(data, dict):
        return []
    at = meta.relative_to(root)
    found = []
    if isinstance(data.get("description"), str):
        found.append(Excerpt(locator=f"{at}:description", text=data["description"].strip()))
    for key in ("input", "output"):
        for port, described in _described_ports(data.get(key)).items():
            found.append(Excerpt(locator=f"{at}:{key}.{port}", text=described))
    return found


def _described_ports(entry: object) -> dict[str, str]:
    """`{port name: one English line}` out of `meta.yml`'s nested input/output shape.

    nf-core writes an output as `{name: [[{meta: …}, {"*.html": {description, pattern}}]]}`
    and an input as a bare list of those inner lists. Both bottom out in `{name: {description,
    pattern, type}}`, so one walk handles them: collect every mapping that has a `description`,
    and name it after the key it hangs off.

    **Best effort, and silence rather than noise when the shape is unfamiliar.** A `meta.yml`
    this cannot read yields no excerpt for that block, which leaves a hole with less evidence —
    strictly better than a hole with a `repr` of a dict, which is what it replaced.
    """
    found: dict[str, str] = {}

    def described(node: object) -> str | None:
        if not isinstance(node, dict):
            return None
        parts = [
            str(node[k]).strip()
            for k in ("description", "pattern")
            if isinstance(node.get(k), str) and node[k].strip()
        ]
        return " — ".join(parts) or None

    def walk(node: object, port: str | None) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item, port)
            return
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if key == "meta":
                continue  # the Groovy sample map, on every single port and never the answer
            text = described(value)
            name = port or str(key)
            if text and name not in found:
                found[name] = f"{key}: {text}" if port else text
            else:
                walk(value, port or str(key))

    if isinstance(entry, dict):
        for port, value in entry.items():
            walk(value, port)
    else:
        walk(entry, None)
    return found


register(NfCoreSource())
