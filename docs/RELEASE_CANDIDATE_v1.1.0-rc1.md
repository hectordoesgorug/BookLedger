# v1.1.0-rc1 candidate preparation report

**Disposition: accepted for release preparation with documented exceptions.** This report records the preparation state before publication; earlier candidate evidence remains historical.

## Baseline and changes

Prepared from clean `main` at `8b4b904d83627c4b11ae749dd83d32bc8b46d8bc`; local and fetched `origin/main` match. Historical `v1.0.0` peels to `1224f3ec25b8a3715f3b6b4234ed2bf9f180bc5c`.

Desktop is `1.1.0`; Android is `1.1.0+2`, application ID unchanged. Release materials include [changelog](../CHANGELOG.md), [draft release notes](RELEASE_NOTES_v1.1.0.md), and [acceptance checklist](RELEASE_CHECKLIST_v1.1.0.md). Source/documentation changes are in `src/bookledger/__init__.py`, `mobile/pubspec.yaml`, `tests/test_release_version.py`, `README.md`, `mobile/README.md`, `docs/PRIVACY_NOTICE.md`, and `THIRD_PARTY_NOTICES.md`. Existing implementation scope and compatibility notes are summarized in the changelog.

## Automated verification

- Focused version and packaging tests: **6 passed**.
- The photo-preview test was corrected after review showed that height growth at fixed width need not enlarge a portrait image already constrained by width. The target test passed five consecutive runs; related intake/callback tests passed 92 with 1 Tcl/Tk skip. The final desktop full suite passed 517, skipped 17, and failed 1 separate minimum-size geometry assertion (body and viewport both measured 769 px); see the dated TEST_REPORT entry. Migration and backup/restore focused suite: **83 passed** with disposable test data.
- Flutter tests: **126 passed, 0 failed, 0 skipped**. `flutter analyze`: no issues. Dart formatting: 35 files checked, 0 changed.
- `git diff --check`: passed; configured LF-to-CRLF notices only.
- Windows build requirements matched CPython 3.14.6 and pinned packages. The established one-file build and existing one-folder fallback spec succeeded. Both executables carry FileVersion/ProductVersion `1.1.0`.
- Each final Windows ZIP passed CRC and structure checks, includes required license/privacy materials, embeds the byte-identical standalone APK, and contains no user config/database or signing material. Disposable extractions of both ZIPs launched for 12 seconds, then were closed. This is a build-host startup check, not physical Windows 11 or clean-machine acceptance.

## Android identity and dependency review

The production release APK built using the existing external signing properties. Android SDK `apksigner` verified APK Signature Scheme v2. Its certificate SHA-256 `539e4a74e133604ec420c1d3a19584200e2a926f19f0ba7b4652de0bb7a85f3d` matches the historical v1.0.0 production APK. Identity is `com.bookledger.mobile`, version `1.1.0`, code `2`; min SDK 24, target/compile SDK 36; `debuggable=false`, `testOnly=false`. Permissions are Camera, Internet, network state, and AndroidX's package-scoped receiver permission. The candidate was not installed.

The exact release APK's compressed Flutter `NOTICES.Z` was decompressed and inspected (1,335,817 bytes), including camera, camera_platform_interface, mobile_scanner, Flutter engine, and other resolved notices. The release runtime graph contains 101 external Maven coordinates. Eight have no license declaration in their Maven POM; they match the components and upstream/artifact evidence already documented in `THIRD_PARTY_NOTICES.md`. CameraX and ML Kit versions remain consistent with the prior audit. All 92 Dart/SDK package entries have local package or SDK license material. No dependency was upgraded; the only lockfile difference from v1.0.0 remains the direct development classification of already resolved camera_platform_interface 2.15.0. These technical findings are not legal clearance.

## Candidate artifacts

All paths are under `dist/v1.1.0-rc1/`. `SHA256SUMS-rc1.txt` contains hashes of the three binary files.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `BookLedger-v1.1.0-rc1-Windows-x64-Portable.zip` | 60,133,742 | `6ae46145f019c6b3bc7638e5cc97c78a9caeee6138e88124af6b5be5ba1bf276` |
| `BookLedger-v1.1.0-rc1-Windows-x64-Fallback.zip` | 60,982,251 | `8a5f64753c30951da91ac5662c20d08b3f875f6583452f5afd8cd17b6e3fd9d1` |
| `BookLedger-v1.1.0-rc1-Android.apk` | 71,633,402 | `26e09dd5eba9cba6f4b9863c0118063c403f285a92a31c700b0a86dce4c0f854` |

