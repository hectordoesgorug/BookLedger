import json
import threading
import time
import tkinter as tk
import urllib.error

import pytest

from bookledger.services import updates
from bookledger.services.update_download import DownloadCancelled
from bookledger.ui.updates import UpdatePage


def release(tag="v1.2.0"):
    return {
        "draft": False, "prerelease": False, "tag_name": tag,
        "html_url": f"{updates.REPOSITORY_URL}/releases/tag/{tag}",
        "body": "Release notes\nKeep your library and backups.",
        "assets": [{
            "name": name, "browser_download_url": f"{updates.REPOSITORY_URL}/releases/download/{tag}/{name}",
            "state": "uploaded", "size": 123,
        } for name in (
            f"BookLedger-{tag}-Windows-x64-Portable.zip",
            f"BookLedger-{tag}-Windows-x64-Fallback.zip",
            f"BookLedger-{tag}-Android.apk", "SHA256SUMS.txt",
        )],
    }


@pytest.mark.parametrize("package,suffix", [("Portable", "Portable.zip"), ("Fallback", "Fallback.zip"), ("Android", "Android.apk")])
def test_official_platform_asset_and_notes_are_selected(package, suffix):
    result = updates.release_result(release(), "1.1.0", package)
    assert result.state == "Update Available"
    assert result.asset_url.endswith(suffix)
    assert result.checksum_url.endswith("SHA256SUMS.txt")
    assert result.installed == "1.1.0" and result.available == "1.2.0"
    assert "Release notes" in result.notes


@pytest.mark.parametrize("installed", ["1.2.0", "1.2.0+build.9", "1.10.0", "2.0.0"])
def test_same_or_older_release_is_not_an_update(installed):
    assert updates.release_result(release(), installed, "Portable").state == "Up to Date"


@pytest.mark.parametrize("field", ["draft", "prerelease"])
def test_unstable_releases_are_rejected(field):
    payload = release()
    payload[field] = True
    with pytest.raises(ValueError):
        updates.release_result(payload, "1.1.0", "Portable")


@pytest.mark.parametrize("tag", ["v1.2.0-rc.1", "latest", "1.2", "v01.2.0", "v1.2.0\n"])
def test_malformed_or_prerelease_tags_cannot_be_stable_updates(tag):
    with pytest.raises(ValueError):
        updates.release_result(release(tag), "1.1.0", "Portable")


def test_semantic_order_handles_prerelease_numbers_and_build_metadata():
    versions = ["1.1.0-alpha", "1.1.0-alpha.2", "1.1.0-alpha.10", "1.1.0-beta", "1.1.0-rc.1", "1.1.0", "1.2.0", "1.10.0"]
    assert sorted(versions, key=updates.version_key) == versions
    assert updates.version_key("v1.1.0+abc") == updates.version_key("1.1.0")
    with pytest.raises(ValueError):
        updates.version_key("1.1.0-rc.01")


@pytest.mark.parametrize("asset_index", [0, 3])
def test_missing_asset_or_checksum_prevents_update(asset_index):
    payload = release()
    payload["assets"].pop(asset_index)
    assert updates.release_result(payload, "1.1.0", "Portable").state == "Unsupported Update"


def test_untrusted_asset_url_is_not_offered():
    payload = release()
    payload["assets"][0]["browser_download_url"] = "https://example.com/payload.zip"
    assert updates.release_result(payload, "1.1.0", "Portable").state == "Unsupported Update"


def test_development_build_can_read_notes_but_cannot_update(monkeypatch):
    monkeypatch.setattr(updates.sys, "frozen", False, raising=False)
    assert updates.desktop_package() is None
    result = updates.release_result(release(), "1.1.0", None)
    assert result.state == "Unsupported Update"
    assert result.available == "1.2.0" and result.asset_url is None
    assert "newer stable version is available for manual review" in result.message
    same = updates.release_result(release("v1.1.0"), "1.1.0", None)
    assert same.state == "Unsupported Update" and same.asset_url is None
    assert "No newer stable version is available." in same.message


