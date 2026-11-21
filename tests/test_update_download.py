import hashlib
from dataclasses import replace
from io import BytesIO
import threading
from urllib.error import HTTPError
from urllib.request import Request
from zipfile import ZipFile

import pytest

from bookledger.services import update_download, updates


class Response:
    def __init__(self, content, url, *, headers=None):
        self._content = BytesIO(content)
        self._url = url
        self.headers = headers or {"Content-Length": str(len(content))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self._url

    def read(self, size):
        return self._content.read(size)


class Opener:
    def __init__(self, responses):
        self.responses = responses

    def open(self, request, timeout):
        assert timeout == update_download._TIMEOUT
        assert request.get_header("Authorization") is None
        response = self.responses[request.full_url]
        if isinstance(response, Exception):
            raise response
        return response


def release_result_for(content, package="Portable", *, manifest_override=None, declared_size=None):
    tag = "v1.2.0"
    suffix = f"Windows-x64-{package}.zip" if package in {"Portable", "Fallback"} else "Android.apk"
    name = f"BookLedger-{tag}-{suffix}"
    manifest = manifest_override if manifest_override is not None else f"{hashlib.sha256(content).hexdigest()}  {name}\n".encode()
    payload = {
        "draft": False,
        "prerelease": False,
        "tag_name": tag,
        "html_url": f"{updates.REPOSITORY_URL}/releases/tag/{tag}",
        "body": "Release notes",
        "assets": [
            {
                "name": asset_name,
                "browser_download_url": f"{updates.REPOSITORY_URL}/releases/download/{tag}/{asset_name}",
                "state": "uploaded",
                "size": asset_size,
            }
            for asset_name, asset_size in ((name, declared_size or len(content)), ("SHA256SUMS.txt", len(manifest)))
        ],
    }
    return updates.release_result(payload, "1.1.0", package), name, manifest


def zip_payload(package="Portable"):
    stream = BytesIO()
    root = "BookLedger" if package == "Portable" else "Fallback"
    with ZipFile(stream, "w") as archive:
        archive.writestr(f"{root}/BookLedger.exe", b"synthetic executable")
        if package == "Fallback":
            archive.writestr("Fallback/_internal/python.dll", b"runtime")
    return stream.getvalue()


def install_opener(monkeypatch, result, manifest, asset):
    package = "Fallback" if result.asset_name and "-Fallback.zip" in result.asset_name else "Portable"
    monkeypatch.setattr(update_download, "desktop_package", lambda: package)
    urls = {
        result.checksum_url: Response(manifest, result.checksum_url),
        result.asset_url: Response(asset, result.asset_url),
    }
    monkeypatch.setattr(update_download, "build_opener", lambda *_args: Opener(urls))


@pytest.mark.parametrize("package", ["Portable", "Fallback"])
def test_streams_hashes_and_structurally_verifies_windows_zip(package, monkeypatch, tmp_path):
    asset = zip_payload(package)
    result, name, manifest = release_result_for(asset, package)
    install_opener(monkeypatch, result, manifest, asset)
    progress = []
    library = tmp_path / "library"
    protected = [library / "data" / "photos" / "cover.jpg", library / "config.json", library / "backups" / "existing.zip"]
    for path in protected:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"user data")

    path = update_download.download_update(
        result, threading.Event(), staging=tmp_path / "profile" / "Updates",
        progress=lambda state, done, total: progress.append((state, done, total)),
    )

    assert path.name == name
    assert path.read_bytes() == asset
    assert path.parents[1] == tmp_path / "profile" / "Updates"
    assert progress[-1][0] == "Verifying"
    assert any(event[0] == "Downloading" for event in progress)
    assert all(path.read_bytes() == b"user data" for path in protected)
    assert len(list((tmp_path / "profile" / "Updates").iterdir())) == 1


