# Android release-readiness audit

**Date:** November 17, 2026 (Asia/Singapore)  
**Source baseline:** `b50d2cfb900f593779d693dc11accd7b4d88afaa` on `main`  
**Assessment:** **BLOCKED for a release decision; release-candidate planning may proceed.**  
**Scope:** current post-v1.0.0 Android source and a freshly installed debug APK. No version, tag, release asset, signing credential, or production code was changed.

## Baseline and environment

The starting worktree was clean. Local `origin/main` and the queried remote branch both matched HEAD. The local annotated `v1.0.0` tag object is `7eb58515fd309fc37529ac1d6040d671295e5113` and peels to the historical release commit `1224f3ec25b8a3715f3b6b4234ed2bf9f180bc5c`; this audit did not alter it. Post-release commits include #6 (`ff2dd21`), #5 (`ea411ac`, `111d0de`, `4af3198`), #8 (`77744ec`, `9594c86`), #19 (`5cd716c`), and #16 (`59b0d2b`, `b50d2cf`). The v1.0.0 release checklist remains a historical record.

The test host is Windows with Flutter 3.47.9 and Dart 3.13.7. The connected phone identifies as Xiaomi/Poco model `23122PCD1G`, Android 16/API 36, 1220×2712 display. The test APK is `mobile/build/app/outputs/flutter-apk/app-debug.apk` (205,713,096 bytes), built from the audited source. It was absent on the phone initially, then installed as a fresh debug install after the device accepted the install prompt. Earlier attempts returned `INSTALL_FAILED_USER_RESTRICTED`; no application was uninstalled and no app data was cleared. Camera permission was granted through Android's normal prompt. The debug APK remains installed for further testing.

Application ID is `com.bookledger.mobile`; `mobile/pubspec.yaml` still declares `1.0.0+1`. APK inspection found version name `1.0.0`, version code `1`, min SDK 24, target/compile SDK 36. Debug signing verified with APK Signature Scheme v2 and Android Debug certificate SHA-256 `63f34630bba63eb86397a24eb56bfd022e8a5c17aff84dfa5de97eed1c952378`. The historical production certificate recorded in `THIRD_PARTY_NOTICES.md` is different. Release signing is configured to require an external absolute signing-properties file and keystore outside the repository; no credential contents were inspected or changed.

## Automated regression

| Check | Result | Scope / limit |
| --- | --- | --- |
| `flutter test --reporter expanded` | **126 passed, 0 failed, 0 skipped** | 12 test files; camera and transport behavior uses fakes/mocks where appropriate. |
| `flutter analyze` | **No issues** | Static Flutter analysis. |
| `dart format --output=none --set-exit-if-changed lib test` | **35 files, 0 changed** | Formatting check. |
| `flutter build apk --debug` | **Succeeded** | Debug package only; Gradle emitted a JDK restricted-native-access warning. |
| `.venv\Scripts\python.exe -m pytest -q` | **516 passed, 19 skipped, 0 failed** | Desktop suite; skips concern Tk/display-dependent tests in this environment. |
| `git diff --check` | **Passed** | Final documentation diff checked after edits. |

Flutter dependency resolution reported **19 newer versions incompatible with current constraints**; none were upgraded. The focused coverage present in the complete Flutter suite includes ISBN validation and scanner callbacks (`isbn_scan_feedback_test.dart`, `single_entry_workflow_test.dart`), manual/no-ISBN and Single Entry UI (`widget_test.dart`), photo capture/Retake/correction (`single_entry_workflow_test.dart`, `photo_camera_controls_test.dart`), Bulk insertion/capacity/early completion (`bulk_capture_queue_test.dart`, `widget_test.dart`), reconnection/retry/acknowledgment fakes (`mobile_connection_controller_test.dart`), camera controls and preferences (`photo_camera_controls_test.dart`, `framing_guides_test.dart`, `mobile_app_settings_test.dart`), Clear Data (`clear_mobile_data_test.dart`, `widget_test.dart`), and layout/navigation (`widget_test.dart`). These results do not prove live barcode detection, camera behavior on other devices, or real desktop acknowledgment.

## Phone checks performed

