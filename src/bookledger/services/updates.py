"""Read-only discovery of official stable releases; no download or installation."""

from __future__ import annotations

import json
import platform
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


REPOSITORY_URL = "https://github.com/hectordoesgorug/BookLedger"
LATEST_RELEASE_URL = "https://api.github.com/repos/hectordoesgorug/BookLedger/releases/latest"
_VERSION = re.compile(
    r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


def version_key(value: str) -> tuple:
    match = _VERSION.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise ValueError("A valid semantic version is required.")
    prerelease = match[4]
    parts = prerelease.split(".") if prerelease else []
    if any(part.isdigit() and len(part) > 1 and part.startswith("0") for part in parts):
        raise ValueError("Invalid prerelease identifier.")
    return (
        *(int(match[i]) for i in (1, 2, 3)),
        0 if prerelease else 1,
        tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts),
    )


def desktop_package() -> str | None:
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return None
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        return None
    root = Path(sys.executable).resolve().parent
    if (root / "_internal").is_dir():
        return "Fallback"
    # PyInstaller one-file unpacks beside a temporary _MEIPASS, not the executable.
    unpacked = getattr(sys, "_MEIPASS", None)
    if unpacked and Path(unpacked).resolve().parent != root:
        return "Portable"
    return None


@dataclass(frozen=True)
class UpdateResult:
    state: str
    installed: str
    available: str | None = None
    notes: str = ""
    message: str = ""
    release_url: str | None = None
    asset_url: str | None = None
    checksum_url: str | None = None
    asset_name: str | None = None
    asset_size: int | None = None
    checksum_size: int | None = None


def release_result(payload: object, installed: str, package: str | None) -> UpdateResult:
    current = version_key(installed)
    if not isinstance(payload, dict) or payload.get("draft") is not False or payload.get("prerelease") is not False:
        raise ValueError("No valid stable release was returned.")
    tag = payload.get("tag_name")
    available = version_key(tag)
    if available[3] != 1:
        raise ValueError("A prerelease tag cannot be a stable update.")
    url = f"{REPOSITORY_URL}/releases/tag/{tag}"
    notes = payload.get("body")
    assets = payload.get("assets")
    if payload.get("html_url") != url or not isinstance(notes, str) or not isinstance(assets, list):
        raise ValueError("Release information is incomplete.")
    base = dict(installed=installed, available=tag.removeprefix("v"), notes=notes, release_url=url)
    if package not in {"Portable", "Fallback", "Android"}:
        discovery = "No newer stable version is available." if available <= current else "A newer stable version is available for manual review."
        return UpdateResult("Unsupported Update", **base, message=f"{discovery} This development build or platform does not support packaged updates. Review releases manually.")
    if available <= current:
        return UpdateResult("Up to Date", **base, message="No newer stable version is available.")
    suffix = "Android.apk" if package == "Android" else f"Windows-x64-{package}.zip"
    asset_name = f"BookLedger-{tag}-{suffix}"

    def asset(name):
        matches = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == name]
        expected = f"{REPOSITORY_URL}/releases/download/{tag}/{name}"
        if len(matches) != 1:
            return None
        asset = matches[0]
        return (expected, asset["size"]) if (
            asset.get("browser_download_url") == expected and asset.get("state") == "uploaded"
            and isinstance(asset.get("size"), int) and not isinstance(asset["size"], bool) and asset["size"] > 0
        ) else None

    archive, checksums = asset(asset_name), asset("SHA256SUMS.txt")
    if not archive or not checksums:
        return UpdateResult("Unsupported Update", **base, message="The release is missing a complete platform asset or checksum manifest.")
    return UpdateResult(
        "Update Available", **base, asset_url=archive[0], checksum_url=checksums[0],
        asset_name=asset_name, asset_size=archive[1], checksum_size=checksums[1],
        message="Review the official release instructions. This check does not download or install updates. Back up the desktop library before a manual upgrade.",
    )


def check_for_updates(installed: str, package: str | None) -> UpdateResult:
    try:
        version_key(installed)
    except ValueError:
        return UpdateResult("Unsupported Update", installed, message="The installed version is unavailable or malformed.")
    request = urllib.request.Request(LATEST_RELEASE_URL, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "BookLedger update check",
    })
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.geturl() != LATEST_RELEASE_URL:
                raise ValueError("Unexpected release endpoint redirect.")
            content = response.read(2 * 1024 * 1024 + 1)
            if len(content) > 2 * 1024 * 1024:
                raise ValueError("Release response is too large.")
            return release_result(json.loads(content.decode("utf-8")), installed, package)
    except urllib.error.HTTPError as exc:
        message = "GitHub refused or rate-limited the request. Try again later." if exc.code in (403, 429) else f"GitHub release check failed (HTTP {exc.code})."
    except (TimeoutError, urllib.error.URLError, OSError):
        message = "Could not reach GitHub. Check the connection and try again."
    except (ValueError, UnicodeError, TypeError):
        message = "GitHub returned incomplete or unexpected release information."
    return UpdateResult("Unable to Check", installed, message=message)
