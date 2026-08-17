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
from mendel_compiler.modulespec import ModuleSpec

from mendel_forge.observe import Excerpt, Fact, Observation
from mendel_forge.sources import ToolRef, register


class NfCoreSource:
    name = "nf-core"

    def discover(self, root: Path) -> list[ToolRef]:
        found = [
            ToolRef(
                source=self.name,
                ident=str(main_nf.parent.relative_to(root / "modules" / "nf-core")),
            )
            for main_nf in (root / "modules" / "nf-core").rglob("main.nf")
        ]
        return sorted(found, key=lambda r: r.ident)

    def ingest(self, ref: ToolRef, root: Path) -> Observation:
        module_dir = root / "modules" / "nf-core" / ref.ident
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


def _prose(module_dir: Path, root: Path) -> list[Excerpt]:
    """`meta.yml` is a scaffold, not a contract — it declares outputs as `type: file` with a
    filename pattern. Its English is still the best evidence a reviewer has for what a port
    *means*, which is exactly the judgement a hole asks for."""
    meta = module_dir / "meta.yml"
    if not meta.exists():
        return []
    data = yaml_strict.load(meta)
    if not isinstance(data, dict):
        return []
    at = meta.relative_to(root)
    found = []
    if isinstance(data.get("description"), str):
        found.append(Excerpt(locator=f"{at}:description", text=data["description"]))
    for key in ("input", "output"):
        entry = data.get(key)
        if entry is not None:
            found.append(Excerpt(locator=f"{at}:{key}", text=str(entry)))
    return found


register(NfCoreSource())
