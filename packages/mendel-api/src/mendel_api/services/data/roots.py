"""The folders Comeni may read (`MENDEL_DATA_ROOTS`), and the one check every path passes.

**Resolve, then compare.** A path is resolved strictly (it must exist, and every `..` and
symlink is followed) and must then sit under a resolved root. Comparing the path as written would
let `root/../etc` or a symlink inside a root reach anywhere on the machine.
"""

import os
from pathlib import Path

from comeni_core.diagnostics import coded
from pydantic import BaseModel


class Folder(BaseModel):
    name: str
    path: str
    files: int


class FolderListing(BaseModel):
    path: str | None
    """The folder listed; `None` for the roots themselves."""
    folders: list[Folder]
    files: int


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
    try:
        with os.scandir(folder) as entries:
            return sum(1 for e in _visible(entries) if e.is_file())
    except OSError:
        return 0


def list_folder(path: Path | str | None, roots: list[Path]) -> FolderListing:
    """A folder's subfolders, each with how many files it holds, and its own file count. Hidden
    entries are left out. `None` lists the roots."""
    if path is None:
        if not roots:
            raise ValueError(coded("MI0222", "no data folders are configured on this installation"))
        found = [r.resolve() for r in roots if r.is_dir()]
        return FolderListing(path=None, files=0, folders=[
            Folder(name=r.name or str(r), path=str(r), files=_count_files(r)) for r in found])
    folder = inside_folder(path, roots)
    try:
        with os.scandir(folder) as entries:
            visible = _visible(entries)
            files = sum(1 for e in visible if e.is_file())
            subs = []
            for e in visible:
                # A subfolder that is a link out of the roots is not listed, nor looked into.
                try:
                    inside = inside_folder(e.path, roots)
                except ValueError:
                    continue
                subs.append(Folder(name=e.name, path=str(inside), files=_count_files(inside)))
    except PermissionError:
        raise ValueError(coded("MI0221", f"{path} is not a folder Comeni can read")) from None
    return FolderListing(path=str(folder), files=files,
                         folders=sorted(subs, key=lambda f: f.name))
