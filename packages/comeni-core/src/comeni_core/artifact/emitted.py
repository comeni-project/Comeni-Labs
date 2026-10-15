"""Record the generated files and the pipeline content used to produce them.

Emitted.of() takes O(f log f + b) time for f file names and b bytes read.
It retains O(f) fingerprint records and reads one complete file at a time,
so peak file-buffer memory depends on the largest selected file.
"""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from comeni_core.artifact.digest import digest_of_bytes
from comeni_core.spell.marks import Digest, NfPath


class EmittedFile(BaseModel):
    """Generated file name and fingerprint of its exact contents."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: NfPath
    digest: Digest


class Emitted(BaseModel):
    """Generated-file fingerprints and the pipeline content fingerprint they came from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    """Pipeline schema version used when calculating from_digest."""

    files: list[EmittedFile] = []
    from_digest: Digest | None = None
    """Source pipeline content digest, calculated with emitted set to None; None if unrecorded."""

    @classmethod
    def of(
        cls,
        directory: Path,
        names: Sequence[str],
        from_digest: Digest | None = None,
        schema_version: int = 1,
    ) -> "Emitted":
        """Fingerprint the named generated files in deterministic name order."""
        return cls(
            files=[
                EmittedFile(name=name, digest=digest_of_bytes((directory / name).read_bytes()))
                for name in sorted(names)
            ],
            from_digest=from_digest,
            schema_version=schema_version,
        )
