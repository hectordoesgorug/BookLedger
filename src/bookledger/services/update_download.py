"""Download and verify eligible GitHub release assets without installing them."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import threading
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from bookledger.services.update_archive import inspect_archive
from bookledger.services.updates import REPOSITORY_URL, UpdateResult, desktop_package, version_key

MAX_WINDOWS_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
_CHUNK_SIZE = 128 * 1024
_TIMEOUT = 15
_ASSET_NAME = re.compile(r"BookLedger-v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)-Windows-x64-(?:Portable|Fallback)\.zip")
_ALLOWED_REDIRECT_HOSTS = {"release-assets.githubusercontent.com"}


class DownloadCancelled(Exception):
    """Raised when the caller explicitly cancels a download."""


class _ValidatedRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_REDIRECT_HOSTS or parsed.port not in (None, 443) or parsed.username or parsed.password:
            raise ValueError("GitHub redirected the download to an unapproved host.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def update_staging_directory() -> Path:
    """Return per-user update storage outside the portable library and install."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    return (Path(base) if base else Path.home() / "AppData" / "Local") / "BookLedger" / "Updates"


def _validate_result(result: UpdateResult) -> tuple[str, int, str]:
    if result.state != "Update Available" or not result.available or not result.asset_name or not result.asset_url or not result.checksum_url:
        raise ValueError("A verified eligible update is required before downloading.")
    running_package = desktop_package()
    if running_package is None:
        raise ValueError("Packaged Windows builds are required to download updates.")
    version_key(result.available)
    if version_key(result.installed) >= version_key(result.available):
        raise ValueError("Only a newer stable release can be downloaded.")
    if not _ASSET_NAME.fullmatch(result.asset_name):
        raise ValueError("The release asset name is not supported.")
    if not isinstance(result.asset_size, int) or isinstance(result.asset_size, bool) or result.asset_size <= 0:
        raise ValueError("The release did not provide a valid asset size.")
    if not isinstance(result.checksum_size, int) or isinstance(result.checksum_size, bool) or not 0 < result.checksum_size <= MAX_MANIFEST_BYTES:
        raise ValueError("The release did not provide a valid checksum-manifest size.")
    tag = result.release_url.rsplit("/", 1)[-1] if result.release_url else ""
    if tag not in {result.available, f"v{result.available}"}:
        raise ValueError("The release identity does not match the available version.")
    if result.release_url != f"{REPOSITORY_URL}/releases/tag/{tag}":
        raise ValueError("The release URL does not match the official repository.")
    asset_url = f"{REPOSITORY_URL}/releases/download/{tag}/{result.asset_name}"
    checksum_url = f"{REPOSITORY_URL}/releases/download/{tag}/SHA256SUMS.txt"
    if result.asset_url != asset_url or result.checksum_url != checksum_url:
        raise ValueError("The release asset URL does not match the official release.")
    package = "Fallback" if "-Fallback.zip" in result.asset_name else "Portable"
    if running_package != package:
        raise ValueError("The selected Windows package does not match this installation.")
    if result.asset_name != f"BookLedger-{tag}-Windows-x64-{package}.zip":
        raise ValueError("The asset filename does not match the selected release.")
    return tag, min(result.asset_size, MAX_WINDOWS_BYTES), package


def _manifest_digest(content: bytes, asset_name: str) -> str:
    try:
        lines = content.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("The release checksum manifest is not valid ASCII.") from exc
    entries = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *]([^/\\\x00]+)", line)
        if not match:
            raise ValueError("The release checksum manifest has an invalid entry.")
        name = match[2]
        key = name.casefold()
        if key in entries:
            raise ValueError("The release checksum manifest contains duplicate entries.")
        entries[key] = match[1].lower()
    if len(entries.get(asset_name.casefold(), "")) != 64:
        raise ValueError("The release checksum manifest does not contain the selected asset exactly once.")
    return entries[asset_name.casefold()]


