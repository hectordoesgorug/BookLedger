# BookLedger

![BookLedger — Your collection, accounted for](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/assets/banner.png?raw=true)

BookLedger is an offline-first book inventory manager for Windows 11 x64, with an Android companion for ISBN scanning and cover capture. The desktop application manages the library; the phone sends captures to it over your local network.

## Download

The links below use the final v1.2.0 release filenames. They resolve after the GitHub Release is published; the [Releases page](https://github.com/hectordoesgorug/BookLedger/releases) lists currently available assets.

| Package | Download |
| --- | --- |
| Windows portable (preferred) | [BookLedger-v1.2.0-Windows-x64-Portable.zip](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.2.0/BookLedger-v1.2.0-Windows-x64-Portable.zip) |
| Windows fallback | [BookLedger-v1.2.0-Windows-x64-Fallback.zip](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.2.0/BookLedger-v1.2.0-Windows-x64-Fallback.zip) |
| Android companion APK | [BookLedger-v1.2.0-Android.apk](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.2.0/BookLedger-v1.2.0-Android.apk) — production-signed, version `1.2.0+3` |
| Checksums | [SHA256SUMS.txt](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.2.0/SHA256SUMS.txt) |

See the [v1.2.0 release page](https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.2.0) for release notes and all assets.

## Features

The Windows desktop app manages bibliographic records and individual physical copies, including photos, condition, location, price, and status. It supports online metadata lookup and manual entry, sales and sales history, reports, copy posters, and portable-library backups. Core inventory work remains available offline.

The Android companion scans or accepts an ISBN, supports no-ISBN capture, photographs covers, and sends one or several entries to BookLedger Desktop. It is not a standalone library manager. See the [Android guide](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/mobile/README.md) for capture and pairing details.

Each library uses one currency. Currency conversion is an explicit, backed-up operation using a dated Frankfurter reference rate; display and notation changes do not convert stored amounts. SRP is informational, and automated SRP lookup is disabled because reliable edition-specific publisher prices were not established.

## Quick start

1. Extract the Windows portable ZIP and run `BookLedger/BookLedger.exe`. With the fallback ZIP, run `Fallback/BookLedger.exe` and keep its `_internal/` folder beside it.
2. Optionally install the [Android APK](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.2.0/BookLedger-v1.2.0-Android.apk). Android may ask you to allow installs from the app used to open the file.
3. On the desktop, open **Settings → Mobile App Setup** and pair by QR code or manual address.
4. Capture a book and send it to the desktop. Keep the phone app open until the desktop acknowledges the transfer, then finish cataloging on the desktop.

If pairing or discovery fails, use the manual IPv4 option and check that both devices can communicate on the same trusted network. Windows Firewall may ask to allow BookLedger on a Private network.

## Data and backups

In portable installs, `data/` contains the database and managed files, `config.json` stores settings, and `backups/` holds archives. Keep these and any user-managed photos, posters, or custom files when updating. Make and verify a backup first.

The v1.1.0 release predates the updater. Updating Windows requires closing BookLedger, extracting the new ZIP into an empty folder, then replacing program files: replace only `BookLedger.exe` from `BookLedger/` for Portable; for Fallback replace `BookLedger.exe` and the complete `_internal/` folder together. Do not extract a whole ZIP over an existing app folder or copy its empty `data/` or `backups/` folders over yours. See the [v1.1.0 release notes](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/docs/RELEASE_NOTES_v1.1.0.md) before upgrading older libraries.

In v1.2.0, open the desktop **Update** page below **About** or choose **Settings → Check for Updates** on Android (below **Clear Data**). Source and debug builds can check releases, but only eligible packaged builds can download and verify an update. Windows installation remains a manual file replacement. Android offers **Install Update** after checking the APK, then asks Android's system installer to complete the user-approved update. Back up the desktop library and send pending phone captures before upgrading. The published v1.1.0 binaries do not include the update flow; details and limits are in the [update guide](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/docs/UPDATE_SYSTEM.md).

Restoring a backup **replaces** the active library; it does not merge records. Backups are unencrypted and may contain provider credentials, so store them securely.

## Privacy and network

BookLedger does not sync your library to a BookLedger-operated cloud service. Metadata lookup requires internet access and sends the ISBN and any credentials needed by the selected provider.

Desktop–phone transfers use authenticated but **unencrypted local HTTP**. Pair only on a trusted network. Android captures are session-only and may be lost if the app closes before the desktop acknowledges transfer. Barcode scanning is processed on-device by BookLedger; the bundled ML Kit SDK may communicate with Google as described in the [Privacy Notice](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/docs/PRIVACY_NOTICE.md).

## Documentation

- [Android companion guide](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/mobile/README.md)
- [Privacy Notice](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/docs/PRIVACY_NOTICE.md)
- [Update system](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/docs/UPDATE_SYSTEM.md)
- [Architecture notes](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/docs/ARCHITECTURE.md)
- [v1.2.0 release notes](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/docs/RELEASE_NOTES_v1.2.0.md)
- [v1.1.0 release notes](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/docs/RELEASE_NOTES_v1.1.0.md)
- [Test report](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/TEST_REPORT.md)

## Build from source

To run the desktop app, use CPython 3.10 or newer with Tk support and run [`run_bookledger.bat`](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/run_bookledger.bat). To build the Windows portable package, use 64-bit CPython 3.14.6 and the pinned requirements:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows-build.txt
.\scripts\build_windows_portable.ps1
```

For Android development and release signing requirements, see the [Android guide](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/mobile/README.md). Keep signing properties and keystores outside the repository.

## License

BookLedger's original code is licensed under the [MIT License](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/LICENSE). Third-party libraries, runtimes, and artwork have their own terms; see [third-party notices](https://github.com/hectordoesgorug/BookLedger/blob/v1.2.0/THIRD_PARTY_NOTICES.md) and the bundled files in `licenses/`.
