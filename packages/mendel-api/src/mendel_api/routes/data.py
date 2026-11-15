"""An analysis's data (#511): the folder tree under the data roots, and (from plan Task 4) the
folders an analysis ticks and what was found in them."""

from fastapi import APIRouter

from mendel_api.refusals import REFUSES
from mendel_api.services.data import roots
from mendel_api.settings import settings

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/tree", operation_id="readDataTree", summary="A folder under the data roots",
            responses=REFUSES)
def read_tree(path: str | None = None) -> roots.FolderListing:
    """The folder's subfolders and file count; no `path` lists the roots themselves."""
    return roots.list_folder(path, settings.data_roots)
