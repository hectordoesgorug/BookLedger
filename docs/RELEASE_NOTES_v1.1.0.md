# BookLedger v1.1.0 — Draft release notes (unpublished)

Internal review candidate: **v1.1.0-rc1**. These notes are prepared for a future GitHub Release; no tag, release, or public asset has been created by this preparation.

## Changes

Desktop now protects each portable library against concurrent access, offers catalog sort direction, improves catalog card sizing and mobile connection status, and reduces image-processing work. Optional subtitles are stored independently, searched, and shown in Inventory and Details; Catalog combines short title/subtitle pairs while posters continue to use the main title.

Android consolidates Settings and removes the obsolete diagnostic button. Cover photography gains torch, hardware-limited zoom, and remembered framing guides. Single/Bulk Entry now makes photos ready without Save, preserves them during identifier correction and canceled Retake, and automatically starts the next scan after Queue. Partial batches can be finished by closing the next scanner and holding Queue. Reconnection regression coverage was expanded. Completed Android scope is #6, #5, #8, #19, and #16; deferred backlog features are not included.

## Internal review artifacts

- `BookLedger-v1.1.0-rc1-Windows-x64-Portable.zip` — preferred one-file Windows 11 x64 package.
- `BookLedger-v1.1.0-rc1-Windows-x64-Fallback.zip` — one-folder fallback; retain its `_internal/` folder.
- `BookLedger-v1.1.0-rc1-Android.apk` — production-signed `com.bookledger.mobile`, version `1.1.0`, code `2`.
- `SHA256SUMS-rc1.txt` — hashes of the three candidate binaries.

These are candidate filenames, not public release assets. Extract the entire Windows ZIP and run `BookLedger/BookLedger.exe`. Both Windows packages include the exact standalone APK at `BookLedger/mobile/BookLedger-Android.apk`. For direct APK distribution, retain the accompanying mobile README, project license, third-party notices, privacy notice, and Android license files.

## Upgrade and data

Close the desktop and create a verified backup before upgrading. Preserve `data/`, `config.json`, and `backups/`; never replace a populated data directory with the package's empty directory. Schema v11 migrates to v12 with a nullable subtitle column; existing titles and identities are retained. Restore replaces the active library and does not merge it. Do not open a migrated library in v1.0.0; rollback requires the pre-upgrade backup and old application.

Android upgrades require the same production certificate and higher version code. Owner acceptance must begin with production-signed v1.0.0 and install this exact candidate in place, preserving data. A debug-signed installation cannot prove that upgrade path. Do not uninstall or clear data to bypass a signature conflict.

## Known limits and acceptance

Mobile captures are session-only and may be lost on process termination; durable capture recovery is outside this release scope. Keep the app open until acknowledgment. Transfers use authenticated, unencrypted local HTTP; use a trusted network. Barcode processing is on-device, with possible ML Kit SDK communications described in the [privacy notice](PRIVACY_NOTICE.md).

An earlier Android startup ANR was not reproduced in the November 17 debug audit; its cause remains unknown. Signed-candidate device startup, real scanning, connected Single/Bulk transfer and interrupted retries, in-place upgrade, and Windows physical acceptance remain pending. Historical owner-reported passes and debug audit results are not candidate-specific acceptance. Automated verification and exact artifacts are recorded in the [candidate checklist](RELEASE_CHECKLIST_v1.1.0.md) and [candidate report](RELEASE_CANDIDATE_v1.1.0-rc1.md).

This preparation does not assert legal clearance or universal device compatibility. Publication requires separate owner review and authorization.
