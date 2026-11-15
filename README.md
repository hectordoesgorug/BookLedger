# BookLedger

BookLedger is an offline-first Windows desktop app for managing a personal or small-scale book inventory. Catalog books and individual physical copies, add photos and bibliographic details, and organize copies by condition, location, status, and price. ISBN-based metadata lookup is available when online.

## Build the portable Windows app

Build on Windows x64 with CPython 3.14.6 and the pinned packages in `requirements-windows-build.txt`. From the repository root, run:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows-build.txt
.\scripts\build_windows_portable.ps1
```

The script builds the preferred PyInstaller one-file application and creates `dist/BookLedger-portable-onefile-candidate.zip`. The ZIP extracts to a `BookLedger/` folder containing `BookLedger.exe`, the replaceable LGPL-licensed Zeroconf Python source in `zeroconf/`, the optional Android APK in `mobile/`, user data folders, and licensing materials. Python, Tcl/Tk, application dependencies, and application assets are bundled into the executable. At launch, PyInstaller temporarily extracts runtime files under a `_MEI...` directory and removes them when the app exits; BookLedger keeps configuration, database, photos, and backups beside the executable. To replace or modify Zeroconf, replace the `zeroconf/` directory with a compatible source version, retain its `COPYING` file, and mark your changes. The executable and its license materials remain separate so the LGPL component can be replaced. `BookLedger.spec` retains the previous one-folder configuration as a fallback.

To build the combined Windows and Android release candidate, place the verified production-signed APK at `release-input/BookLedger-Android.apk` and run the build script. It verifies the APK signature with Android SDK `apksigner`, using `JAVA_HOME` or Android Studio's bundled JBR for that process, rejects the standard Android debug certificate, and does not sign or alter the APK. When provided, the ZIP contains it at `BookLedger/mobile/BookLedger-Android.apk`; without the staged APK, the script builds a Windows-only candidate. Do not put signing keys or credentials in the staging folder.

To install the companion app, copy `BookLedger/mobile/BookLedger-Android.apk` to an Android device and open it with the Files app or another package installer. Android may require enabling installs from that specific source; follow the system prompt. See [Android's sideloading guidance](https://developer.android.com/distribute/marketing-tools/alternative-distribution). The APK is `com.bookledger.mobile`, version `1.0.0` (version code `1`). It is distributed as a sideloaded APK, not through Google Play.

In BookLedger Desktop, open **Settings → Mobile App Setup → Export APK**, choose a save location, and transfer the exported APK to the device. Canceling the save dialog exports nothing. Export copies the bundled file without changing or re-signing it. This option is available only in a package that contains `mobile/BookLedger-Android.apk`.

The companion app asks for Camera access when scanning ISBNs or taking cover photos. It also declares Internet and network-state access for local desktop pairing. It does not request microphone or broad shared-storage permissions. Pairing uses unencrypted HTTP on the local network; use a trusted network. Barcode input and results are processed on-device by the bundled ML Kit model, while the SDK may contact Google for model/fix/hardware compatibility updates and usage/performance metrics. See [mobile/README.md](mobile/README.md) and the accompanying third-party notices for details.

## Run and move BookLedger

Extract the ZIP so it creates one `BookLedger` folder, then run `BookLedger/BookLedger.exe`. The app creates its writable files alongside the executable:

- `data/` contains the database, photos, Trash, managed assets, posters, and logs; it starts empty.
- `config.json` contains preferences, provider order, and API credentials.
- `backups/` contains portable backups.

Keep the folder in a location where the current Windows account can write. If the folder is read-only, BookLedger's established configuration fallback may store configuration under the Windows user profile; other managed data still needs a writable `data/` directory. On first launch, BookLedger initializes `config.json` with its default settings, including Clam when the bundled Tk runtime provides it. A valid existing configuration is retained and only missing settings are added. To move the installation, close BookLedger and move or copy the entire folder, including `data/`, `config.json`, and `backups/`. Do not move only the executable.

To update the application files, make a backup, close BookLedger, then replace `BookLedger.exe`, `zeroconf/`, `mobile/`, `licenses/`, and the bundled documentation from the new package. Keep `data/`, `config.json`, and `backups/` in place. The application initializes a missing `config.json` with its defaults and fills only missing settings in an existing configuration.

The portable data layout is `<application folder>/data/`. Existing `BookLedger_Data/` installations use the app's validated, non-destructive migration and retain the source tree until verification succeeds. If both legacy and current databases exist, BookLedger stops and asks that the conflict be resolved; it does not overwrite either database.

## Run from source

Install Python 3.10 or newer with Tk support, then run [`run_bookledger.bat`](run_bookledger.bat) from the project folder. The launcher creates a development environment, installs runtime dependencies when needed, and starts BookLedger.

## Licensing and distribution status

Original BookLedger desktop and mobile source code is licensed under the [MIT License](LICENSE). Third-party components retain their own terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the `licenses/` directory in the package. Backups include the database, managed photos, and `config.json`; they are not encrypted and may contain API credentials, so store them securely. A portable candidate is not a legal clearance or independent clean-machine certification; review notices and verify the exact package before public redistribution.
