"""Read-only archive inspection prototype. Never extracts or replaces files."""

import hashlib
from io import BytesIO
from pathlib import Path
from pathlib import PurePosixPath
import re
import stat
from zipfile import ZipFile


MAX_UNCOMPRESSED = 512 * 1024 * 1024
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def inspect_archive(content: bytes | Path, checksums: str, asset_name: str, package: str) -> tuple[str, ...]:
    """Validate archive bytes/paths without extracting or loading a file archive into memory."""
    expected = []
    for line in checksums.splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line)
        if match and match[2] == asset_name:
            expected.append(match[1].lower())
    if isinstance(content, Path):
        digest = hashlib.sha256()
        with content.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        archive_source = content
    else:
        digest = hashlib.sha256(content)
        archive_source = content
    if len(expected) != 1 or digest.hexdigest() != expected[0]:
        raise ValueError("Missing, ambiguous, or incorrect SHA-256.")
    if package not in {"Portable", "Fallback"}:
        raise ValueError("Unsupported package layout.")
    root = "BookLedger" if package == "Portable" else "Fallback"
    seen, files = set(), []
    total = 0
    with ZipFile(BytesIO(archive_source) if isinstance(archive_source, bytes) else archive_source) as archive:
        if len(archive.infolist()) > 10000:
            raise ValueError("Archive has too many entries.")
        for entry in archive.infolist():
            name = entry.orig_filename.rstrip("/")
            parts = name.split("/")
            if (
                "\\" in name or name.startswith("/") or parts[0] != root
                or (not entry.is_dir() and len(parts) < 2)
                or any(not part or part in {".", ".."} or part[-1] in " ." or ":" in part
                       or part.split(".")[0].casefold() in _RESERVED
                       or re.search(r'[<>"|?*\x00-\x1f]', part) for part in parts)
                or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1
            ):
                raise ValueError("Unsafe archive entry.")
            key = name.casefold()
            if key in seen:
                raise ValueError("Duplicate Windows path.")
            seen.add(key)
            total += entry.file_size
            if total > MAX_UNCOMPRESSED:
                raise ValueError("Archive is too large.")
            relative = PurePosixPath(*parts[1:]).as_posix()
            if not entry.is_dir():
                if parts[1:2] and (parts[1].casefold() in {"data", "backups", "config.json", ".bookledger-instance.lock"}):
                    raise ValueError("Release contains protected user data.")
                with archive.open(entry) as stream:
                    actual_size = 0
                    while chunk := stream.read(64 * 1024):
                        actual_size += len(chunk)
                        if actual_size > entry.file_size or total - entry.file_size + actual_size > MAX_UNCOMPRESSED:
                            raise ValueError("Archive entry exceeds its declared or allowed size.")
                    if actual_size != entry.file_size:
                        raise ValueError("Archive entry size does not match its directory record.")
                files.append(relative)
    if "BookLedger.exe" not in files:
        raise ValueError("Missing application executable.")
    if package == "Fallback" and not any(name.startswith("_internal/") for name in files):
        raise ValueError("Missing fallback runtime.")
    return tuple(files)