The previous v1.0.0 Windows ZIP, Android APK, and checksum manifest retain their recorded SHA-256 values. Their historical tag and release were not changed.

## Historical pending acceptance and limits (at preparation)

Physical Windows and Android checks remain pending on these exact artifacts. This includes real barcode and camera testing, authenticated Single/Bulk transfer and acknowledgment, interrupted transfer/retry, and an in-place upgrade from production-signed v1.0.0 with data preservation. The audit left a debug-signed APK installed; it is not a valid production upgrade baseline. No APK was installed as part of this work.

The Android capture queue remains session-only; process termination can lose pending identifiers/queue state. An earlier startup ANR remains unexplained, though it was not reproduced in the earlier debug audit. Eight Maven POM license declaration gaps and privacy/legal suitability require further review. See the checklist for physical acceptance checks.

## Git status

Working tree contains only version and release documentation updates; generated candidate binaries/evidence are under ignored `dist/` and `build/`. Branch remains `main` at the starting HEAD and aligned with `origin/main`. No commit, push, tag, or publication occurred.

## Physical acceptance and release exception (recorded November 18, 2026)

The November 18 physical-test report records PASS using v1.1.0-rc1 for Windows portable execution; APK export; Pairing, Forget Pairing, Unpair and reconnection; multiple-instance blocking; Purge with default Clam preserved; all backup/restore features; Android camera controls; Sales, voids, reports and status transitions; updated desktop layout; poster creation; Single Entry including edge cases; and Bulk Entry including partial and full queues. These results were reported and not independently observed. Device/build details and separate fallback physical testing were not supplied.

Production upgrade PASS was reported after first installing the historical production-signed v1.0.0 APK, then installing the exact rc1 APK over it. Android presented an update confirmation and installation succeeded. Post-upgrade settings and pairing persistence were not separately reported as verified.

The remaining display-sensitive minimum-size geometry assertion was accepted as a non-blocking release exception based on reported physical layout testing. The automated suite remains 517 passed, 17 skipped, 1 failed; it is not fully passing. The original preview failure was a corrected test defect; production preview code was unchanged. The transient mobile-connection failure passed three isolated reruns. Session-only pending captures and the prior unreproduced startup ANR remain disclosed limitations.

Final staging is `dist/v1.1.0/`. All three copied binary SHA-256 values match the accepted candidates. ZIP CRC, composition, embedded APK identity, Android package/version and production signature were reverified. No rebuild occurred.

## Publication and independent verification (November 18, 2026)

BookLedger v1.1.0 is published at https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.1.0 as a stable release (not draft/prerelease). Annotated tag object `794954ae76d052bfbeae196a9396a26e60afeca3` peels to approved commit `01dc3990e9fa321e5cf2f815ce509d5a3736e9ac`. The reviewed source commit preceded tag creation and publication.

All four public assets were downloaded independently and SHA-256 verified against final staging and the published manifest. Sizes: Portable 60,133,742 bytes; Fallback 60,982,251 bytes; APK 71,633,402 bytes; SHA256SUMS.txt 317 bytes. Candidate binaries were not rebuilt or modified. Historical v1.0.0 release metadata and its asset records exactly match the pre-publication snapshot. Evidence and downloaded bytes are retained under ignored `build/release58-verification/`.

The accepted automated exception remains 517 passed, 17 skipped, 1 failed (display-sensitive minimum-size assertion); physical acceptance remains documented as reported testing. Session-only pending captures, the prior unreproduced ANR, and unverified post-upgrade settings/pairing persistence remain disclosed. No fresh automated or physical test run is implied by publication verification.

### Historical ANR context clarified (November 18, 2026)

The earlier ANR report concerned a Poco X6 experiencing lag while rapid charging and connected to a PC through TwinDesk. No ANR was reproduced during the subsequent audit, and no root cause has been established. These circumstances are context, not a confirmed explanation or an active verified defect. Historical observations and test results above remain unchanged.
