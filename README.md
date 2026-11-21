# BookLedger

![BookLedger — Your collection, accounted for](assets/banner.png)

BookLedger is an offline-first book inventory manager for Windows 11 x64. Its Android companion scans ISBNs and captures cover photos, then transfers entries over your local network for cataloging on the desktop.

**Stable release: v1.1.0** · **Windows 11 x64 desktop** · **Android companion** · **MIT-licensed project code**

## Download BookLedger v1.1.0

| Download | Package | Notes |
| --- | --- | --- |
| [Windows portable ZIP](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.1.0/BookLedger-v1.1.0-Windows-x64-Portable.zip) | Preferred one-file package | Extract the ZIP and run `BookLedger/BookLedger.exe`. |
| [Windows fallback ZIP](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.1.0/BookLedger-v1.1.0-Windows-x64-Fallback.zip) | One-folder distribution | Run `Fallback/BookLedger.exe`; keep its `_internal/` folder and other package files beside it. |
| [Android companion APK](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.1.0/BookLedger-v1.1.0-Android.apk) | Production-signed, version `1.1.0+2` | Sideload on Android; it works with BookLedger Desktop and is not a standalone inventory manager. |
| [SHA-256 checksums](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.1.0/SHA256SUMS.txt) | Verify downloaded files | Compare each download with its entry in this file. |

See the [v1.1.0 release page](https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.1.0) for all assets and the [full release notes](docs/RELEASE_NOTES_v1.1.0.md).

## What BookLedger does

### Windows desktop

- Keep bibliographic records and track each physical copy, with cover photo, subtitle, condition, location, status, and price.
- Search, filter, and sort the catalog and inventory. Look up metadata online or enter it manually.
- Shorten long Book Details offline, compare the complete original and candidate, and choose which version to save.
- Record sales, retain sales history, void sales, and review inventory and sales reports.
- Create copy posters, manage a portable library, and back up or restore its data.
- Protect a library from simultaneous access by a second BookLedger process.

Core catalog and inventory work is available offline. Online metadata lookup needs an internet connection.

Library prices use one selected currency. You can change the currency label while keeping the stored numbers, or explicitly convert all asking prices, sale history, and saved SRPs using a dated Frankfurter reference rate. BookLedger requests an exchange rate only when you start a conversion; browsing and reporting stay offline.

### Android companion

- Scan an ISBN, enter one manually, or continue without an ISBN.
- Photograph book covers with a torch, supported zoom, and framing guides.
- Send a single capture or queue several in Bulk Entry.
- Pair by QR code or manual address, then reconnect and transfer over the local network.

The desktop remains the library manager: received entries are cataloged there.

## Quick start

1. Download and extract the [Windows portable package](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.1.0/BookLedger-v1.1.0-Windows-x64-Portable.zip), then run `BookLedger/BookLedger.exe`. For the fallback package, run `Fallback/BookLedger.exe` and keep its `_internal/` folder beside it.
2. If you want to capture books by phone, install the [production-signed Android APK](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.1.0/BookLedger-v1.1.0-Android.apk). Android may ask you to allow installation from the app used to open the APK.
3. On the desktop, open **Settings → Mobile App Setup** and pair the phone by QR code or manual entry.
4. Scan an ISBN, enter one manually, or choose No ISBN; take a cover photo and send the entry. Keep the app open until the desktop acknowledges transfer.
5. Complete the book and copy details in the desktop catalog.

The phone and computer must be able to communicate over a trusted local network. See the [Android companion guide](mobile/README.md) for pairing, capture, and recovery details.

## Your data, backups, and upgrades

The portable library is stored alongside the desktop application: `data/` holds the database and managed files, `config.json` holds settings, and `backups/` holds backup archives. Keep `data/` writable; if the application folder cannot store configuration, BookLedger may use a Windows user-profile fallback. Only one process can open a given library at a time; separate portable folders can run independently.

Before upgrading, make and verify a backup. After downloading a verified Windows ZIP, close BookLedger and extract it into a new, empty folder. For **Portable**, replace only `BookLedger.exe` from `BookLedger/`. For **Fallback**, replace `BookLedger.exe` and the complete `_internal/` folder together from `Fallback/`. Keep existing `data/`, `backups/`, `config.json`, photos, posters, and custom files. **Never copy the package's empty `data/` or `backups/` folder over existing data, and never extract a whole ZIP over a populated app folder.** Relaunch and confirm the library opens. The updater cannot recover a failed manual replacement. The v1.1.0 database migration adds a nullable subtitle column (schema v11 to v12); it is not backward-compatible with v1.0.0. Do not run v1.0.0 against a library already migrated by v1.1.0. Rolling back requires a suitable pre-upgrade backup and the older application.

Restoring a backup replaces the active library; it does not merge data. BookLedger validates a backup and saves a recovery backup before activation. Backups are not encrypted and may contain provider credentials, so store them securely. See the [v1.1.0 release notes](docs/RELEASE_NOTES_v1.1.0.md) for upgrade details.