**Single Entry:** Fresh controls showed Scan, Manual, and No ISBN with uniform compact buttons. No ISBN opened the live photo camera. A disposable photo became reviewable and ready without Save; Send remained disabled because the phone was not paired. Cancel Change restored the identifier and photo; Manual correction to a valid ISBN kept the photo. Cancel Retake retained the original app-private photo. Successful Retake replaced it: app-private cache inspection found the new capture file and no superseded `bookledger_capture_*.jpg`. The disposable capture was cleared through the app. A real barcode scan and connected Send were **skipped**.

**Bulk Entry:** With capacity 5, one disposable capture queued at 1/5 and opened the next scanner. Closing that scanner with X retained the queued entry. Holding Queue outside the scanner changed the partial batch to a ready-to-Send state without transferring it. A separate five-photo run reached 1/5 through 5/5; entries 1–4 opened the next scanner, and entry 5 did not. The screen showed 5/5 and Send, disabled while unpaired. Five distinct app-private capture files were present before leaving the batch; normal navigation removed them. Capacity 20 and live transfer were **skipped**. Missing-photo and failed-insertion paths passed automated tests, not hardware fault injection.

**Camera and lifecycle:** Guide 3×3 and Zoom 2.0× appeared in a new capture session and again after a force-stop/restart. Torch was on in the camera, then off after normal background/foreground return; the camera preview resumed. The test changed Guide/Zoom back to the initial L-frame and 1.0× and cleared its capture. Portrait orientation was observed and is declared in the manifest. Native code sets `FLAG_KEEP_SCREEN_ON` on resume and clears it on pause; long-duration screen timeout was not measured. No other hardware model was tested.

## Startup ANR investigation

The first fresh-install cold launch reached a responsive home screen in **6.29 s**. A warm return from background took **0.27 s**. A cold launch after `am force-stop` with Camera permission already granted took **5.93 s**; another warm return while the photo camera was active took **0.22 s** and resumed a working preview. Screens and taps remained responsive. Bounded `logcat -d -t 3000–5000` searches found no `ANR in com.bookledger.mobile`, input-dispatch timeout, or matching reason during these observations. No ANR was reproduced. Its earlier cause remains **undetermined**; these runs cannot rule out intermittent startup or plugin/camera timing failures on other launches or devices. No speculative lifecycle fix was made.

## Transfer and data-integrity assessment

The phone was **not paired**. The existing desktop process was left untouched; no records were written to the real library. A copy of the published Windows package was prepared in the ignored `mobile/build/audit56-desktop/` folder, but no isolated desktop instance was launched and no live transfer was completed. Thus existing pairing, authenticated status on both ends, actual Single/Bulk desktop intake, cataloging, ordering and ID preservation across the network, disconnect/reconnect, failed acknowledgment, idempotent retry, and mobile cleanup after desktop acknowledgment are all **SKIPPED as live integration checks**. Desktop staging and retry logic passed automated Python/Flutter tests only; the previously reported v1.0.0 physical transfer is historical evidence, not validation of this post-release build. The isolated package copy remains locally; it contains the extracted release package and no audit library records.

The current mobile capture and Bulk queue metadata live in memory. `SingleEntryWorkflow.dispose()` and `BulkCaptureQueue.dispose()` clean owned photos on normal screen disposal, but a process kill can discard the in-memory identifiers/queue while temporary photo files remain inaccessible to the workflow. A failed transfer retains captures for retry **while that app session survives**; durable mobile recovery after process interruption is not implemented. This is consistent with the README's “session-only” description but is a material data-loss risk to settle before release approval. The desktop's `MobileIncomingStore` stages accepted captures durably and checks capture UUIDs for duplicate/conflict handling; no live device/desktop failure sequence was executed in this audit.

## Installation, permissions, privacy, and dependencies

The debug APK was a **fresh install**, not an in-place upgrade. Debug signing differs from the historical production key. The development source still uses code `1`; a future production-signed upgrade needs an approved higher version code and the same production signing identity as v1.0.0. No production-signed candidate was built or installed, and upgrade/data-persistence compatibility remains pending the release-candidate phase. The v1.0.0 package and checklist were not changed.

The built APK declares Camera, Internet, network-state, and AndroidX's package-scoped dynamic-receiver permission. It does **not** declare microphone, broad shared-storage, or a background wake-lock permission. The camera is used with audio disabled; camera preview and Torch disposal on backgrounding are implemented. Source review found no new BookLedger analytics/tracking or external application endpoint; pairing/transfer still use token-authenticated, unencrypted local HTTP and the GitHub button opens the project URL. ML Kit's documented possible SDK network activity remains disclosed in `docs/PRIVACY_NOTICE.md` and `mobile/README.md`. Network traffic was not independently captured, so absence of other SDK traffic is not proven. The notices and privacy description match the inspected source/manifest at this level.

