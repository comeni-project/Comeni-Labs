"""The folders Comeni may read (`MENDEL_DATA_ROOTS`), and the one check every path passes.

**Resolve, then compare.** A path is resolved strictly (it must exist, and every `..` and
symlink is followed) and must then sit under a resolved root. Comparing the path as written would
let `root/../etc` or a symlink inside a root reach anywhere on the machine.
"""

import os
from pathlib import Path

from comeni_core.diagnostics import coded
from pydantic import BaseModel


class Looks(BaseModel):
    """How many of a folder's files are of one kind, by extension (`kinds.looks_like`)."""

    type_id: str
    count: int


class Folder(BaseModel):
    name: str
    path: str
    files: int
    folders: int = 0
    """How many subfolders it has: none, and the tree shows nothing to open."""
    looks_like: list[Looks] = []
    """Its files counted by kind (`kinds.looks_like`), filled by the route."""


class FolderFile(BaseModel):
    name: str
    size: int
    type_id: str | None = None


class FolderListing(BaseModel):
    path: str | None
    """The folder listed; `None` for the roots themselves."""
    folders: list[Folder]
    files: int
    entries: list[FolderFile] = []


def inside_roots(path: str | Path, roots: list[Path]) -> Path:
    """`path`, resolved, when it is inside one of `roots`; otherwise a coded refusal."""
    if not roots:
        raise ValueError(coded("MI0222", "no data folders are configured on this installation"))
    try:
        resolved = Path(path).resolve(strict=True)
    except (OSError, RuntimeError):
        raise ValueError(coded("MI0221", f"{path} is not a folder Comeni can read")) from None
    for root in roots:
        try:
            if resolved.is_relative_to(root.resolve(strict=True)):
                return resolved
        except OSError:
            continue
    raise ValueError(coded("MI0221", f"{path} is not a folder Comeni can read"))


def inside_folder(path: str | Path, roots: list[Path]) -> Path:
    """`path`, resolved, when it is a folder inside one of `roots`; a file is refused too."""
    resolved = inside_roots(path, roots)
    if not resolved.is_dir():
        raise ValueError(coded("MI0221", f"{path} is not a folder Comeni can read"))
    return resolved


def _visible(entries):
    return [e for e in entries if not e.name.startswith(".")]


def _count_files(folder: Path) -> int:
    return _count(folder)[0]


def _count(folder: Path) -> tuple[int, int]:
    """Files and subfolders, hidden ones left out."""
    try:
        with os.scandir(folder) as entries:
            visible = _visible(entries)
            return (sum(1 for e in visible if e.is_file()), sum(1 for e in visible if e.is_dir()))
    except OSError:
        return (0, 0)


def list_folder(path: Path | str | None, roots: list[Path], *, offset: int = 0) -> FolderListing:
    """A folder's subfolders, each with how many files it holds, and its own file count. Hidden
    entries are left out. `None` lists the roots."""
    if path is None:
        if not roots:
            raise ValueError(coded("MI0222", "no data folders are configured on this installation"))
        found = [r.resolve() for r in roots if r.is_dir()]
        return FolderListing(path=None, files=0, folders=[
            Folder(name=r.name or str(r), path=str(r), files=_count(r)[0], folders=_count(r)[1])
            for r in found])
    folder = inside_folder(path, roots)
    try:
        with os.scandir(folder) as entries:
            visible = _visible(entries)
            file_entries = []
            for entry in sorted(visible, key=lambda e: e.name):
                try:
                    resolved = inside_roots(entry.path, roots)
                    if resolved.is_file():
                        file_entries.append(entry)
                except (ValueError, OSError):
                    continue
            files = len(file_entries)
            metadata = []
            for entry in file_entries[offset:offset + 200]:
                try:
                    metadata.append(FolderFile(name=entry.name, size=entry.stat().st_size))
                except OSError:
                    continue
            subs = []
            for e in visible:
                # A subfolder that is a link out of the roots is not listed, nor looked into.
                try:
                    inside = inside_folder(e.path, roots)
                except ValueError:
                    continue
                files_in, folders_in = _count(inside)
                subs.append(Folder(name=e.name, path=str(inside), files=files_in,
                                   folders=folders_in))
    except PermissionError:
        raise ValueError(coded("MI0221", f"{path} is not a folder Comeni can read")) from None
    return FolderListing(path=str(folder), files=files, entries=metadata,
                         folders=sorted(subs, key=lambda f: f.name))
