# BookLedger v1.2.0 Release Readiness Audit

**Audit date:** November 21, 2026

**Recommendation:** **Ready for Release Candidate Preparation**

**Release approval:** Not assessed; candidate verification remains required.

## Executive summary

The current source has a coherent, bounded v1.2.0 scope: configurable currency and conversion, offline book-description shortening, repaired existing metadata providers, desktop refinements, and explicit release checking, verified downloads, manual Windows updating, and Android's user-approved package-installer handoff. The Windows updater does not replace application files automatically. The update controls and installation flows are not in the published v1.1.0 binaries.

This read-only review found **no confirmed source defect that blocks starting candidate preparation**. It did not build or install a candidate, rerun tests, verify the production signing key, or establish native acceptance. Those checks remain prerequisites for candidate approval. The existing desktop and Android reports are historical evidence, not results of this audit.

The release boundary should stay narrow. Keep automatic Windows replacement, additional metadata providers, automated SRP retrieval, general-purpose layout work, and broader Catalog virtualization outside v1.2.0. Keep Android capture loss on process termination clearly disclosed.

## 1. Git and release baseline

- The working tree was clean on `main` at `79d6f8afdc419800a6aa57318aa6ea2e6117521e`, matching `origin/main`.
- The published annotated `v1.1.0` tag peels to `01dc3990e9fa321e5cf2f815ce509d5a3736e9ac`. Current `main` contains 19 commits after that tag, touching 67 files (6,015 insertions and 333 deletions).
- The GitHub Releases API reported **v1.1.0** as the latest release on November 21, 2026; it is neither draft nor prerelease. The release page lists the Portable ZIP, Fallback ZIP, production-signed Android APK, and `SHA256SUMS.txt` ([v1.1.0 release](https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.1.0)).
- The published APK is `com.bookledger.mobile`, version `1.1.0`, Android version code `2`. The v1.1.0 binaries predate all current update features. Source and debug builds can inspect releases but cannot use the production download controls.

The changes since v1.1.0 include currency selection/conversion; deterministic synopsis shortening and review; Hardcover/BigBook compatibility and default-provider changes; desktop layout and navigation updates; update discovery, download verification and installation guidance; Android installer handoff; schema migrations; tests; and updated documentation/dependency metadata. These are committed source changes, not functionality already present in the published release.

## 2. Proposed v1.2.0 scope

| Area | Status | Evidence and boundary |
| --- | --- | --- |
| Update discovery on Windows and Android | **Requires Verification** | Explicit checks and release-note presentation are implemented. The newest public release is still v1.1.0, so a newer-release result cannot yet be exercised against a real eligible release. |
| Verified release downloads | **Requires Verification** | Source validates release identity, expected asset, size and SHA-256; Windows ZIPs also receive archive/layout checks. Tests use synthetic releases. The checksum comes from the same release source and is not an independent publisher signature. |
| Windows update installation | **Ready** | The approved flow remains a verified download followed by package-specific manual file replacement. There is no automatic replacement, rollback journal or recovery helper. Preserve and back up user data. |
| Android installer handoff | **Requires Verification** | Source validates the staged APK, package name and higher version code, then asks Android's installer to obtain user approval. No native production-signed update from v1.1.0 has been demonstrated. |
| Currency and conversion | **Requires Verification** | Twenty currencies, notation-only changes and explicit backed-up conversions are implemented. Conversion includes asking prices, retained sales (including voided history) and SRP values; automated SRP sourcing remains out of scope. |
| Offline description shortening | **Ready** | Deterministic sentence selection and the compare/review workflow are implemented with focused regression coverage. Verify the reviewed behavior on both supported desktop packages. |
| Hardcover and BigBook repairs | **Ready** | Existing adapters are repaired. Fresh defaults place and enable Hardcover before Booktopia; BigBook remains implemented, disabled by default and available for manual activation. Saved preferences are preserved. BigBook's demonstrated incremental coverage is limited. |
| Desktop layout refinements | **Requires Verification** | The intake geometry regression now synchronizes the parent and transient window; the test retains exact `960×700` and functional layout assertions. Issue #1's broader multi-screen responsive scope remains open. |
| Database, backup and restore | **Requires Verification** | Current schema is 14; migrations and disposable-database tests cover v1.1.0 schema 12 through 13 to 14. A migrated library cannot be rolled back by running v1.1.0; use a pre-upgrade backup. |
| Additional ISBNdb, Goodreads or WorldCat integration | **Deferred** | No adapters or controls were added. The feasibility review recommends deferring ISBNdb pending written retention rights, rejecting Goodreads under current access conditions, and rejecting a general independent-user WorldCat integration. |
| Automatic SRP lookup, general desktop reflow and catalog virtualization | **Deferred** | No reliable physical-edition SRP source is established. Broader responsive design and larger Catalog-loading work remain separate issues without a confirmed release-critical defect. |