Compared with the v1.0.0 tag, `mobile/pubspec.lock` has **no package version or checksum change**. Its sole change marks already-resolved `camera_platform_interface` 2.15.0 a direct development dependency for test fakes; no new runtime package follows from that declaration. `camera` 0.12.2, `mobile_scanner` 7.5.0, Android Gradle plugin 9.1.0, Kotlin 2.4.0, and Flutter engine revision `89c39edfdfae2949f6806e4a315c0c08522238b7` remain as recorded. The current debug graph resolved CameraX 1.6.2 and ML Kit barcode scanning 17.3.0. The debug APK contains Flutter's `assets/flutter_assets/NOTICES.Z`; repository license texts and distribution instructions remain present. `THIRD_PARTY_NOTICES.md` contains a dated follow-up comparison. The future release-runtime graph, exact release APK notice set, and legal sufficiency need separate review; this audit does not declare legal clearance.

## Classification and next decision

| Class | Finding / required action |
| --- | --- |
| **BLOCKER** | No current-build authenticated Single/Bulk transfer and desktop acknowledgment on a disposable library. Run controlled end-to-end and interrupted/retry checks before release approval. |
| **BLOCKER** | Pending captures are session-only. Decide explicitly whether loss of the in-memory queue after process interruption is acceptable; otherwise authorize a bounded durability/recovery repair and regression tests. |
| **BLOCKER** | Production upgrade path unverified: future approved version code, production signing, in-place install, settings/pairing persistence, and exact release notices must be checked on a release candidate. |
| **WARNING** | Earlier startup input-focus ANR was not reproduced here; cause remains unknown. Repeat cold/warm tests on the signed candidate and another device if available. |
| **WARNING** | Real barcode detection, capacity 20 physical capture, permission denial, other devices, and network traffic observation remain untested in this audit. |
| **WARNING** | JDK restricted-native-access warning and 19 newer constrained package versions; no failure or dependency upgrade occurred. |
| **WARNING** | The release-planning document names `CHANGELOG.md`, but that file does not exist in this checkout. Release history is currently in the release notes, roadmap, and test report; choose a future-release change record before publication. |
| **DEFERRED** | Unrelated backlog enhancements, additional camera hardware calibration, and nonessential design changes. |

### Physical-test checklist for a release candidate

- [ ] Use a **disposable desktop library** and test books/photos; verify the desktop data path before pairing. Keep the real inventory closed to test writes.
- [ ] Install the **production-signed, higher-code** candidate over an existing production-signed v1.0.0 installation without uninstalling or clearing data; verify pairing, settings, and pending-data expectations.
- [ ] Cold launch, warm launch, force-stop/relaunch, Camera permission granted/denied, and background/foreground camera return; record any ANR dialog and bounded logs.
- [ ] Scan a valid physical ISBN; test Manual and No ISBN; capture, Change/Cancel, Retake/Cancel, and replacement-photo cleanup.
- [ ] Transfer a Single Entry and confirm authenticated desktop acknowledgment, intake, cataloging, and mobile cleanup.
- [ ] Queue five independent captures; verify 1/5–5/5, automatic scanner progression, no sixth scanner, explicit Send, order/IDs, desktop acknowledgment, and cataloging.
- [ ] Finish a partial batch by closing the scanner and holding Queue; confirm no transfer occurs until Send.
- [ ] Break and restore connectivity during a transfer; verify retained pending data, retry, no unintended desktop duplicates, and behavior after app/process interruption under the agreed session-durability rule.
- [ ] Exercise capacity 20 and at-capacity rejection if practical; test a second Android model if available.
- [ ] Inspect the exact signed APK manifest, signature, bundled `NOTICES.Z`, accompanying notices/privacy files, and full release dependency graph before distribution.

**Recommendation:** Proceed to planning a bounded release candidate and isolated desktop/phone integration session. Do not approve publication from this debug audit. First resolve the session-durability decision and verify live acknowledged transfers; then validate a signed higher-code upgrade and the exact release package. No new version or release artifact was produced here.