def test_frozen_package_detection_distinguishes_layouts(monkeypatch, tmp_path):
    monkeypatch.setattr(updates.sys, "platform", "win32")
    monkeypatch.setattr(updates.sys, "frozen", True, raising=False)
    monkeypatch.setattr(updates.sys, "executable", str(tmp_path / "BookLedger.exe"))
    monkeypatch.setattr(updates.sys, "_MEIPASS", str(tmp_path.parent / "_MEI123"), raising=False)
    monkeypatch.setattr(updates.platform, "machine", lambda: "AMD64")
    assert updates.desktop_package() == "Portable"
    (tmp_path / "_internal").mkdir()
    assert updates.desktop_package() == "Fallback"


class Response:
    def __init__(self, content): self.content = content
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def geturl(self): return updates.LATEST_RELEASE_URL
    def read(self, _size): return self.content


def test_check_is_read_only_and_independent_of_provider_configuration(monkeypatch, tmp_path):
    files = {name: tmp_path / name for name in ("config.json", "bookledger.sqlite3", "pending.jpg")}
    for path in files.values(): path.write_bytes(b"protected data")
    def request(req, timeout):
        assert req.full_url == updates.LATEST_RELEASE_URL and timeout == 5
        assert req.get_header("Authorization") is None
        return Response(json.dumps(release()).encode())
    monkeypatch.setattr("urllib.request.urlopen", request)
    assert updates.check_for_updates("1.1.0", "Portable").state == "Update Available"
    assert all(path.read_bytes() == b"protected data" for path in files.values())


@pytest.mark.parametrize("error", [TimeoutError(), urllib.error.URLError("offline"), urllib.error.HTTPError(updates.LATEST_RELEASE_URL, 403, "rate limit", {}, None), urllib.error.HTTPError(updates.LATEST_RELEASE_URL, 429, "rate limit", {}, None), urllib.error.HTTPError(updates.LATEST_RELEASE_URL, 500, "failure", {}, None)])
def test_check_classifies_network_and_http_failures(error, monkeypatch):
    def fail(*_args, **_kwargs): raise error
    monkeypatch.setattr("urllib.request.urlopen", fail)
    assert updates.check_for_updates("1.1.0", "Portable").state == "Unable to Check"


@pytest.mark.parametrize("content", [b"{bad json", b"[]", b"{}", b"\xff", b"x" * (2 * 1024 * 1024 + 1)])
def test_unexpected_responses_do_not_claim_up_to_date(content, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: Response(content))
    assert updates.check_for_updates("1.1.0", "Portable").state == "Unable to Check"


@pytest.fixture
def root():
    try:
        widget = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")
    widget.withdraw()
    yield widget
    widget.destroy()


def _wait_for_page_result(root, page):
    deadline = time.monotonic() + 2
    while page._busy and time.monotonic() < deadline:
        root.update()
        time.sleep(0.005)
    assert not page._busy


def test_update_page_displays_result_retries_and_opens_release(root, monkeypatch):
    results = iter((
        updates.UpdateResult("Update Available", "1.1.0", "1.2.0", message="New release", notes="Release notes", release_url="https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.2.0"),
        updates.UpdateResult("Unable to Check", "1.1.0", message="Offline"),
    ))
    calls = []
    monkeypatch.setattr("bookledger.ui.updates.webbrowser.open", lambda url, new=0: calls.append((url, new)) or True)
    page = UpdatePage(root, checker=lambda *_args: next(results), package="Portable")
    page.pack(fill="both", expand=True)
    assert page.state_text.get() == "Checking…"
    assert str(page.retry.cget("state")) == "disabled"
    _wait_for_page_result(root, page)
    assert page.state_text.get() == "Update Available"
    assert page.versions.get() == "Installed: 1.1.0    Available: 1.2.0"
    assert page.notes.get("1.0", "end-1c") == "Release notes"
    assert [button.cget("text") for button in page.winfo_children()[-1].winfo_children()] == [
        "Check Again", "Open Release Page", "Download & Verify", "Cancel Download", "Open Download Folder",
    ]
    page.release.invoke()
    assert calls == [("https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.2.0", 0)]
    page.retry.invoke()
    assert str(page.retry.cget("state")) == "disabled"
    _wait_for_page_result(root, page)
    assert page.state_text.get() == "Unable to Check"
    assert str(page.retry.cget("state")) == "normal"
    page.destroy()