## 3. Open issue disposition

All five reviewed issues remain open. No issue was edited or closed for this audit.

| Issue | Current relationship to v1.2.0 | Recommended disposition |
| --- | --- | --- |
| [#22 — Update system](https://github.com/hectordoesgorug/BookLedger/issues/22) | The issue still describes a preferred true in-app Windows updater, a helper, replacement, rollback and recovery. Current source and [update documentation](UPDATE_SYSTEM.md) implement the approved simpler flow: verified download, manual Windows replacement, and Android's system installer. | Reconcile the issue description with the approved scope before candidate approval. Keep automatic Windows installation and rollback out of this release. Candidate acceptance must verify the actual manual and Android flows. |
| [#20 — Currency and SRP](https://github.com/hectordoesgorug/BookLedger/issues/20) | Currency support is implemented in source but is not in v1.1.0. Reliable automated SRP sourcing remains unresolved. | Include currency in v1.2.0 only after candidate verification. Keep the issue open for SRP research; do not populate SRP from ambiguous retailer, ebook or secondhand prices. |
| [#2 — Metadata providers](https://github.com/hectordoesgorug/BookLedger/issues/2) | Hardcover/BigBook repairs and the [candidate feasibility review](METADATA_PROVIDER_FEASIBILITY.md) are recorded. No new provider integration is part of this release. The issue still contains an older statement that the new default configuration is awaiting verification; current source/tests and the November 21 test report supersede that status. | Update the issue's status and agree dispositions for ISBNdb, Goodreads and WorldCat separately. Do not close it as part of the v1.2.0 release audit. |
| [#1 — Responsive desktop layouts](https://github.com/hectordoesgorug/BookLedger/issues/1) | Broad resize/reflow coverage remains open, with minimum dimensions and screen-specific behavior not fully specified. The current intake-form race was corrected in the test harness; no production layout defect was demonstrated by that failure. | Keep broader layout improvements deferred. Include exact-candidate visual checks at supported sizes and both themes; record any confirmed clipping or inaccessible controls as a blocker. |
| [#11 — Catalog performance](https://github.com/hectordoesgorug/BookLedger/issues/11) | A targeted image-processing improvement is present. Catalog still rebuilds cards eagerly on Tk's main thread; larger collection behavior and perceived gains remain incompletely assessed. | Defer virtualization/caching absent a reproduced candidate defect. Avoid treating synthetic benchmarks as real-world acceptance. |

The #22 description also predates the implemented download and installer stages. The v1.1.0 report and source documentation record their current limits; the issue should describe those limits rather than imply an automatic Windows updater is included.

## 4. Versioning, migration and compatibility

### Version declarations

- Desktop's canonical version is `src/bookledger/__init__.py` (`1.1.0`); `pyproject.toml` reads it dynamically. `APP_VERSION` and Windows FileVersion/ProductVersion derive from the same value. The release-version tests currently assert `1.1.0` and must be updated with the candidate version.
- Android `mobile/pubspec.yaml` is `1.1.0+2`; Gradle takes `versionName` and `versionCode` from Flutter. Use version name `1.2.0` and a code greater than `2` (at least `3`, or higher if any shared signed candidate already consumed a code).
- Keep namespace and application ID `com.bookledger.mobile`. Verify the candidate APK's identity and production certificate against the published v1.1.0 APK. Release signing properties and keystore are externally configured; this audit did not access them.

### Database and user data

The v1.1.0 release has schema 12. Current main advances it through schema 13 for active currency/rate/conversion audit data and schema 14 for original/shortened book details. The v12 migration test checks that existing asking prices, sales and SRPs remain unchanged; the v13 migration test checks that active details are preserved as the original with no invented shortened candidate. These are automated disposable-database checks, not an upgrade of a real library during this audit.

Treat migration as forward-only. v1.1.0 cannot open a schema-14 library. Before upgrading, make and verify a backup; rollback requires restoring that pre-upgrade backup with the older app. Restore replaces the active library rather than merging it. Preserve portable `data/`, `config.json`, `backups/`, photos, posters and custom files during manual Windows updates.

### Packaging and signing

- `BookLedger-onefile.spec` produces the preferred one-file executable; `BookLedger.spec` produces the one-folder `_internal/` fallback. `scripts/build_windows_portable.ps1` automates the one-file ZIP candidate and can bundle an externally supplied APK. It does not produce the Fallback ZIP or generate the final release checksum manifest; prepare and inspect both package variants separately.
- The Windows build script pins 64-bit CPython 3.14.6 and its build requirements. Its APK path checks signature validity and rejects a debug certificate, but the final candidate still needs an explicit comparison to the known production certificate and the version/package checks above.
- The current Android manifest declares `REQUEST_INSTALL_PACKAGES`, and `pubspec.yaml` adds the `crypto` dependency used by update verification. Refresh the resolved dependency/license inventory and inspect the candidate APK's generated Flutter notices, manifest, SDK levels, permissions, debug/test flags, and APK signature. Preserve the project notices and platform license materials with distributed packages.
- Current Gradle configuration is wrapper 9.3.1, AGP 9.1.1 and Kotlin Android plugin 2.4.0; Gradle's daemon JVM is pinned to Java 25. `TEST_REPORT.md` records a debug build with Kotlin 2.4.10 and future Flutter toolchain-minimum warnings. Reconcile the Kotlin version discrepancy and record the actual Flutter, Dart, Gradle, AGP, Kotlin and Java versions during candidate preparation. The historical debug build does not prove a production release build.
- `REQUEST_INSTALL_PACKAGES` works with Android's per-source user setting on supported devices. The current distribution is direct APK sideloading, not Google Play. Google Play's current policy restricts this permission and prohibits using it for self-updating; a future Play distribution would need a different update path and a fresh policy review ([Play policy](https://support.google.com/googleplay/android-developer/answer/12085295), [Android package-install permission](https://developer.android.com/reference/android/content/pm/PackageManager#canRequestPackageInstalls())). This is not a blocker for the existing GitHub APK distribution.

## 5. Existing verification evidence and limits

The latest test results in [TEST_REPORT.md](../TEST_REPORT.md) are historical and were not rerun:

- Desktop full suite: **675 passed, 19 skipped, 0 failed** after the intake geometry synchronization. Tcl/Tk files missing from the installed runtime account for the skips; native behavior across other display configurations remains unverified.
- Android full suite: **169 Flutter tests passed**, with no skips in the recorded run.
- Flutter analysis: exit status 1 for **21 informational `package:flutter/material.dart` deprecation findings**, without analyzer warnings or errors. Do not describe this as a clean analysis run or hide diagnostics globally.
- Android debug APK build: passed historically, with future Gradle/AGP/Kotlin minimum-version warnings noted in the report. It was not a production-signed release build.
- Provider and currency reports include automated fixture coverage and bounded live checks, with their limits and provenance recorded. BigBook's sampled incremental coverage was low; it remains disabled by default.
- Reported physical v1.1.0 acceptance is maintainer-reported, not independently observed. Settings and pairing persistence after the reported v1.0.0-to-v1.1.0 Android upgrade were not separately verified.

No live newer-release download is currently possible through the eligible updater path because the latest stable release is v1.1.0 and no v1.2.0-or-newer release exists. Installer-interface unit tests do not prove Android package-installer behavior, production signing continuity, or a full update. Pending Android capture queue state is session-only and may be lost if an update closes the process. Windows replacement remains manual and cannot automatically recover from a failed replacement. These are explicit limits, not claims of silent installation or durable mobile capture recovery.

## 6. Native acceptance checklist for the exact v1.2.0 candidate

Use isolated Windows library data and an Android test device/profile that will not endanger the installed production app. Record artifact hashes, device/OS versions, dates, outcomes and skips.

### Windows 11 x64

- [ ] Extract and launch both Portable and Fallback packages; verify version/About metadata and normal exit on the supported Windows environment.
- [ ] Upgrade a disposable v1.1.0 portable library using the documented manual procedure. Verify data, settings, photos, posters and backups remain present; do not copy empty package data folders over the library.
- [ ] Add, edit, search and retrieve metadata; confirm Hardcover's missing-token behavior and later-provider availability without exposing credentials.
- [ ] Exercise Catalog, Inventory, Sales and Reports. Check Add/Edit and main-shell controls at supported minimum dimensions, light/dark themes, scrolling and keyboard access.
- [ ] Convert currency in a disposable library after reviewing the preview; verify asking prices, active/voided sale history, SRP, backup and displayed currency afterward. Confirm notation-only changes do not rewrite amounts.
- [ ] Shorten and review the human-origins, Dan Brown thriller and artificial-intelligence descriptions; retain the original and verify the selected text persists after close/reopen.
- [ ] Create and restore a backup, confirming restore replaces the active library and preserves the documented recovery behavior.
- [ ] Pair with a test Android device; verify single and bulk captures, acknowledgment, interruption, reconnection and cataloging. Confirm unsent mobile captures remain documented as session-only.
- [ ] Check the Update page against the current public release; confirm current version, available version, notes, offline errors and no false update claim. Verify package-specific Windows manual instructions.
- [ ] Do not claim the v1.2-to-newer-release download/update flow passed until a newer eligible release exists. Use automated/mock tests for local verification without creating a fake public release.

### Android

- [ ] Inspect the exact production APK's application ID, `versionName`, monotonically higher `versionCode`, SDK levels, permissions, debuggable/test-only flags, notices and signing-certificate fingerprint.
- [ ] Install it in place over a production-signed v1.1.0 app without uninstalling or clearing data. Verify settings, pairing/secure storage, capture flow and library transfer; record the outcome and device details.
- [ ] Exercise camera, scanning, manual/no-ISBN entry, photos, single and bulk transfers, network interruption and reconnection.
- [ ] Review the update control, confirmation warning, per-source install permission guidance, installer cancellation/failure and return-to-app behavior. Do not imply a current v1.1.0-to-v1.2.0 update can be initiated from the old v1.1.0 app; it lacks the updater.
- [ ] If native installer UI must be tested before a newer eligible release exists, use a disposable emulator/device with a debug-signed installation and a higher-code APK signed by the same test key. Keep it isolated from production app data. Record this only as installer-interface testing, not production-signature or release-update acceptance.
- [ ] Do not claim a v1.2.0-to-newer-release installation test until an actual newer eligible release is available. Keep pending captures clear and transfer them before testing an app restart or upgrade.

## 7. Documentation and release approval requirements

Before candidate approval:

1. Reconcile Issue #22 with the simplified updater and update its completion criteria; keep Issue #20 open for SRP and Issue #2 open until provider research dispositions are agreed. Do not change issues as part of this audit.
2. Update `CHANGELOG.md`, README downloads/version and source-versus-release distinction, release notes, `PROGRESS.md`, privacy/Android guidance where needed, and a new v1.2.0 candidate checklist. Preserve v1.0.0/v1.1.0 records.
3. Correct the stale current-status sentence in `PROGRESS.md` that says the update work is uncommitted, and reconcile its older full-suite count with the later geometry results. Do not rewrite historical test records; make the chronology clear.
4. Audit `THIRD_PARTY_NOTICES.md` against the exact release dependency graph and generated Android `NOTICES.Z`; include applicable runtime, bundled APK, permission and privacy details. Technical notices are not legal clearance.
5. Produce Portable and Fallback ZIPs with the same verified production APK and all required notices; independently inspect both package layouts, user-data exclusion, APK identity/signature and final SHA-256 manifest. Preserve the older release artifacts.
6. Review the 21 analyzer infos and Kotlin-version discrepancy, record tool versions and test outcomes, and disposition any new failures without suppressing valid checks.

## 8. Readiness classification and next steps

### BLOCKER

No confirmed source defect was identified that prevents starting release-candidate preparation.

### REQUIRED VERIFICATION

- Versioned Windows Portable/Fallback builds and the production-signed Android APK must be built and inspected.
- The APK's production signing identity, package ID and higher version code must be confirmed.
- Run the agreed candidate desktop/Flutter checks and complete native acceptance on the exact candidate assets. Resolve any failures; report skips accurately.
- Complete the first manual v1.1.0-to-v1.2.0 Windows and Android production upgrade checks with disposable data and preserve rollback backups.
- Reconcile Issue #22, the `PROGRESS.md` current-status discrepancy, the Kotlin report/config discrepancy, dependency notices, and all release documentation.
- Do not claim a newer-release update download or an update from v1.2.0 to a later version until a newer eligible release exists.

### NONBLOCKING

- The manual Windows install has no automatic rollback; a verified backup and careful package-specific replacement are required.
- SHA-256 is not an independent publisher signature.
- Android pending capture queue state is session-only; send entries before any update that may restart the app.
- Existing Flutter deprecation infos and incomplete Tcl/Tk skips are documented verification limitations; resolve or explicitly disposition them for the candidate.
- Automatic SRP retrieval is not implemented and must remain documented as unavailable.

### DEFERRED

- Automatic Windows file replacement/helper and rollback architecture.
- Goodreads, ISBNdb and WorldCat adapters; OAuth as a separate Hardcover integration decision.
- Automated publisher-SRP retrieval, general desktop reflow redesign and Catalog virtualization/caching absent new evidence.

**Conclusion:** Current `main` is ready to enter v1.2.0 release-candidate preparation. This audit does not approve a candidate or release; candidate builds, verification, native acceptance, documentation reconciliation and an explicit release review remain outstanding.
