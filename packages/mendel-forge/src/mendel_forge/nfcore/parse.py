"""One nf-core module folder, read into an `UpstreamModule`.

**Never raises for a module's content.** nf-core holds ~2,100 modules written by hundreds of
people; one that cannot be read is kept with a coded `Problem` and counted, so a sync is never
lost to a single bad file and the catalogue never under-reports.
"""

import re
from pathlib import Path
from typing import Any

import yaml

from mendel_forge.model import Channel, NfTest, Problem, UpstreamModule, UpstreamTool
from mendel_forge.topics import formats_of, topics_of
from mendel_forge.versions import parse_packages, tool_version

_LABEL = re.compile(r"""^\s*label\s+['"](process_\w+)['"]""", re.M)
_TEST = re.compile(r"""^\s*test\(\s*["'](.+?)["']\s*\)""", re.M)
_DATASET = re.compile(r"""modules_testdata_base_path\s*\+\s*['"]([^'"]+)['"]""")
_SINGLE_QUOTED = re.compile(r"'([^']+)'")
_DOUBLE_QUOTED = re.compile(r'"([^"]+)"')


def parse_module(folder: Path, path: str, source: str = "nf-core") -> UpstreamModule:
    problems: list[Problem] = []
    meta = _meta(folder / "meta.yml", problems)
    tools = [_tool(name, props) for name, props in _pairs(meta.get("tools"))]
    packages = _packages(folder / "environment.yml")
    version = tool_version(packages, path, [tool.name for tool in tools])
    if version is None:
        problems.append(Problem(
            code="MF0501",
            says="no conda package is this module's tool, so its tool version is unknown",
        ))
    script = _text_of(folder / "main.nf")
    label = _LABEL.search(script)
    inputs, outputs = _inputs(meta.get("input")), _outputs(meta.get("output"))
    keywords = [str(k) for k in _list(meta.get("keywords"))]
    ontologies = [url for channel in [*inputs, *outputs] for url in channel.ontologies]
    return UpstreamModule(
        source=source,
        path=path,
        name=path,
        description=_text(meta.get("description")),
        keywords=keywords,
        tools=tools,
        inputs=inputs,
        outputs=outputs,
        authors=[str(a) for a in _list(meta.get("authors"))],
        maintainers=[str(m) for m in _list(meta.get("maintainers"))],
        packages=packages,
        tool_version=version,
        containers=_containers(script),
        label=label.group(1) if label else None,
        tests=_tests(folder / "tests" / "main.nf.test"),
        topics=topics_of(keywords, ontologies),
        formats_in=formats_of(inputs),
        formats_out=formats_of(outputs),
        problems=problems,
    )


def _meta(path: Path, problems: list[Problem]) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as error:
        problems.append(Problem(code="MF0500", says=f"meta.yml cannot be read: {error}"))
        return {}
    if not isinstance(data, dict):
        problems.append(Problem(code="MF0500", says="meta.yml is not a mapping"))
        return {}
    return data


def _list(value: object) -> list:
    """A value the schema says is a list; anything else upstream wrote there reads as empty."""
    return value if isinstance(value, list) else []


def _text_of(path: Path) -> str:
    """A file's text, or empty when it is missing or not UTF-8 (`main.nf`, the nf-test)."""
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else ""
    except (OSError, ValueError):
        return ""


def _packages(path: Path) -> list:
    """`environment.yml`'s pins; a file that is missing or malformed pins nothing (MF0501)."""
    try:
        return parse_packages(path.read_text(encoding="utf-8")) if path.is_file() else []
    except (OSError, ValueError, AttributeError, yaml.YAMLError):
        return []


def _text(value: object) -> str | None:
    return str(value).strip() or None if value is not None else None


def _pairs(items: object) -> list[tuple[str, dict[str, Any]]]:
    """`[{name: {props}}, …]` → `[(name, props), …]`, skipping anything not that shape."""
    pairs = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            for name, props in item.items():
                pairs.append((str(name), props if isinstance(props, dict) else {}))
    return pairs


def _tool(name: str, props: dict[str, Any]) -> UpstreamTool:
    licence = props.get("licence") or []
    return UpstreamTool(
        name=name,
        description=_text(props.get("description")),
        homepage=_text(props.get("homepage")),
        documentation=_text(props.get("documentation") or props.get("manual")),
        tool_dev_url=_text(props.get("tool_dev_url")),
        doi=_text(props.get("doi")),
        licence=[str(entry) for entry in (licence if isinstance(licence, list) else [licence])],
        biotools=_text(props.get("identifier")),
    )


def _channel(name: str, props: dict[str, Any]) -> Channel:
    ontologies = [
        str(url)
        for entry in _list(props.get("ontologies"))
        if isinstance(entry, dict)
        for url in entry.values()
    ]
    return Channel(
        name=name,
        type=_text(props.get("type")),
        description=_text(props.get("description")),
        pattern=_text(props.get("pattern")),
        ontologies=ontologies,
    )


def _elements(item: object) -> list[tuple[str, dict[str, Any]]]:
    """One channel's elements without its `meta` maps: a tuple is a list of single-key maps."""
    pairs = _pairs(item if isinstance(item, list) else [item])
    return [(name, props) for name, props in pairs if not re.fullmatch(r"meta\d*", name)]


def _primary(elements: list[tuple[str, dict[str, Any]]]) -> tuple[str, dict[str, Any]] | None:
    """The element that says what the channel carries: its first file, else its first value."""
    files = [e for e in elements if e[1].get("type") in ("file", "directory")]
    return (files or elements or [None])[0]


def _inputs(declared: object) -> list[Channel]:
    channels = []
    for item in declared if isinstance(declared, list) else []:
        primary = _primary(_elements(item))
        if primary is not None:
            channels.append(_channel(*primary))
    return channels


def _outputs(declared: object) -> list[Channel]:
    """Current modules key outputs by emit name; older ones list them like inputs."""
    if not isinstance(declared, dict):
        return _inputs(declared)
    channels = []
    for emit, items in declared.items():
        elements = [e for item in _list(items) for e in _elements(item)]
        primary = _primary(elements)
        if primary is not None:
            channels.append(_channel(str(emit), primary[1]))
    return channels


def _containers(script: str) -> list[str]:
    """Every image the `container` statement names, Singularity's and Docker's alike."""
    lines = script.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().startswith("container ")), None)
    if start is None:
        return []
    statement = lines[start]
    if "${" in statement:
        for line in lines[start + 1:]:
            statement += "\n" + line
            if line.rstrip().endswith('}"'):
                break
    images = [s for s in _SINGLE_QUOTED.findall(statement) if "/" in s]
    return images or [s for s in _DOUBLE_QUOTED.findall(statement) if "/" in s]


def _tests(path: Path) -> list[NfTest]:
    text = _text_of(path)
    starts = list(_TEST.finditer(text))
    tests = []
    for here, after in zip(starts, [*starts[1:], None], strict=False):
        body = text[here.end(): after.start() if after else len(text)]
        tests.append(NfTest(name=here.group(1), datasets=sorted(set(_DATASET.findall(body)))))
    return tests
