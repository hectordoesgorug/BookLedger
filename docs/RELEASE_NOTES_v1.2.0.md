# BookLedger v1.2.0 — Release notes

**Published:** 2026-11-21 as the latest stable release. The annotated tag `v1.2.0` targets `3561873822e41c30aaa5445aa37fdaac7a4382c6` ([GitHub Release](https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.2.0)). Independently verified asset names, sizes, and SHA-256 values are recorded in the [release checklist](RELEASE_CHECKLIST_v1.2.0.md).

BookLedger v1.2.0 brings configurable currency conversion, offline description shortening, metadata-provider improvements, desktop refinements, and the first update-check and verified-download flows.

## Changes

Desktop adds configurable currency display and an explicit conversion workflow with a review step and backup safeguards. Conversion covers asking prices, retained sales history, and saved SRP values; BookLedger does not fetch publisher SRP automatically.

Book descriptions can be shortened deterministically and reviewed beside the original. The original remains available when a shortened version is selected. Hardcover is enabled by default ahead of Booktopia; BigBook remains implemented and can be enabled manually, but is off by default because its demonstrated incremental coverage is limited.

Desktop and Android can check stable GitHub Releases and present release information. Eligible packages can download and verify their exact release asset using the published SHA-256 manifest. Windows still requires manual file replacement after download. Android hands a verified APK to Android's installer and requires the device owner's approval.

## Compatibility and upgrade

Desktop uses database schema 14. Back up the library before upgrading. v1.1.0 cannot open a schema-14 library; rollback requires restoring a verified pre-upgrade backup. Restore replaces the active library and does not merge it.

The Android application ID remains `com.bookledger.mobile`; the released version is `1.2.0` with version code `3`. Upgrade compatibility depends on the same production signing identity. The published v1.1.0 app does not include update controls, so the first move to an updater-capable version must be installed manually.

## Known limits

- Windows update installation remains manual; BookLedger does not replace files or roll back automatically.
- Android pending capture queues are session-only and may be lost if the process stops. Send pending entries before an update.
- Checksums are downloaded from the same GitHub Release as the asset; they are not an independent publisher signature.
- No later stable release is available to exercise an update from v1.2.0.
- Automated SRP sourcing and new ISBNdb, Goodreads, and WorldCat adapters are outside this release.
- Physical upgrade, installer, and package acceptance results are recorded in the candidate report and must not be inferred from automated tests.

See the [release checklist](RELEASE_CHECKLIST_v1.2.0.md) and [candidate report](RELEASE_CANDIDATE_v1.2.0-rc1.md) for exact artifact identity, publication verification, and historical acceptance results.
