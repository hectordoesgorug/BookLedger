from __future__ import annotations

import argparse
from importlib.metadata import distribution, version
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
ZEROCONF_VERSION = "0.153.0"
LICENSED_DISTRIBUTIONS = (
    "Pillow",
    "ttkbootstrap",
    "qrcode",
    "ifaddr",
    "PyInstaller",
    "pyinstaller-hooks-contrib",
    "altgraph",
    "packaging",
    "pefile",
    "pywin32-ctypes",
)


def _copy_zeroconf_source(bundle: Path) -> None:
    if version("zeroconf") != ZEROCONF_VERSION:
        raise RuntimeError(f"Expected zeroconf {ZEROCONF_VERSION}; found {version('zeroconf')}.")
    import zeroconf

    source = Path(zeroconf.__file__).resolve().parent
    destination = bundle / "zeroconf"
    if destination.exists():
        shutil.rmtree(destination)
    for path in source.rglob("*"):
        if path.is_file() and (path.suffix == ".py" or path.name == "py.typed"):
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    copying = next(
        (path for path in distribution("zeroconf").files or () if path.name == "COPYING"),
        None,
    )
    if copying is None:
        raise RuntimeError("The zeroconf distribution does not include its LGPL COPYING file.")
    shutil.copy2(distribution("zeroconf").locate_file(copying), destination / "COPYING")


def _copy_licenses(bundle: Path) -> None:
    license_root = bundle / "licenses"
    for name in LICENSED_DISTRIBUTIONS:
        dist = distribution(name)
        candidates = [
            path
            for path in dist.files or ()
            if ".dist-info" in path.as_posix()
            and (path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE", "COPYRIGHT")))
            and path.suffix.lower() in {"", ".txt", ".md", ".rst"}
        ]
        if not candidates:
            raise RuntimeError(f"No license text was found for {name} {dist.version}.")
        package_dir = license_root / f"{dist.metadata['Name']}-{dist.version}"
        for relative in candidates:
            source = Path(dist.locate_file(relative))
            target = package_dir / relative.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    for name in ("LICENSE.txt", "LICENSE"):
        source = Path(sys.base_prefix) / name
        if source.is_file():
            target = license_root / "Python" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            break

    icon_license = Path(distribution("ttkbootstrap").locate_file("ttkbootstrap/assets/icons/LICENSE"))
    if not icon_license.is_file():
        raise RuntimeError("The ttkbootstrap icon asset license was not found.")
    target = license_root / "Bootstrap-Icons" / "LICENSE"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(icon_license, target)

    pillow_licenses = ROOT / "licenses" / "Pillow-Dependencies"
    shutil.copytree(pillow_licenses, license_root / "Pillow-Dependencies", dirs_exist_ok=True)
    android_licenses = ROOT / "licenses" / "Android"
    shutil.copytree(android_licenses, license_root / "Android", dirs_exist_ok=True)
    python_licenses = ROOT / "licenses" / "Python-THIRD-PARTY-LICENSES.rst"
    shutil.copy2(python_licenses, license_root / "Python" / python_licenses.name)


def prepare(bundle: Path, android_apk: Path | None = None) -> None:
    bundle = bundle.resolve()
    if not bundle.is_dir() or not (bundle / "BookLedger.exe").is_file():
        raise RuntimeError(f"Expected a completed package with BookLedger.exe at {bundle}.")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md"):
        shutil.copy2(ROOT / name, bundle / name)

    docs = bundle / "docs"
    docs.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "docs" / "PRIVACY_NOTICE.md", docs / "PRIVACY_NOTICE.md")

    mobile = bundle / "mobile"
    mobile.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "mobile" / "README.md", mobile / "README.md")
    if android_apk is not None:
        if not android_apk.is_file():
            raise RuntimeError(f"Android release APK not found: {android_apk}")
        shutil.copy2(android_apk, mobile / "BookLedger-Android.apk")
    (bundle / "data").mkdir(exist_ok=True)
    (bundle / "backups").mkdir(exist_ok=True)
    _copy_zeroconf_source(bundle)
    _copy_licenses(bundle)
    tcltk_license = ROOT / "licenses" / "tcltk-8.6-license.terms"
    target = bundle / "licenses" / "Tcl-Tk" / tcltk_license.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tcltk_license, target)
    tk_license = Path(sys.base_prefix) / "tcl" / "tk8.6" / "license.terms"
    if tk_license.is_file():
        target = bundle / "licenses" / "Tk" / "license.terms"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tk_license, target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--apk", type=Path)
    args = parser.parse_args()
    prepare(args.bundle, args.apk)
    print("Prepared portable files; Android APK included:" , bool(args.apk))