def test_update_page_reports_verified_download_and_storage_location(root, tmp_path):
    name = "BookLedger-v1.2.0-Windows-x64-Portable.zip"
    result = updates.UpdateResult(
        "Update Available", "1.1.0", "1.2.0", message="New release",
        release_url="https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.2.0",
        asset_url=f"{updates.REPOSITORY_URL}/releases/download/v1.2.0/{name}",
        checksum_url="https://github.com/hectordoesgorug/BookLedger/releases/download/v1.2.0/SHA256SUMS.txt",
        asset_name=name, asset_size=100, checksum_size=317,
    )

    def downloader(_result, _cancel, *, staging, progress):
        progress("Downloading", 100, 100)
        progress("Verifying", 100, 100)
        folder = tmp_path / "v1.2.0-Portable-operation"
        folder.mkdir()
        path = folder / name
        path.write_bytes(b"verified fixture")
        return path

    page = UpdatePage(root, checker=lambda *_args: result, package="Portable", downloader=downloader)
    page.pack(fill="both", expand=True)
    _wait_for_page_result(root, page)
    assert str(page.download.cget("state")) == "normal"
    page.download.invoke()
    deadline = time.monotonic() + 2
    while page._download_cancel is not None and time.monotonic() < deadline:
        root.update()
        time.sleep(0.005)
    assert page._download_cancel is None
    assert page.state_text.get() == "Verified Download"
    assert name in page.download_status.get()
    assert str(tmp_path) in page.download_status.get()
    assert "Installation is not available yet." in page.download_status.get()
    assert str(page.open_download_folder.cget("state")) == "normal"
    page.destroy()


def test_leaving_page_cancels_download_and_removes_its_poll(root):
    name = "BookLedger-v1.2.0-Windows-x64-Portable.zip"
    result = updates.UpdateResult(
        "Update Available", "1.1.0", "1.2.0", message="New release",
        release_url="https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.2.0",
        asset_url=f"{updates.REPOSITORY_URL}/releases/download/v1.2.0/{name}",
        checksum_url="https://github.com/hectordoesgorug/BookLedger/releases/download/v1.2.0/SHA256SUMS.txt",
        asset_name=name, asset_size=100, checksum_size=317,
    )
    started = threading.Event()
    observed_cancel = threading.Event()

    def downloader(_result, cancel, **_kwargs):
        started.set()
        cancel.wait(2)
        observed_cancel.set()
        raise DownloadCancelled()

    page = UpdatePage(root, checker=lambda *_args: result, package="Portable", downloader=downloader)
    page.pack(fill="both", expand=True)
    _wait_for_page_result(root, page)
    page.download.invoke()
    assert started.wait(1)
    page.destroy()
    assert observed_cancel.wait(1)


def test_release_notes_use_the_active_theme_colors(root, monkeypatch):
    class ThemeStyle:
        def lookup(self, widget_style, _option):
            return {"TFrame": "#222222", "TLabel": "#eeeeee"}[widget_style]

    monkeypatch.setattr("bookledger.ui.updates.ttk.Style", lambda _widget: ThemeStyle())
    page = UpdatePage(root, checker=lambda *_args: updates.UpdateResult("Up to Date", "1.1.0"), package="Portable")

    assert page.notes.cget("background") == "#222222"
    assert page.notes.cget("foreground") == "#eeeeee"
    assert page.notes.cget("insertbackground") == "#eeeeee"
    page.destroy()


def test_leaving_update_page_cancels_poll_and_returning_starts_a_fresh_check(root):
    pending = threading.Event()
    checks = []
    def check(installed, _package):
        checks.append(True)
        pending.wait(2)
        return updates.UpdateResult("Unable to Check", installed, message="Offline")
    page = UpdatePage(root, checker=check, package="Portable")
    page.pack(fill="both", expand=True)
    assert page.state_text.get() == "Checking…"
    assert str(page.retry.cget("state")) == "disabled"
    page.destroy()
    root.update()
    pending.set()
    returned = UpdatePage(root, checker=check, package="Portable")
    returned.pack(fill="both", expand=True)
    _wait_for_page_result(root, returned)
    assert len(checks) == 2
    assert returned.state_text.get() == "Unable to Check"
    returned.destroy()
    root.update()
