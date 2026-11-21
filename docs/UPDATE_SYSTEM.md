# Update checks and installation

## Release checks and downloads

Desktop and Android check GitHub's designated latest stable release only after the user selects **Check Again** or **Check for Updates**. Checks do not run at startup, send library data or provider credentials, or change preferences. Both clients validate the release identity and compare semantic versions; network failures never report that the app is up to date.

Eligible packaged builds offer **Download & Verify** only when a newer release has the expected platform asset and `SHA256SUMS.txt`. Downloads use separate staging storage, enforce size and HTTPS redirect limits, show progress, support cancellation, and retain a file only after its size and SHA-256 match the release metadata and checksum manifest. Desktop ZIPs also receive path, layout, size, CRC, and protected-data checks. Android checks that the file is a ZIP-based APK. A release checksum detects transfer corruption or an asset mismatch; it is not an independent publisher signature and does not protect against compromise of the GitHub account.

The published v1.1.0 binaries do not include update discovery or download support. Source/development desktop builds and Android debug builds can inspect release information but cannot download production assets. Only eligible frozen Windows x64 builds and production-signed Android builds can use the download controls.

## Windows: manual update

The updater never extracts, replaces, or launches application files. After a verified ZIP downloads:

1. Make and verify a library backup, then close BookLedger completely.
2. Extract the ZIP into a new, empty folder. Do not extract it over the existing application folder.
3. For **Portable**, copy `BookLedger/BookLedger.exe` to the existing application folder and replace that executable.
4. For **Fallback**, copy `Fallback/BookLedger.exe` and the complete `Fallback/_internal/` folder together to the existing application folder. Replace both from the same release; do not mix runtime files from different versions.
5. Keep the existing `data/`, `backups/`, `config.json`, photos, posters, and custom files. Never copy a package's empty `data/` or `backups/` directory over existing folders.
6. Relaunch BookLedger and confirm the library opens normally.

Keep the verified ZIP and the pre-update backup until the new version is confirmed. This is a manual file replacement; BookLedger cannot journal or automatically recover from a failed replacement. Do not start an older version against a database it cannot read. Restoring a backup replaces the active library and must be a deliberate choice.

## Android: system-approved update

After **Download & Verify** succeeds, Android inspects the APK from app-private update storage. The **Install Update** action appears only if the APK still matches the verified SHA-256, its package ID is `com.bookledger.mobile`, and its version code is higher than the installed app. The app does not accept a caller-supplied file path. Android's system package installer performs the final signature and compatibility checks and asks the device owner to approve installation.

On Android 8.0 and later, Android may require allowing BookLedger to install APKs from this source. The app opens the system's per-source settings only after the user confirms installation; after granting access, return to BookLedger and tap **Install Update** again. The APK is shared using a temporary read-only content URI. If the installer is unavailable, permission is denied, the user cancels, or Android rejects the APK, the current app remains installed. The app reports success only when the installer returns and PackageManager confirms the requested version code. It never silently installs, uninstalls the existing app, or clears app data.

Before continuing, BookLedger warns:

> Any unsent captures may be lost if the update closes BookLedger. Send pending entries to the desktop before proceeding.

Pairing, preferences, secure storage, and app-private files are left to Android's normal in-place package upgrade. The app does not delete pending captures; however, capture queue metadata is session-only and may be lost if Android closes the process. Transfer pending entries first.

## Compatibility and limits

- The APK must target the existing `com.bookledger.mobile` installation and use a strictly higher Android version code. A different signing certificate or incompatible package is rejected by Android; do not uninstall or clear data to bypass the check.
- A first update from the published v1.1.0 binaries requires manually downloading and installing a later updater-capable release. Existing binaries cannot use this update flow.
- The latest stable release observed during the November 21, 2026 verification was v1.1.0, so a newer-release download and native installation have not been exercised. Installer-interface tests and a debug build do not prove a production-signed device upgrade.
- Android pending captures are not durable across process termination. Backups are unencrypted and may contain provider credentials; store them securely.

See the [desktop guide](../README.md#your-data-backups-and-upgrades), [Android guide](../mobile/README.md#checking-for-updates-in-current-source-builds), and [verification report](../TEST_REPORT.md) for operating steps and current evidence.
