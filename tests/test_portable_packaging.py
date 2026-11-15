from pathlib import Path

import pytest

from scripts import prepare_portable_distribution


def test_prepare_stages_onefile_executable_without_changing_it(tmp_path, monkeypatch):
    bundle = tmp_path / "BookLedger"
    bundle.mkdir()
    executable = bundle / "BookLedger.exe"
    executable.write_bytes(b"one-file executable")
    apk = tmp_path / "BookLedger-Android.apk"
    apk.write_bytes(b"signed apk")
    monkeypatch.setattr(prepare_portable_distribution, "_copy_zeroconf_source", lambda _bundle: None)
    monkeypatch.setattr(prepare_portable_distribution, "_copy_licenses", lambda _bundle: None)

    prepare_portable_distribution.prepare(bundle, apk)

    assert executable.read_bytes() == b"one-file executable"
    assert (bundle / "data").is_dir()
    assert (bundle / "backups").is_dir()
    assert (bundle / "mobile" / "BookLedger-Android.apk").read_bytes() == b"signed apk"
    assert (bundle / "README.md").is_file()
    assert not (bundle / "_internal").exists()


def test_prepare_rejects_bundle_without_bookledger_executable(tmp_path):
    with pytest.raises(RuntimeError, match="Expected a completed package"):
        prepare_portable_distribution.prepare(tmp_path / "empty")