Android upgrades require the same production signing certificate and a higher version code. A reported test installed the v1.1.0 APK over the production-signed v1.0.0 installation. Persistence of settings and pairing across that upgrade was not separately verified. Do not uninstall or clear app data to work around a signing conflict.

## Network and privacy

BookLedger does not sync your library to a BookLedger-operated cloud service. Core desktop inventory features work offline; metadata providers require internet access and receive the ISBN and any credentials needed for the lookup.

Desktop and phone communicate using authenticated, **unencrypted local HTTP**. Pair only on a trusted network. Windows Firewall may need to allow BookLedger on a trusted Private network. Android pending captures are session-only and may be lost if the app process ends before transfer is acknowledged. Backups are not encrypted. Barcode scanning runs on-device, though the bundled ML Kit SDK may communicate with Google as described in the [Privacy Notice](docs/PRIVACY_NOTICE.md).

## Checking for updates in current source builds

The desktop sidebar has an **Update** page directly below **About**. Android Settings has **Check for Updates** below **Clear Data**. Checks run only when selected, contact the official GitHub Releases API over HTTPS, and show stable-release versions and notes without changing library data, pairing or preferences. Source/debug builds can inspect releases but show **Unsupported Update** for packaged updates. The desktop version appears at the far right of its footer.

Click the application banner or activate it with Enter or Space to open the project repository in the default browser. The configurable shop logo below the navigation continues to open its separately configured shop URL.

The published v1.1.0 binaries do not include this updater. In eligible packaged builds with a newer stable release, **Download & Verify** saves the official Windows ZIP or Android APK to separate staging storage and checks its SHA-256 against that release's `SHA256SUMS.txt`. Windows ZIPs also receive path, layout, size and CRC validation. Downloads can be canceled; verified files remain staged until manually removed. Source and debug builds cannot download production updates. The checksum is not an independent publisher signature. Windows installation remains manual; Android offers **Install Update** after checking the APK package and higher version code, then requires Android's system installer approval. The app cannot recover a failed manual Windows replacement. Send pending phone captures and back up the desktop library before upgrading. See the [update system design](docs/UPDATE_SYSTEM.md) and [verification results](TEST_REPORT.md).

## Currency and SRP

Choose the library currency in **Settings → Preferences → Customize**. A fresh library uses PHP. Changing the currency without conversion keeps all numbers and changes how they are interpreted. Converting values uses a dated Frankfurter reference rate, creates a recovery backup, and converts asking prices, sale history, and informational SRPs together. Conversion requires an internet connection; displaying values and changing notation do not. All currencies display two decimal places.

SRP is informational and never changes the asking Price. Automated SRP lookup is not enabled because the investigated source data did not establish a reliable publisher list price for BookLedger's physical editions.

## Troubleshooting

- **Desktop cannot connect to the phone:** Confirm both devices can reach each other on the same trusted local network, keep BookLedger Desktop open, and allow it through Windows Firewall on a Private network if prompted.
- **QR pairing or discovery does not work:** Use the manual IPv4 address option in **Mobile App Setup**. Discovery can be unavailable on networks that filter multicast.
- **Android blocks APK installation:** Follow Android's prompt to allow installs from the app opening the APK. The app is distributed by sideloading, not Google Play.
- **A transfer is interrupted:** Keep BookLedger Mobile open until acknowledgment. Pending phone captures are session-only; if the process ends, the queue may be lost. Retry a transfer while the capture remains available.
- **You have an existing desktop library:** Preserve `data/`, `config.json`, and `backups/` while replacing program files. The app validates and migrates a legacy `BookLedger_Data/` installation at startup; if both old and current databases exist, startup stops rather than overwriting either. A backup restore replaces the active library, so choose the correct archive first.

## Documentation and licensing

- [Android companion guide](mobile/README.md)
- [Privacy Notice](docs/PRIVACY_NOTICE.md)
- [v1.1.0 release notes](docs/RELEASE_NOTES_v1.1.0.md)
- [v1.1.0 release checklist](docs/RELEASE_CHECKLIST_v1.1.0.md)
- [Architecture notes](docs/ARCHITECTURE.md)
- [MIT License](LICENSE) for original BookLedger code
- [Third-party notices](THIRD_PARTY_NOTICES.md) and bundled license files in `licenses/`

Third-party libraries, runtimes, and artwork retain their own license terms. The notices describe the documented components and packaging; they are not legal advice or a legal clearance of a particular use.

## Build from source

To run the Windows desktop from source, use CPython 3.10 or newer with Tk support and start [`run_bookledger.bat`](run_bookledger.bat); it creates or repairs the project virtual environment and installs the desktop dependencies. To build the portable Windows package, use 64-bit CPython 3.14.6 and the pinned requirements:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows-build.txt
.\scripts\build_windows_portable.ps1
```

The script prepares a Windows portable candidate. To bundle Android, provide the verified production-signed APK as described by the script and [Android guide](mobile/README.md). Keep signing properties and keystores outside the repository. See [third-party notices](THIRD_PARTY_NOTICES.md) before redistributing builds.