@pytest.mark.parametrize("manifest", [b"", b"malformed entry\n", b"0" * 64 + b"  other.zip\n"])
def test_bad_checksum_manifest_removes_only_its_partial_operation(manifest, monkeypatch, tmp_path):
    asset = zip_payload()
    result, _name, _ = release_result_for(asset)
    result, _, manifest = release_result_for(asset, manifest_override=manifest)
    install_opener(monkeypatch, result, manifest, asset)
    with pytest.raises(ValueError):
        update_download.download_update(result, threading.Event(), staging=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_duplicate_manifest_entries_mismatch_and_truncated_payload_fail(monkeypatch, tmp_path):
    asset = zip_payload()
    result, name, manifest = release_result_for(asset)
    duplicate = manifest + manifest
    result, _, _ = release_result_for(asset, manifest_override=duplicate)
    install_opener(monkeypatch, result, duplicate, asset)
    with pytest.raises(ValueError, match="duplicate"):
        update_download.download_update(result, threading.Event(), staging=tmp_path)
    assert list(tmp_path.iterdir()) == []

    case_variant = manifest + manifest.replace(name.encode(), name.upper().encode())
    result, _, _ = release_result_for(asset, manifest_override=case_variant)
    install_opener(monkeypatch, result, case_variant, asset)
    with pytest.raises(ValueError, match="duplicate"):
        update_download.download_update(result, threading.Event(), staging=tmp_path)
    assert list(tmp_path.iterdir()) == []

    wrong = f"{'0' * 64}  {name}\n".encode()
    result, _, _ = release_result_for(asset, manifest_override=wrong)
    install_opener(monkeypatch, result, wrong, asset)
    with pytest.raises(ValueError, match="SHA-256"):
        update_download.download_update(result, threading.Event(), staging=tmp_path)
    assert list(tmp_path.iterdir()) == []

    result, _, manifest = release_result_for(asset, declared_size=len(asset) + 1)
    install_opener(monkeypatch, result, manifest, asset)
    with pytest.raises(ValueError, match="size|truncated"):
        update_download.download_update(result, threading.Event(), staging=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_cancellation_and_http_failure_leave_no_partial_files(monkeypatch, tmp_path):
    asset = zip_payload()
    result, _, manifest = release_result_for(asset)
    install_opener(monkeypatch, result, manifest, asset)
    canceled = threading.Event()
    canceled.set()
    with pytest.raises(update_download.DownloadCancelled):
        update_download.download_update(result, canceled, staging=tmp_path)
    assert list(tmp_path.iterdir()) == []

    opener = Opener({result.checksum_url: HTTPError(result.checksum_url, 429, "rate limited", {}, None)})
    monkeypatch.setattr(update_download, "build_opener", lambda *_args: opener)
    with pytest.raises(HTTPError):
        update_download.download_update(result, threading.Event(), staging=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_cancel_during_asset_stream_removes_only_the_incomplete_operation(monkeypatch, tmp_path):
    asset = zip_payload()
    result, _name, manifest = release_result_for(asset)
    install_opener(monkeypatch, result, manifest, asset)
    canceled = threading.Event()

    def progress(_state, _done, _total):
        canceled.set()

    with pytest.raises(update_download.DownloadCancelled):
        update_download.download_update(result, canceled, staging=tmp_path, progress=progress)
    assert list(tmp_path.iterdir()) == []


def test_redirect_policy_allows_only_verified_github_asset_host():
    handler = update_download._ValidatedRedirects()
    request = Request("https://github.com/hectordoesgorug/BookLedger/releases/download/v1.1.0/file.zip")
    assert handler.redirect_request(
        request, None, 302, "Found", {},
        "https://release-assets.githubusercontent.com/file.zip?token=test",
    ) is not None
    for url in ("http://release-assets.githubusercontent.com/file.zip", "https://example.com/file.zip"):
        with pytest.raises(ValueError):
            handler.redirect_request(request, None, 302, "Found", {}, url)


def test_source_build_and_wrong_package_cannot_start_download(monkeypatch, tmp_path):
    asset = zip_payload()
    result, _, manifest = release_result_for(asset)
    monkeypatch.setattr(update_download, "desktop_package", lambda: None)
    with pytest.raises(ValueError, match="Packaged Windows"):
        update_download.download_update(result, threading.Event(), staging=tmp_path)
    monkeypatch.setattr(update_download, "desktop_package", lambda: "Fallback")
    with pytest.raises(ValueError, match="does not match"):
        update_download.download_update(result, threading.Event(), staging=tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("release_url", "https://example.com/releases/tag/v1.2.0"),
        ("asset_name", "BookLedger-v9.9.9-Windows-x64-Portable.zip"),
        ("checksum_size", True),
    ],
)
def test_untrusted_release_metadata_is_rejected_before_network(field, value, monkeypatch, tmp_path):
    asset = zip_payload()
    result, _, _ = release_result_for(asset)
    result = replace(result, **{field: value})
    monkeypatch.setattr(update_download, "desktop_package", lambda: "Portable")
    monkeypatch.setattr(update_download, "build_opener", lambda *_args: pytest.fail("network must not start"))
    with pytest.raises(ValueError):
        update_download.download_update(result, threading.Event(), staging=tmp_path)
    assert list(tmp_path.iterdir()) == []