def _read_response(opener, url: str, expected_size: int | None, limit: int, cancel: threading.Event, progress):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError("The release download URL is not an official GitHub URL.")
    request = Request(url, headers={"User-Agent": "BookLedger update downloader", "Accept": "application/octet-stream"})
    with opener.open(request, timeout=_TIMEOUT) as response:
        final = urlsplit(response.geturl())
        if final.scheme != "https" or final.hostname not in {"github.com", *_ALLOWED_REDIRECT_HOSTS} or final.port not in (None, 443):
            raise ValueError("The final download host is not approved.")
        announced = response.headers.get("Content-Length")
        if announced is not None:
            if not announced.isdecimal() or int(announced) > limit:
                raise ValueError("The server declared an invalid or oversized download.")
            if expected_size is not None and int(announced) != expected_size:
                raise ValueError("The release asset size no longer matches its metadata.")
        chunks = [] if progress is None else None
        digest = hashlib.sha256()
        count = 0
        while True:
            if cancel.is_set():
                raise DownloadCancelled()
            chunk = response.read(_CHUNK_SIZE)
            if not chunk:
                break
            count += len(chunk)
            if count > limit or expected_size is not None and count > expected_size:
                raise ValueError("The download exceeded its declared or configured size limit.")
            digest.update(chunk)
            if chunks is not None:
                chunks.append(chunk)
            if progress is not None:
                progress(count, expected_size)
        if expected_size is not None and count != expected_size:
            raise ValueError("The download ended before the declared asset size was received.")
        return b"".join(chunks) if chunks is not None else digest.hexdigest(), count


def download_update(result: UpdateResult, cancel: threading.Event, *, staging: Path | None = None, progress=None) -> Path:
    """Download, hash, and retain the selected release file; never install it."""
    tag, limit, package = _validate_result(result)
    size = result.asset_size
    if size is None or size > limit:
        raise ValueError("The release asset exceeds the configured size limit.")
    root = (staging or update_staging_directory()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < size + MAX_MANIFEST_BYTES:
        raise OSError("There is not enough free storage for this update and its verification data.")
    operation_dir = root / f"{tag}-{package}-{uuid4().hex}"
    operation_dir.mkdir()
    partial = operation_dir / (result.asset_name + ".partial")
    final = operation_dir / result.asset_name
    opener = build_opener(_ValidatedRedirects())
    try:
        manifest_url = result.checksum_url
        manifest, manifest_size = _read_response(opener, manifest_url, result.checksum_size, MAX_MANIFEST_BYTES, cancel, None)
        if manifest_size == 0:
            raise ValueError("The release checksum manifest is empty.")
        expected = _manifest_digest(manifest, result.asset_name)
        if cancel.is_set():
            raise DownloadCancelled()
        received = 0
        digest = hashlib.sha256()
        with partial.open("xb") as output:
            request = Request(result.asset_url, headers={"User-Agent": "BookLedger update downloader", "Accept": "application/octet-stream"})
            with opener.open(request, timeout=_TIMEOUT) as response:
                final_url = urlsplit(response.geturl())
                if final_url.scheme != "https" or final_url.hostname not in {"github.com", *_ALLOWED_REDIRECT_HOSTS} or final_url.port not in (None, 443):
                    raise ValueError("The final download host is not approved.")
                announced = response.headers.get("Content-Length")
                if announced is not None and (not announced.isdecimal() or int(announced) != size):
                    raise ValueError("The release asset size no longer matches its metadata.")
                while True:
                    if cancel.is_set():
                        raise DownloadCancelled()
                    chunk = response.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > size or received > limit:
                        raise ValueError("The download exceeded its declared or configured size limit.")
                    digest.update(chunk)
                    output.write(chunk)
                    if progress is not None:
                        progress("Downloading", received, size)
            output.flush()
            os.fsync(output.fileno())
        if received != size:
            raise ValueError("The download ended before the declared asset size was received.")
        if digest.hexdigest() != expected:
            raise ValueError("The downloaded asset failed SHA-256 verification.")
        if package in {"Portable", "Fallback"}:
            if progress is not None:
                progress("Verifying", received, size)
            inspect_archive(partial, f"{expected}  {result.asset_name}\n", result.asset_name, package)
        else:
            with partial.open("rb") as source:
                if not source.read(4).startswith(b"PK"):
                    raise ValueError("The selected Android asset is not a ZIP-based APK.")
        if cancel.is_set():
            raise DownloadCancelled()
        os.rename(partial, final)
        return final
    except BaseException:
        try:
            partial.unlink(missing_ok=True)
            operation_dir.rmdir()
        except OSError:
            pass
        raise
