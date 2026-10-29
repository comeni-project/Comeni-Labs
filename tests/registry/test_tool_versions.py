"""A registry id's version is the tool's version (forge spec, answer 6; #407).

Six ids had kept an older number after their vendored module moved on (`star/align@1.11.0`
pinned star 2.7.11b), so the id said one tool and the pipeline ran another. Each contract's
version must equal what its vendored `module/environment.yml` pins for its tool: the package
whose name is the tool's folder (`trimgalore` → `trim-galore`, `subread/featurecounts` →
`subread`)."""

import yaml
from mendel_forge.versions import parse_packages, tool_version
from support.paths import REGISTRY


def test_every_contract_names_the_tool_version_its_module_pins():
    contracts = sorted((REGISTRY / "tools").rglob("contract.yml"))
    assert contracts, "no contracts: the registry submodule is not initialised"
    wrong = []
    for path in contracts:
        contract_id = yaml.safe_load(path.read_text())["id"]
        tool_path, version = contract_id.split("/", 1)[1].rsplit("@", 1)
        environment = path.parent / "module" / "environment.yml"
        if not environment.is_file():
            continue
        # The catalogue's rule (`mendel_forge.versions`), so the two cannot disagree.
        pinned = tool_version(parse_packages(environment.read_text()), tool_path, [])
        if pinned is not None and pinned != version:
            wrong.append(f"{contract_id}: its module pins {pinned}")
    assert wrong == [], wrong
