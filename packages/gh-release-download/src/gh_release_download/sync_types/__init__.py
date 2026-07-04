from __future__ import annotations

from gh_release_download.sync_base import ReleaseSyncType

from .appimage import AppImageSyncType
from .rpm import RpmSyncType


SYNC_TYPES: dict[str, ReleaseSyncType] = {
    sync_type.type_name: sync_type
    for sync_type in (
        RpmSyncType(),
        AppImageSyncType(),
    )
}


__all__ = ["SYNC_TYPES"]
