# BookLedger

BookLedger is an offline-first Windows desktop app for managing a personal or small-scale book inventory. Catalog books and individual physical copies, add photos and bibliographic details, and organize copies by condition, location, status, and price. ISBN-based metadata lookup is available when online.

## Build the portable Windows folder

Build on Windows x64 with CPython 3.14.6 and the pinned packages in `requirements-windows-build.txt`. From the repository root, run:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows-build.txt
.\scripts\build_windows_portable.ps1
```

The script builds a PyInstaller one-folder application and creates `dist/BookLedger-portable-candidate.zip`. Python, Tcl/Tk, application dependencies, and internal resources are bundled. The LGPL-licensed Zeroconf Python source and its `COPYING` file are placed in the `zeroconf/` directory beside the executable and loaded from there at runtime. To replace or modify Zeroconf, replace that directory with a compatible source version, retain `COPYING`, and mark your changes. The ZIP includes the MIT License, this guide, third-party notices, package license texts, and `mobile/README.md`.

The current candidate does not include an Android APK. To include a future signed release APK, place it at `release-input/BookLedger-Android.apk` and rebuild. The script verifies the signature with Android SDK `apksigner` and rejects APKs signed with the standard Android debug certificate; it does not sign APKs. The resulting package places it at `mobile/BookLedger-Android.apk`. The app's **Export APK** button looks for that file beside `BookLedger.exe`, then copies it to a location chosen with Save As. It does not download or alter the source APK. Until a signed release APK is supplied and the candidate rebuilt, Export APK reports that the file is unavailable.

## Run and move BookLedger

Extract the ZIP so it creates one `BookLedger` folder, then run `BookLedger/BookLedger.exe`. The app creates its writable files alongside the executable:

- `data/` contains the database, photos, Trash, managed assets, posters, and logs; it starts empty.
- `config.json` contains preferences, provider order, and API credentials.
- `backups/` contains portable backups.

Keep the folder in a location where the current Windows account can write. If the folder is read-only, BookLedger's established configuration fallback may store configuration under the Windows user profile; other managed data still needs a writable `data/` directory. On first launch, BookLedger initializes `config.json` with its default settings. A valid existing configuration is retained and only missing settings are added. To move the installation, close BookLedger and move or copy the entire folder, including `data/`, `config.json`, and `backups/`. Do not move only the executable.

To update the application files, make a backup, close BookLedger, then replace `BookLedger.exe`, `_internal/`, `zeroconf/`, and the bundled documentation from the new package. Keep `data/`, `config.json`, and `backups/` in place. The application initializes a missing `config.json` with its defaults and fills only missing settings in an existing configuration.

The portable data layout is `<application folder>/data/`. Existing `BookLedger_Data/` installations use the app's validated, non-destructive migration and retain the source tree until verification succeeds. If both legacy and current databases exist, BookLedger stops and asks that the conflict be resolved; it does not overwrite either database.

## Run from source

Install Python 3.10 or newer with Tk support, then run [`run_bookledger.bat`](run_bookledger.bat) from the project folder. The launcher creates a development environment, installs runtime dependencies when needed, and starts BookLedger.

## Licensing and distribution status

Original BookLedger desktop and mobile source code is licensed under the [MIT License](LICENSE). Third-party components retain their own terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the `licenses/` directory in a built package. The Windows ZIP is a candidate and has not been tested on an independent clean Windows installation. Review third-party notices and verify the exact package before public redistribution.
