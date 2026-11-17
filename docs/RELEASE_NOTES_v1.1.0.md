# BookLedger v1.1.0 — Release notes

BookLedger v1.1.0 promotes the maintainer-accepted v1.1.0-rc1 binaries unchanged.

## Changes

Desktop now protects each portable library against concurrent access, offers catalog sort direction, improves catalog card sizing and mobile connection status, and reduces image-processing work. Optional subtitles are stored independently, searched, and shown in Inventory and Details; Catalog combines short title/subtitle pairs while posters continue to use the main title.

Android consolidates Settings and removes the obsolete diagnostic button. Cover photography gains torch, hardware-limited zoom, and remembered framing guides. Single/Bulk Entry now makes photos ready without Save, preserves them during identifier correction and canceled Retake, and automatically starts the next scan after Queue. Partial batches can be finished by closing the next scanner and holding Queue. Reconnection regression coverage was expanded. Completed Android scope is #6, #5, #8, #19, and #16; deferred backlog features are not included.

## Downloads

- `BookLedger-v1.1.0-Windows-x64-Portable.zip` — preferred one-file Windows 11 x64 package.
- `BookLedger-v1.1.0-Windows-x64-Fallback.zip` — one-folder fallback; retain its `_internal/` folder.
- `BookLedger-v1.1.0-Android.apk` — production-signed `com.bookledger.mobile`, version `1.1.0`, code `2`.
- `SHA256SUMS.txt` — hashes of the three candidate binaries.

Final assets are byte-identical copies of accepted rc1. Extract the entire ZIP. Run `BookLedger/BookLedger.exe` for Portable, or `Fallback/BookLedger.exe` for Fallback; retain all sibling folders including fallback `_internal/`. Each package includes the exact standalone APK under its root at `mobile/BookLedger-Android.apk`. For direct APK distribution, retain the accompanying mobile README, project license, third-party notices, privacy notice, and Android license files.

## Upgrade and data

Close the desktop and create a verified backup before upgrading. Preserve `data/`, `config.json`, and `backups/`; never replace a populated data directory with the package's empty directory. Schema v11 migrates to v12 with a nullable subtitle column; existing titles and identities are retained. Restore replaces the active library and does not merge it. Do not open a migrated library in v1.0.0; rollback requires the pre-upgrade backup and old application.

Android upgrades require the same production certificate and higher version code. The maintainer reports installing historical production v1.0.0 first, then the exact rc1 APK over it; Android showed an update confirmation and installation succeeded. Post-upgrade settings and pairing persistence were not separately verified. A debug-signed installation cannot prove that upgrade path. Do not uninstall or clear data to bypass a signature conflict.

## Known limits and acceptance

Mobile captures are session-only and may be lost on process termination; durable capture recovery is outside this release scope. Keep the app open until acknowledgment. Transfers use authenticated, unencrypted local HTTP; use a trusted network. Barcode processing is on-device, with possible ML Kit SDK communications described in the [privacy notice](https://github.com/hectordoesgorug/BookLedger/blob/v1.1.0/docs/PRIVACY_NOTICE.md).

The earlier ANR report concerned a Poco X6 experiencing lag while rapid charging and connected to a PC through TwinDesk. No ANR was reproduced during the subsequent audit, and no root cause has been established. These circumstances are context, not a confirmed explanation or an active verified defect. The maintainer reports PASS for Windows execution/layout, backup/restore, Sales/reports/status changes, poster creation, pairing/reconnection, Android camera controls and Single/Bulk workflows including edge cases and partial/full queues. These checks were maintainer-reported. The desktop suite remains 517 passed, 17 skipped, 1 failed; its display-sensitive minimum-size assertion is accepted as a non-blocking exception based on successful maintainer layout testing. Automated verification and exact artifacts are recorded in the [candidate checklist](https://github.com/hectordoesgorug/BookLedger/blob/v1.1.0/docs/RELEASE_CHECKLIST_v1.1.0.md) and [candidate report](https://github.com/hectordoesgorug/BookLedger/blob/v1.1.0/docs/RELEASE_CANDIDATE_v1.1.0-rc1.md).

Maintainer acceptance and publication were authorized. This release does not assert legal clearance or universal device compatibility.
