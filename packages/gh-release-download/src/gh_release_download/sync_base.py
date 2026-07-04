from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class GitHubReleaseSyncEntry:
    type_name: str
    name: str
    repo: str
    version: str
    asset_pattern: str
    asset_regex: str
    extra: dict[str, object]


class ReleaseSyncType(Protocol):
    type_name: str
    table_path: tuple[str, ...]
    updated_heading: str

    def extra_from_entry(
        self, entry: dict[str, Any], *, name: str, path: Path
    ) -> dict[str, object]: ...

    def require_environment(self) -> None: ...

    def sync(
        self,
        entry: GitHubReleaseSyncEntry,
        *,
        retries: int,
        dry_run: bool,
        force: bool,
    ) -> bool: ...


def normalize_version(version: str) -> str:
    normalized = version.strip()
    if len(normalized) > 1 and normalized[0] in {"v", "V"} and normalized[1].isdigit():
        return normalized[1:]
    return normalized
