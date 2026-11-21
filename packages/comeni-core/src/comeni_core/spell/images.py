"""A container image reference split into name, tag and digest (#308).

`ContainerRef` stays a label (`marks.py`): OCI reference syntax is not this repository's to own.
This reads only the shape a contract's `container:` takes, `name[:tag][@sha256:<64 hex>]`, so a
contract can say both the tag a person reads and the digest a run pulls.
"""

from pydantic import BaseModel, ConfigDict

_HEX = frozenset("0123456789abcdef")


def is_digest(text: str) -> bool:
    """`sha256:` and 64 lower-case hex digits. Spelled out rather than a regex: `re` is off this
    package's import allowlist (`tests/support/purity.py`), as `marks.py` says."""
    body = text.removeprefix("sha256:")
    return body != text and len(body) == 64 and set(body) <= _HEX


class Image(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    tag: str | None = None
    digest: str | None = None

    @property
    def ref(self) -> str:
        return (self.name + (f":{self.tag}" if self.tag else "")
                + (f"@{self.digest}" if self.digest else ""))

    def pinned(self, digest: str) -> "Image":
        if not is_digest(digest):
            raise ValueError(f"{digest!r} is not a sha256 digest")
        return self.model_copy(update={"digest": digest})

    def unpinned(self) -> "Image":
        return self.model_copy(update={"digest": None})


def image_of(ref: str) -> Image:
    """`ref` split; a tag is a colon after the last slash, so a registry port is not one."""
    if not ref or any(c.isspace() for c in ref):
        raise ValueError(f"{ref!r} is not an image reference")
    rest, at, digest = ref.partition("@")
    if at and not is_digest(digest):
        raise ValueError(f"{ref!r} carries {digest!r}, which is not a sha256 digest")
    slash = rest.rfind("/")
    colon = rest.rfind(":")
    name, tag = (rest[:colon], rest[colon + 1:]) if colon > slash else (rest, None)
    if not name or tag == "":
        raise ValueError(f"{ref!r} is not an image reference")
    return Image(name=name, tag=tag, digest=digest or None)
