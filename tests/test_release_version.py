from importlib.metadata import version

from bookledger import __version__
from bookledger.config import APP_VERSION
from scripts.windows_version_info import build_version_info


def test_desktop_release_version_has_one_source():
    assert __version__ == "1.0.0"
    assert APP_VERSION == __version__
    assert version("bookledger") == __version__


def test_windows_file_version_uses_desktop_release_version():
    info = build_version_info(__version__)

    assert info.ffi.fileVersionMS == 1 << 16
    assert info.ffi.fileVersionLS == 0
    assert "FileVersion" in str(info)
    assert "1.0.0" in str(info)


def test_windows_file_version_rejects_non_three_part_versions():
    for invalid in ("1.0", "1.0.0.0", "one.two.three", "65536.0.0"):
        try:
            build_version_info(invalid)
        except ValueError:
            continue
        raise AssertionError(f"Accepted invalid version {invalid!r}.")
