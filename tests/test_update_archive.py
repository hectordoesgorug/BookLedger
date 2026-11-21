import hashlib
from io import BytesIO
import stat
from zipfile import BadZipFile, ZipFile, ZipInfo

import pytest

from bookledger.services import update_archive


def inspect(names, package="Portable", checksum=True):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        for name in names:
            archive.writestr(name, b"fixture")
    content = stream.getvalue()
    for name in names:
        if isinstance(name, str) and "\\" in name:
            content = content.replace(name.replace("\\", "/").encode(), name.encode())
    sha = hashlib.sha256(content).hexdigest() if checksum else "0" * 64
    return update_archive.inspect_archive(content, f"{sha}  fixture.zip\n", "fixture.zip", package)


def test_inspection_checks_bytes_and_layout_without_creating_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert inspect(["BookLedger/BookLedger.exe", "BookLedger/data/", "BookLedger/backups/"]) == ("BookLedger.exe",)
    assert list(tmp_path.iterdir()) == []
    assert inspect(["Fallback/BookLedger.exe", "Fallback/_internal/runtime.dll"], "Fallback") == ("BookLedger.exe", "_internal/runtime.dll")


@pytest.mark.parametrize("unsafe", [
    "BookLedger/../config.json", "/BookLedger/payload", "C:/payload", "BookLedger\\payload",
    "BookLedger/data/library.sqlite3", "BookLedger/CONFIG.JSON", "BookLedger/backups/archive.zip",
    "BookLedger/aux.txt", "BookLedger/file.", "BookLedger/stream:secret", "BookLedger/a//b",
])
def test_unsafe_paths_and_protected_files_are_rejected(unsafe):
    with pytest.raises(ValueError):
        inspect(["BookLedger/BookLedger.exe", unsafe])


def test_wrong_checksum_duplicate_paths_and_missing_runtime_are_rejected():
    for names, package, checksum in [
        (["BookLedger/BookLedger.exe"], "Portable", False),
        (["BookLedger/BookLedger.exe", "BookLedger/bookledger.EXE"], "Portable", True),
        (["Fallback/BookLedger.exe"], "Fallback", True),
    ]:
        with pytest.raises(ValueError):
            inspect(names, package, checksum)


def test_symlinks_and_excessive_uncompressed_content_are_rejected(monkeypatch):
    link = ZipInfo("BookLedger/link")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(ValueError):
        inspect(["BookLedger/BookLedger.exe", link])
    monkeypatch.setattr(update_archive, "MAX_UNCOMPRESSED", 1)
    with pytest.raises(ValueError):
        inspect(["BookLedger/BookLedger.exe"])


def test_file_path_inspection_streams_crc_and_rejects_corrupt_entry(tmp_path):
    path = tmp_path / "fixture.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("BookLedger/BookLedger.exe", b"fixture executable")
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    checksums = f"{digest}  fixture.zip\n"
    assert update_archive.inspect_archive(path, checksums, "fixture.zip", "Portable") == ("BookLedger.exe",)

    damaged = content.replace(b"fixture executable", b"corrupt executable")
    path.write_bytes(damaged)
    checksum = hashlib.sha256(damaged).hexdigest()
    with pytest.raises(BadZipFile, match="CRC"):
        update_archive.inspect_archive(path, f"{checksum}  fixture.zip\n", "fixture.zip", "Portable")
