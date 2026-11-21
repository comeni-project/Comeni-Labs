"""A container tag resolved to the digest a run pulls (#308).

An anonymous OCI distribution `HEAD /v2/<repository>/manifests/<tag>`, reading
`Docker-Content-Digest`. A registry that asks for a bearer token (Wave does; quay.io does not)
names where to get an anonymous one in its `WWW-Authenticate` challenge, and that is asked once.
A multi-architecture image answers with its index digest, which keeps every architecture.

Network I/O, so it lives here rather than in a pure package. `http` is injectable so tests replay
recorded answers and never reach a registry.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path

from comeni_core.spell.images import image_of

ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])
"""Index types first, so a multi-architecture image answers with its index."""

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")

Http = Callable[[str, Mapping[str, str]], tuple[int, Mapping[str, str], bytes]]


class ImageError(Exception):
    pass


def _urllib(url: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
    method = "HEAD" if "/manifests/" in url else "GET"
    request = urllib.request.Request(url, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as reply:  # noqa: S310 (https only)
            return reply.status, {k.lower(): v for k, v in reply.headers.items()}, reply.read()
    except urllib.error.HTTPError as error:
        return error.code, {k.lower(): v for k, v in error.headers.items()}, b""


def _challenge(header: str) -> dict[str, str]:
    scheme, _, rest = header.partition(" ")
    if scheme.lower() != "bearer":
        return {}
    return dict(re.findall(r'(\w+)="([^"]*)"', rest))


def digest_of_image(ref: str, *, http: Http | None = None) -> str:
    """The digest `ref`'s tag points at now. A reference already pinned is returned as it is."""
    http = http or _urllib
    try:
        image = image_of(ref)
    except ValueError as error:
        raise ImageError(str(error)) from error
    if image.digest:
        return image.digest
    if not image.tag:
        raise ImageError(f"{ref} has no tag; name one rather than resolving `latest`")
    host, _, repository = image.name.partition("/")
    if "." not in host and ":" not in host and host != "localhost":
        host, repository = "registry-1.docker.io", image.name
    url = f"https://{host}/v2/{repository}/manifests/{image.tag}"
    headers = {"Accept": ACCEPT}
    status, answered, _ = http(url, headers)
    if status == 401:
        fields = _challenge(answered.get("www-authenticate", ""))
        if "realm" not in fields:
            raise ImageError(f"{ref}: the registry asked for credentials this does not have")
        query = urllib.parse.urlencode({k: fields[k] for k in ("service", "scope") if k in fields})
        token_status, _, body = http(f"{fields['realm']}?{query}", {})
        token = json.loads(body or b"{}") if token_status == 200 else {}
        bearer = token.get("token") or token.get("access_token")
        if not bearer:
            raise ImageError(f"{ref}: no anonymous token from {fields['realm']}")
        status, answered, _ = http(url, {**headers, "Authorization": f"Bearer {bearer}"})
    digest = answered.get("docker-content-digest", "")
    if status != 200 or not _DIGEST.fullmatch(digest):
        raise ImageError(f"{ref}: the registry answered {status} with no sha256 digest")
    return digest


_CONTAINER_LINE = re.compile(r"^container: (?P<ref>\S+)$", re.MULTILINE)


def pin_containers(registry: Path, *, http: Http | None = None) -> list[tuple[Path, str, str]]:
    """Pin every contract's `container:` under `registry/tools` to the digest its tag points at
    now, rewriting that one line and nothing else. Every image is resolved before any file is
    written, so a registry that refuses one leaves the layer as it was. Returns what changed,
    sorted by path."""
    planned = []
    for contract in sorted((registry / "tools").rglob("contract.yml")):
        text = contract.read_text()
        found = _CONTAINER_LINE.search(text)
        if found is None or image_of(found["ref"]).digest:
            continue
        ref = found["ref"]
        pinned = image_of(ref).pinned(digest_of_image(ref, http=http)).ref
        planned.append((contract, ref, pinned, text, found))
    for contract, _, pinned, text, found in planned:
        contract.write_text(text[:found.start("ref")] + pinned + text[found.end("ref"):])
    return [(contract, ref, pinned) for contract, ref, pinned, _, _ in planned]
