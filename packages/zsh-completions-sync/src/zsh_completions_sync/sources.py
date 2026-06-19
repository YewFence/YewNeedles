"""Completion script sources."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, url2pathname, urlopen


HTTP_TIMEOUT = 30
USER_AGENT = "zsh-completions-sync"


@dataclass(frozen=True)
class CommandSource:
    command: tuple[str, ...]


@dataclass(frozen=True)
class LocalFileSource:
    path: Path


@dataclass(frozen=True)
class HttpFileSource:
    url: str


@dataclass(frozen=True)
class GitFileSource:
    repository: str
    path: str
    ref: str | None = None


@dataclass(frozen=True)
class FileSource:
    file: LocalFileSource | HttpFileSource | GitFileSource


@dataclass(frozen=True)
class SourceReadResult:
    content: bytes | None = None
    error: str | None = None


CompletionSource = CommandSource | FileSource


def parse_source(config: Mapping[str, Any]) -> CompletionSource | None:
    command = parse_command(config.get("command"))
    file = config.get("file")

    if file is not None:
        file_source = parse_file_source(file)
        if file_source is None:
            return None
        return FileSource(file=file_source)

    if command is None:
        return None
    return CommandSource(command=command)


def parse_command(value: object) -> tuple[str, ...] | None:
    if (
        isinstance(value, list)
        and len(value) > 0
        and all(isinstance(item, str) and item for item in value)
    ):
        return tuple(value)
    return None


def parse_file_source(value: object) -> LocalFileSource | HttpFileSource | GitFileSource | None:
    if isinstance(value, str) and value:
        return parse_file_string(value)
    if isinstance(value, Mapping):
        return parse_file_mapping(value)
    return None


def parse_file_string(value: str) -> LocalFileSource | HttpFileSource | GitFileSource | None:
    if value.startswith("git+"):
        return parse_git_file_string(value.removeprefix("git+"))

    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return HttpFileSource(url=value)
    if parsed.scheme == "file":
        return LocalFileSource(path=Path(url2pathname(unquote(parsed.path))).expanduser())
    if parsed.scheme:
        return None

    return LocalFileSource(path=Path(os.path.expandvars(value)).expanduser())


def parse_file_mapping(value: Mapping[str, Any]) -> LocalFileSource | HttpFileSource | GitFileSource | None:
    repository = value.get("git", value.get("repo"))
    if isinstance(repository, str) and repository:
        path = value.get("path")
        ref = value.get("ref")
        if isinstance(path, str) and path and (ref is None or isinstance(ref, str)):
            return GitFileSource(repository=repository, path=path.lstrip("/"), ref=ref)
        return None

    url = value.get("url")
    if isinstance(url, str) and url:
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"}:
            return HttpFileSource(url=url)
        if parsed.scheme == "file":
            return LocalFileSource(path=Path(url2pathname(unquote(parsed.path))).expanduser())
        return None

    path = value.get("path")
    if isinstance(path, str) and path:
        return LocalFileSource(path=Path(os.path.expandvars(path)).expanduser())

    return None


def parse_git_file_string(value: str) -> GitFileSource | None:
    separator_index = value.rfind("//")
    if separator_index <= 0:
        return None

    repository = value[:separator_index]
    path_and_query = value[separator_index + 2 :]
    path, _, query = path_and_query.partition("?")
    path = unquote(path).lstrip("/")
    if not repository or not path:
        return None

    query_values = parse_qs(query)
    ref_values = query_values.get("ref", [])
    ref = ref_values[-1] if ref_values else None
    return GitFileSource(repository=repository, path=path, ref=ref)


def read_source(source: CompletionSource) -> SourceReadResult:
    if isinstance(source, CommandSource):
        return read_command_source(source)
    return read_file_source(source)


def read_command_source(source: CommandSource) -> SourceReadResult:
    if not command_exists(source.command):
        return SourceReadResult(error=f"command not found: {source.command[0]}")

    try:
        result = subprocess.run(
            source.command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        return SourceReadResult(error=f"failed to run command {format_command(source.command)}: {error}")

    if result.returncode != 0:
        return SourceReadResult(error=process_error(source.command, result))
    return SourceReadResult(content=result.stdout)


def read_file_source(source: FileSource) -> SourceReadResult:
    if isinstance(source.file, LocalFileSource):
        return read_local_file(source.file)
    if isinstance(source.file, HttpFileSource):
        return read_http_file(source.file)
    return read_git_file(source.file)


def command_exists(command: tuple[str, ...]) -> bool:
    executable = command[0]
    if Path(executable).parent != Path("."):
        return Path(executable).exists()
    return shutil.which(executable) is not None


def read_local_file(source: LocalFileSource) -> SourceReadResult:
    try:
        return SourceReadResult(content=source.path.read_bytes())
    except OSError as error:
        return SourceReadResult(error=f"failed to read local file {source.path}: {error}")


def read_http_file(source: HttpFileSource) -> SourceReadResult:
    request = Request(source.url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return SourceReadResult(content=response.read())
    except (OSError, TimeoutError, URLError, ValueError) as error:
        return SourceReadResult(error=f"failed to read HTTP file {source.url}: {error}")


def read_git_file(source: GitFileSource) -> SourceReadResult:
    if shutil.which("git") is None:
        return SourceReadResult(error="command not found: git")

    with tempfile.TemporaryDirectory() as temp_dir:
        repository_dir = Path(temp_dir) / "repository"
        clone_error = clone_git_repository(source.repository, repository_dir)
        if clone_error is not None:
            return SourceReadResult(error=clone_error)

        revision = "HEAD"
        if source.ref is not None:
            fetch_error = fetch_git_ref(repository_dir, source.ref)
            if fetch_error is not None:
                return SourceReadResult(error=fetch_error)
            revision = "FETCH_HEAD"

        return show_git_file(repository_dir, revision, source.path)


def clone_git_repository(repository: str, destination: Path) -> str | None:
    command = (
        "git",
        "clone",
        "--depth=1",
        "--filter=blob:none",
        "--no-checkout",
        repository,
        str(destination),
    )
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        return f"failed to run command {format_command(command)}: {error}"

    if result.returncode == 0:
        return None

    shutil.rmtree(destination, ignore_errors=True)
    fallback_command = (
        "git",
        "clone",
        "--depth=1",
        "--no-checkout",
        repository,
        str(destination),
    )
    try:
        fallback_result = subprocess.run(
            fallback_command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        return f"failed to run command {format_command(fallback_command)}: {error}"

    if fallback_result.returncode == 0:
        return None
    return process_error(fallback_command, fallback_result)


def fetch_git_ref(repository_dir: Path, ref: str) -> str | None:
    command = ("git", "-C", str(repository_dir), "fetch", "--depth=1", "origin", ref)
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        return f"failed to run command {format_command(command)}: {error}"

    if result.returncode == 0:
        return None
    return process_error(command, result)


def show_git_file(repository_dir: Path, revision: str, path: str) -> SourceReadResult:
    command = ("git", "-C", str(repository_dir), "show", f"{revision}:{path}")
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        return SourceReadResult(error=f"failed to run command {format_command(command)}: {error}")

    if result.returncode != 0:
        return SourceReadResult(error=process_error(command, result))
    return SourceReadResult(content=result.stdout)


def process_error(command: tuple[str, ...], result: subprocess.CompletedProcess[bytes]) -> str:
    message = f"command failed with exit code {result.returncode}: {format_command(command)}"
    stderr = result.stderr.decode(errors="replace").strip()
    if stderr:
        message = f"{message}; {stderr}"
    return message


def format_command(command: tuple[str, ...]) -> str:
    return " ".join(command)
