from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from bookledger import resources
from bookledger.resources import (
    apply_application_icon,
    normalize_shop_url,
    render_svg_icon,
    resource_path,
    resolve_managed_logo,
    store_shop_logo,
)


def test_bundled_resources_are_relative_to_the_module_not_the_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resource_path("assets", "icon.ico").is_file()
    for filename in (
        "icon-dashboard.svg", "icon-catalog.svg", "icon-inventory.svg", "icon-acquisitions.svg",
        "icon-sale history.svg", "icon-reports.svg", "icon-settings.svg", "icon-help.svg",
        "generalists_bookshop_logo.png",
    ):
        assert resource_path("assets", filename).is_file()


def test_installed_launcher_runtime_resolves_resources_from_an_unrelated_working_directory(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", "from bookledger.resources import resource_path; assert resource_path('assets', 'icon.ico').is_file()"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_bundled_resources_use_frozen_resource_root_when_available(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "icon.ico").touch()
    monkeypatch.setattr(resources.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resource_path("assets", "icon.ico") == tmp_path / "assets" / "icon.ico"


def test_supplied_navigation_svgs_render_to_consistent_enlarged_transparent_images():
    filenames = (
        "icon-dashboard.svg", "icon-catalog.svg", "icon-inventory.svg", "icon-acquisitions.svg",
        "icon-sale history.svg", "icon-reports.svg", "icon-settings.svg", "icon-help.svg",
    )
    for filename in filenames:
        image = render_svg_icon(resource_path("assets", filename), frame_size=36, content_size=32)
        assert image is not None
        assert image.mode == "RGBA"
        assert image.size == (36, 36)
        assert image.getbbox() is not None
        assert image.getpixel((0, 0))[3] == 0
    assert render_svg_icon(resource_path("assets", "missing.svg")) is None


def test_application_icon_uses_the_portable_bundled_icon_path():
    calls = []
    window = SimpleNamespace(iconbitmap=lambda *args, **kwargs: calls.append((args, kwargs)))
    assert apply_application_icon(window)
    icon_path = str(resource_path("assets", "icon.ico"))
    assert calls == [((icon_path,), {}), ((), {"default": icon_path})]


def test_managed_logo_paths_are_relative_and_cannot_escape_assets(tmp_path):
    data = tmp_path / "data"
    (data / "assets").mkdir(parents=True)
    assert resolve_managed_logo(data, "assets/shop-logo.png") == data / "assets" / "shop-logo.png"
    assert resolve_managed_logo(data, "../shop-logo.png") is None
    assert resolve_managed_logo(data, "assets/../../shop-logo.png") is None
    assert resolve_managed_logo(data, str(tmp_path / "logo.png")) is None
    assert resolve_managed_logo(data, "assets\\shop-logo.png") is None


def test_shop_logo_is_normalized_and_content_addressed_for_replacement(tmp_path):
    assets = tmp_path / "data" / "assets"
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.png"
    Image.new("RGB", (1600, 800), "navy").save(first)
    Image.new("RGBA", (640, 480), (200, 20, 30, 128)).save(second)

    saved_first = store_shop_logo(first, assets)
    saved_second = store_shop_logo(second, assets)
    with Image.open(saved_first) as rendered:
        assert rendered.format == "PNG"
        assert rendered.size == (1024, 512)
        assert rendered.mode == "RGB"
    with Image.open(saved_second) as rendered:
        assert rendered.mode == "RGBA"
        assert rendered.size == (640, 480)
    assert saved_first.parent == assets
    assert saved_second.parent == assets
    assert saved_first != saved_second
    assert saved_first.is_file()  # Replacing a selection leaves the previous portable file intact.


@pytest.mark.parametrize(("entered", "expected"), [
    ("shop.example/books", "https://shop.example/books"),
    ("HTTPS://shop.example/books", "https://shop.example/books"),
    ("", ""),
    ("javascript:alert(1)", None),
    ("file:///C:/Windows/system.ini", None),
    ("https://user:secret@shop.example", None),
    ("shop.example/with spaces", None),
])
def test_shop_url_is_normalized_only_to_http_or_https(entered, expected):
    assert normalize_shop_url(entered) == expected
