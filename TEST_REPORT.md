## v1.2.0-rc1 candidate verification — November 21, 2026

The desktop release version is `1.2.0`; Android is `1.2.0+3`. The full results and staged artifact hashes are in the [v1.2.0 candidate report](docs/RELEASE_CANDIDATE_v1.2.0-rc1.md). The published v1.1.0 packages and production phone installation were not changed.

- `.venv\Scripts\python.exe -m pytest -q -rs` — **676 passed, 18 skipped, 0 failed**. Tcl/Tk `init.tcl` and `ttk/sizegrip.tcl` runtime files are missing for the skipped display tests.
- `.venv\Scripts\python.exe -m pytest tests\test_updates.py tests\test_update_download.py tests\test_update_archive.py tests\test_release_version.py tests\test_portable_packaging.py tests\test_uuid_backup_restore.py tests\test_currency.py -q -rs` — **94 passed, 1 skipped, 0 failed**. The skipped Tk update-page test cannot load `tk.tcl`.
- `tests\test_intake_ui.py::test_form_minimum_size_keeps_scrollable_content_reachable` — **1 passed in each of five separate runs** at the exact `960×700` requirement.
- `tests\test_release_version.py` — **3 passed**. The local editable package metadata was refreshed from 1.1.0 to 1.2.0 after the initial full run exposed stale environment metadata and a file-version expectation still set to 1.1.0.
- `.venv\Scripts\python.exe -m compileall -q src tests`, `.venv\Scripts\python.exe -m pip check`, the pinned isolated Windows build environment's `pip check`, and `git diff --check` — **passed**.
- From `mobile/`, `flutter test --reporter expanded` — **169 passed, 0 failed, 0 skipped**.
- From `mobile/`, `flutter test test\update_service_test.dart test\update_check_action_test.dart --reporter expanded` — **43 passed, 0 failed, 0 skipped**.
- From `mobile/`, `flutter analyze` — **21 informational `package:flutter/material.dart` deprecations, no warnings or errors, exit 1**. These are SDK import notices; no Dart sources changed for the release version update.
- From `mobile/`, `dart format --output=none --set-exit-if-changed lib test` — **40 files, 0 changed**.
- Android `flutter build apk --debug --no-pub` — **passed** from an isolated project copy after `flutter pub get` created its generated package configuration. The first copied-tree attempt lacked `.dart_tool/package_config.json` and did not reach compilation.
- Android `flutter build apk --release --no-pub` — **passed**, 401.9 seconds, with external production signing configuration. The candidate certificate matches the published v1.1.0 APK.

The first full desktop run during version changes had **673 passed, 19 skipped, and 2 failed** because test expectations and installed editable metadata still described v1.1.0. Those causes were corrected before the final full run. The first Fallback packaging smoke test exposed a staging error with the required `_internal/` layout; it was corrected, and fresh extractions of both final packages then launched the v1.2.0 Dashboard and closed normally. The Android runtime dependency report initially hit the release-signing guard because the task name contains `releaseRuntimeClasspath`; rerunning with the external signing configuration resolved the graph without printing or moving credentials. The final graph and notice findings are recorded in `THIRD_PARTY_NOTICES.md`.

Flutter 3.50.0 / Dart 3.14.0, Gradle 9.3.1, AGP 9.1.1, JBR/Java 25.0.4, Build Tools 36.0.0, and Kotlin compiler 2.4.10 were observed. `settings.gradle.kts` declares Kotlin plugin 2.4.0; Gradle's loaded Kotlin plugin classloader and compiler report 2.4.10. Gradle's embedded Kotlin 2.2.21 is a separate runtime. No toolchain version change was made because both Android builds passed. Future Flutter minimums and AGP/Kotlin deprecation notices remain maintenance warnings.

The candidate APK is production-signed, non-debuggable, version 1.2.0/code 3, min SDK 24, target/compile SDK 36, and supports `arm64-v8a`, `armeabi-v7a`, and `x86_64`. No install, upgrade, uninstall, data clear, pairing change, or capture modification was performed on the connected Android 16 device. Native Android upgrade and feature acceptance remain pending.

## Portable startup investigation — November 21, 2026

Baseline: Windows 11 Home x64, build 26200, `main` at `4b486a5eaf2ef83a304860d7c464220a97aba004`, aligned with `origin/main`. Real-time antivirus protection remained enabled. C: and E: are local NTFS volumes. All runs used fresh disposable package extractions, test profiles through process-scoped `LOCALAPPDATA`/`APPDATA`, and dedicated temporary directories. “First” means first launch after extraction; OS file caches were not forcibly cleared. Timing is executable process launch to the visible `BookLedger · Book collection manager` window title. Each measured app accepted normal close and its process tree exited normally.

| Package and location | Root process created (+08:00) | Window time |
| --- | --- | ---: |
| v1.2.0-rc1 Portable, executable/temp on E: | 13:49:51.214 first | 2.257 s |
| v1.2.0-rc1 Portable, executable/temp on E: | 13:50:10.764 warm | 2.214 s |
| v1.2.0-rc1 Portable, executable/temp on E: | 13:53:55.309 diagnostic | 3.617 s |
| v1.2.0-rc1 Portable, executable/temp on C: | 13:52:33.696 first | 2.996 s |
| v1.2.0-rc1 Portable, executable/temp on C: | 13:52:39.413 warm | 2.657 s |
| v1.2.0-rc1 Portable, executable/temp on C: | 13:53:49.599 diagnostic | 2.597 s |
| v1.2.0-rc1 Fallback, extracted on E: | 13:50:31.899 first | 1.317 s |
| v1.2.0-rc1 Fallback, extracted on E: | 13:50:35.406 warm | 1.094 s |
| Published v1.1.0 Portable, extracted on E: | 13:50:52.351 first | 1.975 s |
| Published v1.1.0 Portable, extracted on E: | 13:50:57.305 warm | 2.429 s |

Exact hashes: rc1 Portable `b1b06ace51b1c0cc849279c00255528b7796b6a85659a3bea425c52a24138645`; rc1 Fallback `5011a8366c2619d61f4843867e5c32ebb955547045e3103fa9472eba9413e629`; downloaded [published v1.1.0 Portable](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.1.0/BookLedger-v1.1.0-Windows-x64-Portable.zip) `6ae46145f019c6b3bc7638e5cc97c78a9caeee6138e88124af6b5be5ba1bf276` (60,133,742 bytes). The rc1 Portable executable is 25,480,919 bytes. Diagnostic runs recorded a one-file child process starting 1.008 seconds after its parent on E: and 1.293 seconds after it on C:. While the application window was open, its `_MEI` extraction contained 1,038 files totaling 47,078,088 bytes. Its process used about 0.9–1.2 CPU seconds before the window appeared.

**Classification: Environmental limitation (process-selection error in the measurement harness).** The >120-second delay was not reproduced with process-tree-aware timing. The invalid initial probe watched only the windowless PyInstaller parent while its child had the visible dashboard. This explains the long wait in that probe; the earlier >120-second observation is consistent with the same error, but its original instrument was unavailable, so its exact provenance cannot be confirmed. Normal one-file extraction adds about one second relative to the Fallback package in these runs. No Defender event trace or disk performance trace was collected, and these measurements are from one computer rather than a controlled multi-system benchmark.

## Native update discovery and desktop repository link — November 20, 2026

Baseline: `main` at `255d59ed4cd002da2d928c5f91d659003fe5c40b`, aligned with local `origin/main`, with the existing 25-file uncommitted implementation/stabilization changes preserved. The results here are independently observed native checks and subsequent regressions. Earlier automated and reported physical evidence remains below with its original counts and limitations.

### Native Windows checks

The current source ran with the project's `.venv` Python/Tk/ttkbootstrap environment and the normal `BookLedgerApp` implementation. A disposable `AppPaths` root, process-local application-profile paths and library lock isolated the empty test database, configuration and credentials. Test mobile services used disposable storage and ephemeral ports. No existing library was opened. Read-only Tk timer diagnostics supplemented visible native interaction; they did not replace the GUI checks.

| Check | Observed result |
| --- | --- |
| Initial Dashboard at `1280×800` and `1000×650` | **Defect found:** workspace content consumed the available pack height, leaving the status/update labels unmapped at `1×1`. The earlier empty-workspace test missed this case |
| Corrected minimum-size layout | **Passed:** the bottom row is packed before the expanding workspace. Status text and the underlined Check for Updates link remain visible beside one another; long-status/tall-content coverage now verifies mapped controls |
| Light/dark appearance | **Passed:** native Clam light presentation and the application's Dark theme show readable hyperlink colors and hover/focus emphasis. Both Visit GitHub below About and the workspace update link fit at `1000×650` |
| Mouse and keyboard update activation | **Passed:** mouse click and Shift-Tab/Enter open the modeless dialog. Focus diagnostics matched the update link after keyboard navigation |
| Live release discovery | **Passed:** installed/available `1.1.0`, official v1.1.0 notes, and the explicit message “No newer stable version is available.” The source build correctly retains **Unsupported Update** eligibility; it is not represented as a verified frozen package |
| Dialog/readability/normal operation | **Passed:** version text, scrollable plain-text notes and actions are readable in both themes. Closing returns to the main window; search focus and Catalog navigation work normally |
| Network failure | **Passed:** a process-only local HTTPS proxy deliberately held/refused the official GitHub CONNECT request. Checking and disabled retry painted while the request was outstanding, followed by **Unable to Check**, installed `1.1.0`, available `unknown`, and a clear connection/retry message. Closing restored normal navigation. This was a controlled failed request, not a machine-wide network disconnection |
| Visit GitHub | **Passed:** the new text link appears directly below About and shares `TextLink` mouse/keyboard behavior. Ctrl-F then Shift-Tab focused it; Enter opened the official BookLedger repository in the default Brave browser. Browser success, false return and exception paths are also automated |

The status-row regression first failed with the update link unmapped and passed after the pack-order correction. Adding the repository link exposed insufficient sidebar space with a shop logo: a focused run recorded **116 passed, 2 skipped, 1 failed** at the existing footer ordering assertion. Reducing sidebar button vertical padding from four to two pixels per edge retained the new link and the footer. The final minimum-window regression uses the supported maximum `176×66` logo, verifies link placement below About/above the logo, and preserves connection/version containment assertions. No assertion was weakened.

### Native Android checks

Device: **POCO X6 5G / 23122PCD1G**, Android **16 / API 36**. The existing non-debug `com.bookledger.mobile` installation was version **1.1.0 / code 2**. Its signer SHA-256 was **`539e4a74e133604ec420c1d3a19584200e2a926f19f0ba7b4652de0bb7a85f3d`**, differing from the debug signer's **`63f34630bba63eb86397a24eb56bfd022e8a5c17aff84dfa5de97eed1c952378`**. The ordinary debug APK was therefore not installed over it.

A temporary Gradle init script outside the repository changed only the acceptance build's application ID to `com.bookledger.mobile.acceptance` and label to **BookLedger Acceptance**; production Gradle identity/signing configuration stayed unchanged. Manifest/debug-signature checks preceded installation. Native tests used the actual Settings and update implementations, a real isolated pairing service and a synthetic app-private cached JPEG. A temporary debug entry point routed only GitHub API requests to a closed loopback proxy when a marker in that acceptance app's private files existed. Removing that marker restored direct live HTTPS requests. This fault injection did not alter phone Wi-Fi or production app networking.

| Check | Observed result |
| --- | --- |
| Settings structure and placement | **Passed:** pairing, appearance, Clear Data and update controls remain on one page. The teal text update action follows the red Clear Data button with distinct spacing. All controls fit the tested phone viewport. Smaller-viewport/large-text scrolling is covered separately by the automated Settings tests; native forced-small-viewport scrolling was not performed |
| Light and dark presentation | **Passed:** the appearance switch changed the acceptance app in both directions; Settings, version text, release notes and dialog actions remain readable |
| Stable release recognition | **Passed:** installed `1.1.0 (code 2)`, available `1.1.0`, real release notes and the explicit no-newer-version message. **Unsupported Update** remains correct for the debug application |
| Failed request and recovery | **Passed:** the acceptance-only proxy fault showed **Unable to Check**, available `unknown` and a recoverable connection/service message. Back returned to Settings; removing the marker and checking again retrieved v1.1.0 successfully. No installer was invoked |
| Back and repeated checks | **Passed:** Back dismissed the dialogs and returned through Settings to Home. Repeated live checks worked, and pairing still showed an authenticated connection to the isolated desktop service |
| Pairing/preferences/cached image | **Passed within the fixture scope:** four of five compared file hashes were unchanged, including the 631-byte cached JPEG and ordinary preferences. The JPEG SHA-256 remained **`8579c1034f2eddd87ed11c521b7ac944c86802a1f5f3d8b9fc3b28cdb1d71520`**. `FlutterSecureStorage.xml` ciphertext changed while the existing connection controller persisted a validated endpoint during reconnection. Authenticated connectivity remained valid; exact plaintext-token equality was not inspected. No Forget Pairing or Clear Data operation was performed |

The JPEG was a seeded file fixture, not a physical camera capture or active in-memory Bulk queue. Native queue preservation across process termination or an upgrade is not established by these checks. The temporary acceptance package was removed after testing; only the original production package remained. Its version, non-debug flags and **November 18, 2026, 07:51:55** installation-update timestamp were unchanged. The isolated desktop, pairing server and failure proxy were closed. No production app storage, signing material, library data or published assets were changed.

### Regressions after native corrections

| Command | Actual result |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest tests/test_updates.py tests/test_update_archive.py tests/test_app_callbacks.py -q -rs` | **119 passed, 0 failed, 0 skipped**, 7.46 s |
| `.venv\Scripts\python.exe -m pytest tests/test_app_callbacks.py::test_sidebar_footer_fits_with_all_navigation_buttons_at_minimum_window_size -q -rs` | **1 passed, 0 failed, 0 skipped**, 1.95 s, with the maximum-height logo fixture |
| `.venv\Scripts\python.exe -m pytest -q -rs` | **652 passed, 19 skipped, 0 failed**, 109.49 s. Seventeen provider-diagnostic skips cite missing `ttk/sizegrip.tcl`; two callback-geometry cases cite Tcl/Tk initialization files (`ttk/notebook.tcl`, `auto.tcl`). The updated minimum-size case skipped here but passed in the focused command above. Historical mobile-connection intermittency did not recur and is not claimed resolved |
| `.venv\Scripts\python.exe -m compileall -q src tests` and `git diff --check` | **Passed** |
| From `mobile/`, `flutter test test/update_service_test.dart test/update_check_action_test.dart test/mobile_app_settings_test.dart --reporter expanded` | **36 passed, 0 failed, 0 skipped** |
| From `mobile/`, `flutter test --reporter expanded` | **156 passed, 0 failed, 0 skipped** |
| From `mobile/`, `flutter analyze` | **21 informational Material import deprecations, 0 warnings/errors**, exit **1**; the previously classified 19 baseline / 2 new imports remain unchanged |
| From `mobile/`, `dart format --output=none --set-exit-if-changed lib test` | **39 files, 0 changed**, exit 0 |
| From `mobile/`, `flutter build apk --debug` | **Passed**, 39.9 s, using the normal application ID and entry point, without acceptance overrides. Future Gradle/AGP/Kotlin minimum warnings remain |

Normal debug output is `mobile/build/app/outputs/flutter-apk/app-debug.apk`, **180,865,755 bytes**, SHA-256 **`50d8cb2657ebf581791f0a6278de56e404fd1d977f105b2ede5db2c20ce687d3`**. Build Tools badging confirms **BookLedger Companion**, `com.bookledger.mobile`, version **1.1.0 / code 2**, debuggable. It was not installed on the production package. The retained acceptance APK is a separate local test artifact, **204,004,377 bytes**, SHA-256 **`1dbaeebed9e0874003e452527918013cfc9c9d702a1a400b38e76bc9eb53d180`**; its fault-injection entry point is not part of normal builds or tracked source.

Source changes from native acceptance are confined to the status/sidebar layout and repository callback in `src/bookledger/app.py`, the shared `TextLink` in `src/bookledger/ui/updates.py`, explicit development-build version messages in the Python/Dart update services, and their focused regressions in `tests/test_app_callbacks.py`, `tests/test_updates.py` and `mobile/test/update_service_test.dart`. README, progress and update-system documentation reflect the resulting behavior. Test harnesses, fixture secrets and native screenshots remain outside tracked source; incidental generated plugin-order changes were removed.

The source/debug discovery interface has native acceptance evidence on these two environments. Frozen Windows execution, production-signed Android upgrades, physical pending-queue preservation during an upgrade and real installation remain unverified. Final Git remains `main` at the same HEAD with the existing implementation plus these targeted corrections unstaged. No commit, push, issue modification, tag or release publication was performed.

## Update discovery verification stabilization — November 20, 2026

Baseline: `main` at `255d59ed4cd002da2d928c5f91d659003fe5c40b`, aligned with local `origin/main`, with the existing 22-file uncommitted update-discovery change preserved. The earlier results below are historical; this entry records independently reproduced failures and the corrected verification baseline. Update discovery, installation scope, credentials, portable data and published release packages are unchanged.

### Findings and targeted corrections

- **Desktop geometry:** the original isolated test failed at the extra `850 < 850` assumption. A disposable Tk probe measured a valid default `1120×850` window with body/viewport heights `822/822`; at the actual minimum `960×700`, those heights were `822/672`, and scrolling reached `(0.18248175182481752, 1.0)`. Equal body/viewport heights are normal at the content-sized default window. The previous test requested a resize without asserting that Windows had applied it; a single `update()` is not a window-manager acknowledgement. The test now waits for the requested Configure event with a two-second failure timeout, asserts exact dimensions, derives the default from content height and exercises larger sizes relative to that default. It retains body-overflow, positive scroll-offset, action reachability, field alignment and preview-growth assertions at `960×700`. No production form layout change was needed. The historical `798/798` observation was not independently reproduced before correction in this isolated run; it is consistent with measuring the old viewport and is no longer accepted without checking the actual window size.
- **Camera fixture:** the old focused regression independently reproduced Windows errno 32 during deletion of its own temporary directory. It supplied ten non-image bytes to `Image.file`, used a fixed 100 ms sleep for capture, and did not explicitly dispose the retaken camera or finish/evict image work before fixture deletion. The fixture now supplies a valid 2×3 PNG, pumps until capture readiness and decoded `RawImage` availability while yielding to real IO, then unmounts, settles and evicts that exact file image before cleanup. The original byte-preservation checks remain; a new assertion verifies both camera controllers were disposed. The condition waits fail after five seconds; no fixed delay, delete retry, forced deletion or exception suppression was added. No production camera leak was established.
- **Banner fixture:** the old test independently reproduced expected ratio `3.0` versus `Infinity`. `pumpAndSettle()` can finish without pending frames while native asset IO/decoding remains unfinished; the image then has zero height. The test now loads and precaches the real asset outside FakeAsync before displaying the home screen, fails on decode errors/timeouts, and retains the original rendered ratio assertion. Production banner rendering was not changed. Exploratory attempts that awaited already-pending fake-zone image futures stalled and were interrupted; one intermediate combined run recorded 1 passed / 1 failed with synchronization timeouts before the final condition-based repair. These attempts are not counted as successful verification.
- **Android build:** only the AGP pin changed, **9.1.0 → 9.1.1**, in `mobile/android/settings.gradle.kts`. [AGP's compatibility table](https://developer.android.com/build/releases/agp-9-1-0-release-notes) supports the existing Gradle 9.3.1 wrapper. Inspected toolchain: Flutter **3.50.0**, Dart **3.14.0**, Android SDK Build Tools **36.0.0**, Android Studio JBR **25.0.4**, Java/JVM target **17**. The Kotlin plugin declaration remains **2.4.0**; Flutter reports effective Kotlin **2.4.10** during the build, while Gradle's own embedded Kotlin is **2.2.21**. No wrapper, Kotlin, Java, signing, package identity or version change was made. Dependency validation remains enabled. Flutter warns of future minimums Gradle 9.5.0, AGP 9.3.1 and Kotlin 2.4.20; the direct Gradle check also emits JDK native-access warnings. These are maintenance warnings, not the former build-stopping AGP minimum error.
- **Analysis:** all **21** findings are `deprecated_member_use` infos for `package:flutter/material.dart`, whose installed SDK entry point is marked deprecated after 3.47.0-0.0.pre. A comparison with HEAD finds **19** baseline imports and **2** new imports (`updates/update_check_action.dart` and its test). The new imports add the same SDK migration diagnostic, not a correctness warning. `material_ui` is not a current project dependency; a partial migration or private SDK imports would add scope and compatibility risk. The existing public import convention is retained, without local or global suppression. There are no analyzer warnings/errors or new control-flow findings. Analysis still exits 1 and is an explicitly evaluated exception, not a clean pass.

Changed during stabilization: `tests/test_intake_ui.py` (geometry synchronization), `mobile/test/photo_camera_controls_test.dart` (valid image/lifecycle regression), `mobile/test/widget_test.dart` (banner IO/decode synchronization), `mobile/android/settings.gradle.kts` (AGP patch), `mobile/README.md` (build baseline), `docs/UPDATE_SYSTEM.md`, `PROGRESS.md` and this report (verification and acceptance limits). Existing update-discovery files/tests were preserved. Incidental generated Windows plugin-order changes were removed.

### Final verification commands

Desktop commands run from the repository root; Flutter/Dart commands run from `mobile/`:

| Command | Result |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest tests/test_intake_ui.py::test_form_minimum_size_keeps_scrollable_content_reachable -q -rs` | Before correction: 1 failed (`850 < 850`); after correction: **1 passed, 0 failed, 0 skipped**, 3.86 s |
| `.venv\Scripts\python.exe -m pytest tests/test_updates.py tests/test_update_archive.py tests/test_intake_ui.py tests/test_app_callbacks.py::test_sidebar_footer_fits_with_all_navigation_buttons_at_minimum_window_size -q -rs` | **77 passed, 1 skipped, 0 failed**, 21.61 s; dialog test skipped for `tcl_findLibrary` initialization failure |
| `.venv\Scripts\python.exe -m pytest -q -rs` | **650 passed, 18 skipped, 0 failed**, 61.41 s; geometry regression passes. Seventeen provider-diagnostic cases skip for missing `ttk/sizegrip.tcl`; the sidebar geometry case skips for missing `ttk/defaults.tcl`. No assertion was suppressed |
| `.venv\Scripts\python.exe -m compileall -q src tests` | **Passed**, exit 0 |
| `git diff --check` | **Passed**, exit 0; configured LF-to-CRLF notices only |
| `flutter test test/update_service_test.dart test/update_check_action_test.dart test/mobile_app_settings_test.dart --reporter expanded` | **36 passed, 0 failed, 0 skipped** |
| `flutter test test/photo_camera_controls_test.dart test/widget_test.dart --name 'retake restores guide mode and captured bytes unchanged\|home banner asset loads and keeps its source aspect ratio' --reporter expanded` | Before correction: **0 passed, 2 failed, 0 skipped**, independently reproducing both Flutter failures |
| `flutter test test/photo_camera_controls_test.dart test/widget_test.dart --name 'retake restores guide mode and captured bytes unchanged\|home banner asset loads and keeps its source aspect ratio\|Settings sections fit a typical portrait screen in order\|Settings scrolls on small screens with enlarged text' --reporter expanded --timeout 30s` | **Three consecutive runs: 4 passed, 0 failed, 0 skipped each** |
| `flutter test --reporter expanded` | **156 passed, 0 failed, 0 skipped** |
| `flutter analyze` | **21 infos, 0 warnings, 0 errors**, exit **1**; evaluated SDK-deprecation exception described above |
| `dart format --output=none --set-exit-if-changed lib test` | **39 files, 0 changed**, exit 0 |
| `flutter build apk --debug` | **Passed**, 303.8 s; native Android/Kotlin compilation completed, no device installation |
| In `mobile/android/`, process-local `JAVA_HOME` set to Android Studio's JBR, then `.\gradlew.bat --version` and `.\gradlew.bat :app:buildEnvironment --console=plain` | **Passed**; Gradle 9.3.1 / Java 25.0.4 verified, build-environment task successful |

An initial test-selection command used `--plain-name` with a regex alternation and selected no tests; it exited 1 and was corrected to `--name`. This was a command-selection error, not a regression result. Initial synchronization probes were limited to disposable fixtures; no real captures or library data were used.

Debug output: `mobile/build/app/outputs/flutter-apk/app-debug.apk`, **180,865,703 bytes**, SHA-256 **`c1a636e5cf9e98a08553f95272c5cf259b1957c5c9d9be0d1ded475ce4068f36`**. Android Build Tools `aapt dump badging` confirms `com.bookledger.mobile`, version name **1.1.0**, version code **2**, launchable `com.bookledger.mobile.MainActivity` and `application-debuggable`. This is a local debug artifact, not a published release or proof of production signer continuity.

The automated baseline is suitable for code review and native acceptance with the explicitly classified Tcl/Tk skips and SDK deprecations. It does not establish complete native visual/theme/accessibility acceptance, frozen Windows runtime behavior or production-signed Android upgrade/data preservation. Historical intermittent mobile-connection failures did not recur in this full desktop run; their root cause remains unproven. Real installation is still unimplemented. Final Git remains on the same HEAD with all implementation/stabilization changes unstaged, no staged changes and no commits, pushes, issue changes, releases or device installation.

## Explicit update discovery — November 20, 2026

Baseline: clean `main` at `255d59ed4cd002da2d928c5f91d659003fe5c40b`, matching the local `origin/main` reference. Desktop and Android now have explicit stable-release discovery, platform-asset validation, version/notes dialogs and unsupported-development-build handling. The desktop action is a keyboard-accessible status-row hyperlink; Android's action is directly below Clear Data. No startup check, download, installer, application-file replacement, version bump or production-data change was performed. [The update system design](docs/UPDATE_SYSTEM.md) documents installation proposals and a read-only ZIP inspection prototype.

### Changed files

| Files | Purpose |
| --- | --- |
| `src/bookledger/services/updates.py`, `src/bookledger/ui/updates.py`, `src/bookledger/app.py` | Stable release discovery, desktop hyperlink and nonblocking dialog |
| `src/bookledger/services/update_archive.py` | Read-only checksum/path/layout prototype |
| `mobile/lib/updates/update_service.dart`, `mobile/lib/updates/update_check_action.dart`, `mobile/lib/settings/mobile_app_settings.dart`, `mobile/lib/settings/settings_screen.dart`, `mobile/android/app/src/main/kotlin/com/bookledger/mobile/MainActivity.kt` | Android discovery/dialog/placement, installed-build metadata and allowlisted release-page opening |
| `tests/test_updates.py`, `tests/test_update_archive.py`, `tests/test_app_callbacks.py` | Desktop service, UI, archive and minimum-shell regressions |
| `mobile/test/update_service_test.dart`, `mobile/test/update_check_action_test.dart`, `mobile/test/widget_test.dart` | Android service/UI/data-preservation fixtures and Settings placement |
| `README.md`, `mobile/README.md`, `docs/ARCHITECTURE.md`, `docs/PRIVACY_NOTICE.md`, `docs/UPDATE_SYSTEM.md`, `PROGRESS.md`, `TEST_REPORT.md` | Current-source behavior, network disclosure, installation proposal and verification limits |

### Automated checks

- `.venv\Scripts\python.exe -m pytest tests/test_updates.py tests/test_update_archive.py -q -rs`: **47 passed, 0 skipped, 0 failed** after the ZIP fixture correction. The final focused command added `tests/test_app_callbacks.py::test_sidebar_footer_fits_with_all_navigation_buttons_at_minimum_window_size`: **47 passed, 1 skipped, 0 failed** in 1.97 seconds. A new dialog test skipped because Tcl/Tk initialization could not load `icons.tcl`; the minimum-window shell test passed, including link containment and non-overlap with a long status. A broader focused run including all `tests/test_app_callbacks.py` had **114 passed, 2 skipped, 0 failed** in 3.88 seconds. Tcl/Tk initialization is inconsistent across runs; a passing run does not resolve the missing-library environment.
- `.venv\Scripts\python.exe -m pytest -q -rs`: final run **648 passed, 19 skipped, 1 failed** in 62.20 seconds. `test_form_minimum_size_keeps_scrollable_content_reachable` still fails at `798 > 798`. Skips cite incomplete Tcl/Tk libraries or display initialization. Earlier full runs were **634 passed, 19 skipped, 1 failed** in 65.60 seconds before the archive tests (the same form assertion), and **649 passed, 18 skipped, 1 failed** in 48.94 seconds after prototype integration (the fake shell root lacked the new update callback). That harness regression was fixed by supplying the callback stub; the final shell test passes. The form assertion was not changed. Mobile-connection assertions passed in the final run; historical intermittent failures remain unresolved.
- From `mobile/`, `flutter test test/update_service_test.dart test/update_check_action_test.dart --reporter expanded`: **30 passed, 0 skipped, 0 failed**. The final full suite also passes all update tests, including numeric/prerelease ordering beyond native integer range. Tests cover stable-only flags/tags, no downgrades, missing/duplicate/untrusted assets, malformed responses, network/rate-limit/timeout failures, no startup request, UI busy/error/retry/disposal and read-only preference/capture behavior. The Settings placement assertions pass in the full suite. Mocked services/platform channels establish behavior under those fixtures, not Android installation or signer compatibility.
- From `mobile/`, `flutter test --reporter expanded`: final **155 passed, 0 skipped, 1 failed**. `retake restores guide mode and captured bytes unchanged` fails during existing fixture teardown at `test/photo_camera_controls_test.dart:169`: Windows `PathAccessException`, errno 32, deleting a temporary directory with an open file. The earlier full run had **154 passed, 0 skipped, 2 failed**; it also failed `home banner asset loads and keeps its source aspect ratio` with expected ratio `3.0` versus `Infinity` from zero height. Both failures reproduced in isolated reruns; the banner test passed in the final full run and remains intermittent. Camera/home production code and these assertions were not changed; no root-cause fix is claimed.
- From `mobile/`, `flutter analyze`: exits **1**, with **21 informational Material import deprecations**, no warnings or errors under Flutter 3.50.0 / Dart 3.14.0. Nineteen are in existing files and two in the new UI/test imports, which follow the repository's Material convention. New control-flow lint findings were corrected. Migrating the whole application to the SDK's replacement Material package is outside this change.
- From `mobile/`, `dart format --output=none --set-exit-if-changed lib test`: final **39 files, 0 changed**, exit **0**, after formatting the new regression assertions.
- From `mobile/`, `flutter build apk --debug`: **failed before native source compilation**. Installed Flutter requires Android Gradle Plugin **9.1.1 or newer**; the repository pins **9.1.0**. It also warns that Gradle **9.3.1** should move to **9.5**. Build dependencies and validation were not bypassed or changed. Native Kotlin compilation, a current APK and physical Android UI/upgrade acceptance remain unverified.
- `.venv\Scripts\python.exe -m compileall -q src tests` and `git diff --check`: **passed**. Git emits configured LF-to-CRLF notices only.

Synthetic archive tests verify SHA-256 matching, portable/fallback structure, traversal/absolute/Windows ambiguous paths, protected files, duplicate paths, symlinks and size limits without extraction. Disposable sentinels and mocked platform calls check that discovery does not write library/configuration/capture files or call preference/clear/pairing operations. These checks do not prove safe staging, helper activation, rollback, Windows lock handoff or Android installation.

### Live discovery and remaining acceptance

Read-only GitHub release metadata was inspected on November 20, 2026. Both implemented clients contacted the official endpoint and returned installed/available `1.1.0`, **4,542 characters** of notes and **Unsupported Update** in their actual development context. The stable v1.1.0 release advertises both expected Windows ZIPs, the Android APK and `SHA256SUMS.txt`. Release archives/APKs were not downloaded or installed; no newer live release exists in this check, so Update Available is demonstrated with deterministic fixtures.

Native visual/theme/accessibility acceptance, frozen one-file/fallback discovery and production-signed Android checks remain pending. The helper/installer design explicitly gates file ownership, signing trust, update protocol versions, clean shutdown/locks, rollback and schema migration. Real updating remains unimplemented. Issue #22 is not complete, and no issue, commit, push, tag, release or published artifact was changed. Final source changes remain unstaged on the same `main` HEAD; unrelated generated plugin-order changes were removed.

## Provider defaults and candidate feasibility — November 20, 2026

Baseline: clean `main` at `5fe714fc36e6fee2c4ddc4301da1b608e98b754c`, matching the local `origin/main` reference. Hardcover is now enabled before Booktopia in fresh/default configurations. Bigbook remains disabled and available for manual activation. Explicit saved ordering and enabled states are preserved. The existing missing-token guard makes no network request and permits later-provider fallback; the regression checks its authentication diagnostic and Booktopia completion. Provider authentication, schemas and persistence were not redesigned.

- `.venv\Scripts\python.exe -m pytest tests/test_provider_settings.py tests/test_archive_org.py tests/test_booktopia.py tests/test_metadata.py tests/test_hardcover.py tests/test_provider_diagnostic.py tests/test_intake_ui.py -q -rs`: **223 passed, 17 skipped, 0 failed** in 15.25 seconds. Skips cite missing Tcl/Tk files or unavailable initialization. Coverage includes fresh defaults, configurations without provider preferences, preserved customized settings/configuration bytes, missing-token no-network behavior, chain fallback, aggregation, diagnostics and default provider status rows.
- `.venv\Scripts\python.exe -m pytest -q -rs`: **601 passed, 19 skipped, 1 failed** in 54.25 seconds. `test_form_minimum_size_keeps_scrollable_content_reachable` again failed because body and viewport heights were both 798, making `798 > 798` false. The mobile connection assertions passed in this run; their earlier intermittent failures remain unresolved. Tcl/Tk failures account for the skips. No assertion was weakened or failure suppressed, and this run does not establish that intermittent failures are fixed.
- `.venv\Scripts\python.exe -m compileall -q src tests` and `git diff --check`: **passed**. Git emitted configured LF-to-CRLF notices only.
- Official ISBNdb, Goodreads and OCLC documentation was reviewed for [candidate feasibility](docs/METADATA_PROVIDER_FEASIBILITY.md). No candidate catalog API requests, subscriptions, trial activations, purchases or new credentials were used. Public documentation and OpenAPI access do not establish live metadata coverage or latency. ISBNdb's browser-readable terms impose retention/deletion conditions; Goodreads has no established obtainable public developer route; OCLC eligibility and reuse restrictions block a general independent-user catalog integration.

Issue #2 was inspected and remains open for review and disposition of all three candidates. No issue-description change, completion comment or closure was performed. Native Windows acceptance of the defaults/diagnostic presentation was not performed; automated checks and prior live provider samples have narrower scope.

## Metadata provider compatibility — November 20, 2026

Baseline: clean `main` at `780798f3442dc3ea3008c9a93cc3ebc305006156`, matching the local `origin/main` reference. Existing description shortening is integrated. This reassessment used public bibliographic identifiers, existing local credentials loaded through `AppConfigStore`, and read-only HTTPS requests. No library database, inventory, backups, provider order, enablement, or credentials were changed. The root configuration bytes were checked before and after the bounded sample run and were unchanged; the profile fallback was absent. Credential values and raw exception bodies are excluded from this report.

### Contract findings

The [official Hardcover documentation repository](https://github.com/hardcoverapp/hardcover-docs/tree/d9439f56e9eccca6d4589fb6897068b12bc3d045) was inspected at `d9439f56e9eccca6d4589fb6897068b12bc3d045`. Its [GraphQL schema](https://github.com/hardcoverapp/hardcover-docs/blob/d9439f56e9eccca6d4589fb6897068b12bc3d045/schema.graphql) and successful authenticated live introspection show that `books.author_names`, `books.genres`, and `editions.description` are absent. Older rendered schema pages still list those fields, so they were not used as the current contract.

The query now requests edition/book contributions with author names, book description, and `book.cached_tags`. Only explicit `Author` contributions populate Author, preferring edition credits and falling back to work credits. Only the `Genre` category supplies Genre; mood and general tags do not. Genre still must satisfy the catalog's approved list. Edition title takes precedence over work title. Publisher, release fields, edition information/format, and pages use supported fields; missing fields remain optional. Both ISBN forms are queried, and unrelated returned identifiers remain rejected.

The [current getting-started source](https://github.com/hardcoverapp/hardcover-docs/blob/d9439f56e9eccca6d4589fb6897068b12bc3d045/src/content/docs/api/Getting-Started.mdx) describes PAT permissions and user-selected expiration introduced after the legacy token system. Its capability map lists catalog read scopes for editions, books, contributions, authors, and publishers; no write scope is needed by this adapter. Actual least-privilege-token enforcement was not live-tested. Legacy tokens can have access equivalent to `all`; the former fixed January 1 expiry description should not be applied to every current PAT. Bearer authentication succeeded; the separate bare-token probe returned HTTP 400. Saved credentials may contain either a bare token or a Bearer prefix; requests now send exactly one prefix. HTTP and GraphQL failures retain sanitized classifications. The current free plan documents 5,000 daily requests, 60 per minute, and burst capacity 10. Each top-level alias counts toward quota; the two ISBN selections cost two units per lookup. Live rate headers agreed with those limits. The old rendered maximum-depth statement was not assumed to apply: the corrected query with nested contributions was accepted live.

[Hardcover's OAuth guidance](https://github.com/hardcoverapp/hardcover-docs/blob/d9439f56e9eccca6d4589fb6897068b12bc3d045/src/content/docs/api/OAuth.mdx) recommends OAuth for applications used by others. PAT entry remains suitable for a personal tool but is not the recommended long-term distributed-app sign-in design. A separately scoped OAuth/PKCE implementation and appropriate token storage should be assessed before promoting Hardcover as a default provider. No OAuth implementation or credential migration was performed. Only public catalog metadata was requested; no user-library or account mutations were attempted.

[BigBook's official documentation](https://bigbookapi.com/docs/) confirms `GET /search-books?isbn=...`, nested `books` groups, `GET /{id}`, and `x-api-key` authentication. Live responses agreed. The detail sample supplies title, authors, description, numeric publication year and page count. Publisher, edition, genre, and SRP are not inferred. The documented/live sample puts ISBN-10 `0439139597` in both ISBN fields; ISBN equivalence still verifies it for `9780439139595`. This is not evidence that other editions can be accepted without matching identifiers. Missing or malformed `books` arrays now produce an invalid-response failure rather than a confirmed miss. Transport errors from both adapters are sanitized, including exception messages that contain credentials.

BigBook documents daily quotas, free-plan throughput of 60 requests per minute, HTTP 402 for exhausted daily allocation, and HTTP 429 for rate limiting. Quota headers were observed on every successful sample response. The tested account began with 50 daily units and ended with 41; this is an observed account allocation, not a promise about every plan. Search and detail calls continue to share one five-second provider budget. No live retries or automatic backoff were used.

### Bounded live requests

Hardcover: ten POST requests total to `https://api.hardcover.app/v1/graphql`. No tokens were included in the URL or GraphQL variables.

| Request | Selection/input | Observed outcome | Total duration |
| --- | --- | --- | --- |
| 1 | Introspection of edition, book, and contribution field names | Bearer accepted; HTTP 200, no GraphQL errors | 0.964 s |
| 2 | Original adapter, `9780547928227` | Lookup failed, provider classification; HTTP status was not captured for this baseline call | 0.793 s |
| 3 | Corrected contract probe, `9780547928227`, one edition plus public credits/tags | HTTP 200; verified ISBN and supported fields | 0.825 s |
| 4 | Bare-token comparison, edition ID 0 with limit 1 | HTTP 400; no account records requested | 0.835 s |
| 5 | Repaired adapter, fiction `9780547928227` | HTTP 200; title, author, ISBN, genre, publisher, year, edition, pages, description | 1.105 s |
| 6 | Repaired adapter, nonfiction `9780062316097` | HTTP 200; same nine fields | 1.026 s |
| 7 | Repaired adapter, academic `9780306406157` | HTTP 200; same fields except genre | 0.873 s |
| 8 | Repaired adapter, equivalent ISBN-10 `054792822X` | HTTP 200; same nine fields as fiction ISBN-13 | 1.056 s |
| 9 | Repaired adapter, synthetic `9780000000002` | HTTP 200; unexpectedly matched a sparse record: title, author, ISBN, genre, year | 0.833 s |
| 10 | Synthetic `9799999999990`, direct edition ISBN-13 selection | HTTP 200; empty edition list, no GraphQL errors | 0.790 s |

Requests 5–9 used the adapter's `byIsbn13` and `byIsbn10` selections with the entered ISBN and its valid equivalent. Every retrieved adapter result passed identifier verification. The synthetic ISBN in request 9 is not a reliable no-result fixture: the service actually contains a record for it. Request 10 establishes an empty live result; it does not establish that every synthetic identifier will be absent.

BigBook: nine GET requests total to `https://api.bigbookapi.com`, all with `x-api-key` authentication and no key in the URL.

| Request | Path/input | Observed outcome | Total duration |
| --- | --- | --- | --- |
| 1 | `/search-books?isbn=9780547928227` | HTTP 200, empty books | 1.147 s |
| 2 | `/search-books?isbn=9780062316097` | HTTP 200, empty books | 0.593 s |
| 3 | `/search-books?isbn=9780306406157` | HTTP 200, empty books | 0.578 s |
| 4 | ISBN-10 input `054792822X`, normalized request `/search-books?isbn=9780547928227` | HTTP 200, empty books | 0.240 s |
| 5 | `/search-books?isbn=9780000000002` | HTTP 200, empty books | 0.641 s |
| 6 | `/16384516`, the official documentation example | HTTP 200, title, authors, description, year, pages, equivalent ISBN-10 | 0.680 s |
| 7 | `/search-books?isbn=9780439139595` | HTTP 200, nested group containing ID 16384516 | 0.795 s |
| 8–9 | Complete adapter lookup for `9780439139595`: same search followed by `/16384516` | Both HTTP 200; Retrieved with verified ISBN and six mapped fields | 0.900 s total; response-opening times 0.667/0.232 s |

Empty searches establish limited coverage for these exact identifiers at this time, not a confirmed endpoint defect. The successful documentation example establishes live search/detail compatibility and ISBN equivalence. Live edition mismatch was not deliberately induced; rejection of unrelated editions, credential failures, quota/rate-limit errors, and network failures were tested with deterministic fixtures. No invalid credentials were sent to either live service.

### Recommendations and automated verification

- Hardcover: retain available for manual enabling, disabled by default. The query repair passed bounded live validation. Coverage, scoped-PAT enforcement, future schema changes, and distributed-app authentication still need attention; assess OAuth separately before wider promotion.
- BigBook: retain available for manual enabling, disabled by default. Authentication and one complete ISBN lookup worked, but coverage was sparse in the representative sample and each successful search may require additional quota for details.
- `.venv\Scripts\python.exe -m pytest tests/test_hardcover.py tests/test_bigbook.py tests/test_metadata.py tests/test_provider_settings.py -q`: **80 passed** before the additional regression cases.
- `.venv\Scripts\python.exe -m pytest tests/test_hardcover.py tests/test_bigbook.py tests/test_metadata.py tests/test_provider_settings.py tests/test_provider_diagnostic.py tests/test_intake_ui.py -q -rs`: **167 passed, 17 skipped, 0 failed**. Skips cite incomplete Tcl/Tk files or unavailable display initialization. Automated checks cover both ISBN forms, verified/mismatched editions, explicit author roles, optional fields, malformed responses, HTTP 401/402/403/429/500/503, GraphQL errors over HTTP 200, credential redaction, network/timeout failures, a shrinking five-second detail budget, chain fallback/precedence, diagnostics, manual-value preservation, and default-disabled settings.
- First `.venv\Scripts\python.exe -m pytest -q -rs`: **598 passed, 19 skipped, 1 failed** in 60.96 seconds. The failure was `tests/test_mobile_connection.py::test_pairing_consumes_expiring_credential_and_authenticates_device`: HTTP 200 was received but the immediate `connected` assertion was false. That test passed on an isolated rerun (**1 passed** in 0.51 seconds). The unchanged connection handler writes the response before recording connection confirmation, which permits a timing race with that assertion. This is an explanation supported by the ordering, not a completed mobile fix. The skips cite Tcl/Tk initialization or missing files. The prior minimum-window geometry failure did not recur.
- Confirmation `.venv\Scripts\python.exe -m pytest -q -rs`: **597 passed, 19 skipped, 2 failed** in 57.86 seconds. The minimum-window geometry check recurred (`798 > 798` was false), and `tests/test_mobile_connection.py::test_connection_confirmation_expires_recovers_and_is_cleared_by_unpair` failed an immediate `connected` assertion after HTTP 200. Neither the form geometry nor mobile connection implementation/tests were changed. Provider regressions remained passing; the full suite is not green. These failures remain unresolved and were not suppressed or repaired as part of the provider changes.
- `.venv\Scripts\python.exe -m compileall -q src tests` and `git diff --check`: **passed**. Git emitted configured LF-to-CRLF notices only.

Native Windows acceptance of Settings and diagnostics was not performed. Mocked success and error fixtures do not establish live service availability beyond the requests recorded above.

## Android release-readiness audit - November 17, 2026

Baseline: clean `main` at `b50d2cfb900f593779d693dc11accd7b4d88afaa`, matching `origin/main`. The audit report is `docs/ANDROID_RELEASE_READINESS_AUDIT.md`; this entry records new runs without replacing earlier results.

- `flutter test --reporter expanded`: **126 passed, 0 failed, 0 skipped** across 12 test files. The suite covers ISBN validation and scanning callbacks, manual/no-ISBN capture, photo correction and Retake, Queue insertion and capacity, early completion, mocked transfer/reconnection/retry, camera controls, Settings, Clear Data, and layout.
- `flutter analyze`: **no issues**.
- `dart format --output=none --set-exit-if-changed lib test`: **35 files checked, 0 changed**.
- `flutter build apk --debug`: **succeeded**. Gradle reported a JDK restricted-native-access warning; dependency resolution reported 19 newer package versions incompatible with current constraints. No packages were upgraded.
- `.venv\Scripts\python.exe -m pytest -q`: **516 passed, 19 skipped, 0 failed**. The skips concern Tk/display-dependent tests in this environment; they are not Android test skips.
- `git diff --check`: **passed** on the final documentation diff; Git reported only its configured LF-to-CRLF notice for `THIRD_PARTY_NOTICES.md`.

On a Xiaomi/Poco 23122PCD1G running Android 16 (API 36), the built debug APK was installed as a fresh install after the phone accepted its install prompt; no app data was cleared. Cold first launch (6.29 seconds), warm resume (0.27 seconds), and cold launch after force-stop with Camera permission granted (5.93 seconds) reached a responsive home screen. A second background/foreground resume while the photo camera was active returned to a working preview with Torch off. Bounded logcat searches and visible observation found no BookLedger ANR; the earlier ANR cause remains unknown.

Disposable physical checks passed for initial Scan/Manual/No ISBN choices, No ISBN photo capture without Save, disabled Send while unpaired, photo-preserving Cancel Change and Manual correction, canceled Retake, successful Retake replacement (old app-private photo removed), camera Guide/Zoom persistence across force-stop, and Torch reset after backgrounding. Bulk capacity 5: Queue reached 1/5 and opened the scanner, scanner X retained the queued entry, a hold outside the scanner made Send appear without sending, and a separate five-photo batch progressed to 5/5 with no sixth scanner. Test captures were removed through normal app navigation and app-private cache inspection; the debug APK remains installed. A real barcode scan, capacity 20 physical run, authenticated reconnect, transfer and desktop acknowledgment, production-signed upgrade, and fresh release build were **not performed** in this audit.

## Android Issue #16 - November 17, 2026

Revised intake uses identifier selection, photography, then explicit Send/Queue without Save. Tests cover immediate readiness, correction/Retake preservation, stale camera-session rejection, next-scan progression, capacity/early finish, reconnect and failed-transfer retry, small-screen layout, camera controls and Settings.

Physical Android 16 checks: debug APK installed; initial 2x2 layout inspected; No ISBN opened the camera; test photograph captured; manual ISBN correction retained it; canceled Retake restored it; Bulk Queue advanced to the next scanner (1/5); scanner cancellation retained the queue; hold Queue produced Send for the partial batch. No inventory was transferred. Initial launches displayed Android input-focus ANR dialogs; after dismissal and granting Camera permission the intake screens responded. The startup warning has not been isolated. Full-capacity progression, real barcode detection, permission denial, saved-preference restart, and authenticated reconnect/transfer remain unverified on hardware. The debug APK remains installed for further testing.

Automated results: `flutter test` - 124 passed, 0 failed, 0 skipped. `flutter analyze` - no issues. `dart format --output=none --set-exit-if-changed lib test` - 35 files, 0 changed. `flutter build apk --debug` succeeded; Gradle warned about restricted `System.load` native access, and dependency resolution reported 19 newer incompatible versions (no dependency changes made). `git diff --check` passed. No desktop code changed; desktop tests were not rerun. Camera-failure recovery and readable identifier-choice controls were included in the final APK rebuild; the final APK was installed without uninstalling or clearing app data.

# Test report history

Record started: 2026-10-19; latest dated entry: 2026-11-20.

This is a record of specific test runs, investigations, and reported physical tests, not a current comprehensive validation certificate. Results and limitations apply to the dates and environments recorded in each section. The 2026-11-15 Milestone 5 source-level run did not establish clean-machine Windows compatibility or physical Android end-to-end transfer/cataloging; a separate reported final-asset session on 2026-11-16 is recorded below.

## Optional bibliographic Subtitle support (2026-11-17)

Schema v12 adds nullable `book_records.subtitle`; the sequential v11 migration does not rewrite existing titles or copy/sales rows. Add/Edit accepts and clears Subtitle independently. Catalog search includes Subtitle, Catalog displays `Title: Subtitle` only below 60 characters and otherwise displays main Title, Inventory always combines them, and Book Details separates them. ISBN providers retain their existing full-title/empty-field behavior, posters continue to use main Title, and Android code is unchanged. No-ISBN duplicate detection remains exact main Title plus Author, so legacy rows with subtitle text embedded in Title may not automatically match a newly separated pair.

Migration, persistence, title formatting/threshold, search, Inventory and Details display, provider handling, poster binding, mobile-originated intake, and backup/restore tests were added or updated. Disposable databases and backup archives were used; no actual library records were modified.

- `.venv\Scripts\python.exe -m pytest tests\test_catalog.py tests\test_catalog_card_text.py tests\test_app_callbacks.py tests\test_intake_ui.py tests\test_posters.py tests\test_uuid_backup_restore.py tests\test_mobile_incoming.py -q -rs --basetemp=.pytest-tmp-issue15-focused-recheck` — **208 passed, 2 skipped**. Skips were Tcl/Tk-dependent geometry tests.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-issue15-final-suite` — **516 passed, 18 skipped, 1 failed**. The single failure was `test_connection_confirmation_expires_recovers_and_is_cleared_by_unpair`, which observed `connected == False` after its authenticated request; the same test passed when rerun alone (**1 passed**). A second full-suite run reproduced that one timing-sensitive failure. The Issue #15 focused tests passed.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed. `git diff --check` — passed; Git emitted only configured LF-to-CRLF notices.

Tk tests that skipped could not load local Tcl/Tk files. The failed mobile-connection test does not exercise changed Issue #15 modules; it remains an unresolved full-suite warning rather than being represented as a pass.

The first combined focused run also exposed two form-window size assertions that depended on Tk applying a resize before measurement. They passed when rerun alone; the form test now processes the requested geometry update before asserting, and the final focused run passed.

## Catalog performance investigation (2026-11-17)

Synthetic libraries were created in disposable temporary directories at 20, 100, 500, and 1,000 copies. They used varied titles, authors, genres, statuses, prices, locations, and optional metadata, plus a representative 1,200 × 1,800 JPEG cover. Database query timings are medians of five calls; sort timings are medians of seven calls through 500 rows and one call at 1,000 rows; image timings include opening, RGB conversion, thumbnail resizing, and Sold tinting. The same generated JPEG was reused per row to make the repeated image-processing cost comparable. The image benchmark used three-run medians through 500 rows and one run at 1,000 rows because of runtime. The OS file cache was warm during the repeated image runs; cold disk startup was not isolated, and the application has no thumbnail cache.

| Copies | Full query median | Filtered query median | Sort | Image baseline | Image optimized |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | 0.93 ms | 0.86 ms | 0.01 ms | 283.22 ms | 219.31 ms |
| 100 | 1.71 ms | 1.55 ms | 0.03 ms | 1,392.77 ms | 1,110.66 ms |
| 500 | 6.36 ms | 4.59 ms | 0.13 ms | 6,965.84 ms | 5,468.12 ms |
| 1,000 | 11.58 ms | Not measured | 0.42 ms | 13,376.46 ms | 11,182.95 ms |

The dominant measured separable stage was repeated image processing. The app retrieves records once per population and sorts them in memory; no N+1 query path was found. Reusing a loaded RGB image for the resize avoids an extra full-resolution RGB copy while preserving full-resolution sampling. Exact pixel comparisons against the prior processing sequence passed for synthetic RGB JPEG and RGBA PNG covers, including Sold tinting. A faster JPEG draft-resize alternative was rejected after visual inspection showed fine-detail artifacts.

No thumbnail cache, background worker, pagination, or virtualization was added: these add invalidation, memory, or interaction complexity, and the measured full-resolution resize change improves the image stage by about 16–23%. Actual widget construction, complete refresh/navigation timing, scrolling responsiveness, and process memory were not measured. The local Tcl/Tk installation lacks required ttk theme files, so full visual card validation remains unverified.

- `.venv\Scripts\python.exe -m pytest tests\test_catalog.py tests\test_catalog_card_text.py tests\test_app_callbacks.py -q -rs --basetemp=.pytest-tmp-issue11-catalog-final` — **138 passed, 1 skipped**. The skipped Tk geometry test could not load Tcl/Tk files.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-issue11-full` — **507 passed, 18 skipped**. Tk UI tests skipped because the installed Tcl/Tk distribution is missing required files, including ttk theme assets.
- The two added thumbnail pixel-preservation cases are included in the focused and full-suite totals.

## Initial final-asset physical smoke session (reported, 2026-11-16)

This physical session was reported using the exact final Windows ZIP and Android APK after the assets had been verified. The tests were not independently observed. No errors were reported. The Windows device was described as a Windows 11 laptop; device model, Windows build, Android model/OS, and whether Android installation was fresh or an upgrade were not supplied.

| # | Result | Reported scenario |
| ---: | --- | --- |
| 1 | PASS | Windows ZIP size and SHA-256 matched. |
| 2 | PASS | Fresh Windows extraction and launch without Python. |
| 3 | PASS | Desktop version, navigation, Settings, About, and theme selection. |
| 4 | PASS | Disposable book add, edit, search, and photo handling. |
| 5 | PASS | Exact Android APK verified and installed/upgraded; fresh-install versus upgrade was not specified. |
| 6 | PASS | Android version and camera permissions. |
| 7 | PASS | ISBN scanning, manual ISBN entry, and No ISBN. |
| 8 | PASS | Photo capture and preview. |
| 9 | PASS | Single Entry and Bulk Entry workflows. |
| 10 | PASS | QR and manual pairing. |
| 11 | PASS | Single Entry transfer with ISBN and photo. |
| 12 | PASS | Bulk Entry transfer. |
| 13 | PASS | Desktop cataloging and duplicate handling. |
| 14 | SKIPPED | Backup and persistence after restart. This was deliberately omitted from the final session; prior testing was reported. |
| 15 | SKIPPED | Automatic reconnection after restart. This was deliberately omitted from the final session; prior testing was reported. |

**Session total: 13 PASS, 2 SKIPPED, 0 FAIL.** These two scenarios were deliberately omitted from this session and are retained as SKIPPED in its historical record. Earlier testing of both scenarios was reported. No device-specific details or install-versus-upgrade distinction have been inferred for this session.

## Follow-up of previously skipped scenarios (reported, 2026-11-16)

Both scenarios that were skipped in the session above were subsequently reported as rerun:

| Scenario | Result | Reported outcome |
| --- | --- | --- |
| Windows backup and persistence after restart | PASS | The previously skipped physical smoke scenario passed in the follow-up round. |
| Android/desktop automatic reconnection after restart | PASS | The previously skipped physical smoke scenario passed in the follow-up round. |

The latest aggregate across the 15 scenarios was reported as **15 PASS, 0 FAIL, 0 SKIPPED**. This cumulative status combines the original session's 13 reported passes with these two subsequently reported passes; it does not change the original session's 13 PASS / 2 SKIPPED record. Neither physical test round was independently observed for this report. The follow-up clarification does not specify whether these two reruns used the exact final release assets, and supplies no additional device or OS details.

## Configurable metadata provider registry

Implementation adds a central provider registry and a versioned root `config.json` for enabled states and lookup priority, with a per-user fallback when the portable root is read-only. Settings includes functional drag reordering and Restore Defaults. Lookup stops when title, author, genre, publisher, and publication year are available; edition, format, synopsis, and page count are optional enrichment. Google Books credentials remain in their existing separate file. Inventory Purge preserves provider configuration.

- `.venv\Scripts\python.exe -m pytest tests\test_provider_settings.py tests\test_metadata.py tests\test_booktopia.py tests\test_portable_lifecycle.py -q --basetemp=.pytest-tmp-provider-focused-final` — **91 passed**.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-provider-full-final` — **170 passed, 2 skipped**. Tk could not initialize because required Tcl/Tk files are missing; Settings drag/drop was not runtime-tested.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git reported configured LF-to-CRLF notices only.

## Direct ISBN fallback follow-up

- `.venv\Scripts\python.exe -m pytest tests/test_booktopia.py -q --basetemp=.pytest-tmp-direct-isbn-focused-final2` — **36 passed**.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-direct-isbn-full-final2` — **160 passed, 1 skipped**. The skipped Tk UI test could not initialize Tcl/Tk in this environment.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git emitted configured LF-to-CRLF notices only.

The `9780553290998` direct-fallback test uses synthetic HTML with a supplied ISBN, title, and author; its synopsis text is explicitly synthetic and no live response was captured. The test simulates the search HTTP error followed by the direct ISBN request resolving to the reported canonical URL. Previously reported browser observations remain the only live evidence for this listing; no live request for it was made in this environment. A live recheck of both the search and canonical URLs for `9780716736387` failed at DNS resolution (`[Errno 11001] getaddrinfo failed`), so the response code, redirect path, and error-body content remain unverified.

## Booktopia unavailable HTTP-response follow-up

- `.venv\Scripts\python.exe -m pytest tests/test_booktopia.py -q --basetemp=.pytest-tmp-booktopia-http-body-focused` — **33 passed**.
- `.venv\Scripts\python.exe -m pytest` — **97 passed, 61 setup errors** because pytest could not create `tmp_path` directories under the sandbox's AppData temp path.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-unavailable-listing-full` — **157 passed, 1 skipped**. The skipped Tk UI test could not load the installed Tcl/Tk `ttk/spinbox.tcl` file.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git emitted configured LF-to-CRLF notices only.

Live requests to the ISBN `9780716736387` search and canonical product URLs failed with `URLError: [Errno 11001] getaddrinfo failed`; the available web view also could not open either URL. Therefore the live HTTP status, redirect chain, and presence of a usable error response body remain unknown. The parser tests use only synthetic fixtures. The unavailable-product fixture now uses a generic synthetic ISBN and does not claim to represent the observed listing.

## Latest synopsis-policy changes

- `.venv\Scripts\python.exe -m pytest tests/test_booktopia.py tests/test_metadata.py -q --basetemp=.pytest-tmp-synopsis-policy-focused-final3` — **64 passed**.
- `.venv\Scripts\python.exe -m pytest tests/test_intake_ui.py -q -rs --basetemp=.pytest-tmp-synopsis-policy-intake-final2` — **18 passed, no skips**.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-synopsis-policy-full-final2` — **155 passed, no skips** in 19.27s.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git emitted only configured LF-to-CRLF notices.

## Coverage and behavior

Open Library tests confirm title, author, publisher, publication year, and page count remain available while edition descriptions, notes, excerpts, and linked-work descriptions never populate Book Details/Synopsis. The linked-work API request is no longer made solely to retrieve a synopsis. ISBN `9780716736387` has a deterministic regression for the observed bibliographic notes.

Booktopia tests use mocked responses and synthetic HTML fixtures, not captured site responses. They verify explicit tab-to-panel relationships, rejection of a tab ID without a relationship, panel text taking precedence over structured bibliographic notes, filtering author/review/recommendation sections, rejection of generic meta descriptions and purchase copy in matching Book JSON-LD, safe empty synopsis results, ISBN aliases, matching-product checks, unavailable-product status, and HTTP/network error distinctions. The existing `9780140449136` and `9781923058507` cases use synthetic fixtures to test matching synopsis extraction; their earlier manual GUI checks are separate observations and do not make the fixtures captured responses. The unavailable-product behavior uses a generic synthetic ISBN fixture, not `9780716736387`. No captured Booktopia response for the unavailable `9780716736387` page is available.

The previous Booktopia parser collected unqualified body `itemprop="description"`, schema.org descriptions, and generic `description`/Open Graph metadata, without identifying a Description tab's associated panel. That allowed bibliographic notes and retail SEO text to be treated as Book Details. The revised parser only trusts a panel when the identified tab explicitly references it, or a matching schema.org Book description after filtering recognized note and retail boilerplate patterns. Unassociated `itemprop="description"` and generic meta descriptions are ignored. If no usable synopsis exists, it leaves the field empty. A matching page marked with an explicit unavailability message or structured `OutOfStock`, `Discontinued`, or `SoldOut` state reports `Product unavailable`. For HTTP error responses, the bounded HTML body is parsed only when the final URL is the requested ISBN's canonical product URL; metadata is accepted only with matching page ISBN evidence and supported values. Error pages that do not meet those checks retain their provider-error status.

## Live investigation limits

No raw current Booktopia HTML or sanitized live capture was available in the development environment. The web-rendered indexed text snapshot for [Crime and Punishment, ISBN 9780140449136](https://www.booktopia.com.au/crime-and-punishment-fyodor-dostoyevsky/book/9780140449136.html) (crawled 1.1 years ago) and [The Strength of the Few, ISBN 9781923058507](https://www.booktopia.com.au/the-strength-of-the-few-james-islington/book/9781923058507.html) (crawled two weeks ago) shows substantial text beneath a Description label, but the transformed snapshots do not expose HTML attributes or response timing. They cannot establish whether the text is in the initial HTTP response, a hidden panel, embedded structured data, or a later browser request. The current page for [The Triumph of Evolution, ISBN 9780716736387](https://www.booktopia.com.au/the-triumph-of-evolution-niles-eldredge/book/9780716736387.html) could not be read through the available web view, and direct requests failed DNS resolution. Thus the live response status, redirect chain, and presence or absence of usable error-body HTML remain unverified; the prior synthetic test is no longer presented as evidence about that listing.

The extraction change is **not yet verified against Booktopia's actual live tab-to-panel markup**. The synthetic fixtures prove the relationship-based parser and rejection policy only. Do not treat them as captured evidence or claim that live synopsis extraction is confirmed. A sanitized current response or inspected relationship from a browser is still needed to verify the actual selector and availability signal. If the page structure does not expose a relation supported by the parser, Book Details will remain empty rather than use generic text.

The integration remains best-effort and subject to site changes and access policies. No schema or runtime dependency changes were made. The rest of the suite covers catalog validation, sales and status transitions, backup/restore, portable paths and migration, Trash and photo lifecycle, recovery, verification, callbacks, and intake UI behavior. Manual native-Windows GUI acceptance remains pending.

## Archive.org metadata provider integration

- `.venv\Scripts\python.exe -m pytest -q tests\test_archive_org.py tests\test_provider_settings.py tests\test_provider_diagnostic.py tests\test_metadata.py tests\test_booktopia.py --basetemp=.pytest-tmp-archive --tb=short` — **136 passed, 13 skipped**.
- `.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-archive --tb=short` — **364 passed, 14 skipped, 4 failed**. The failures are existing missing-bundled-logo failures in `test_app_callbacks.py` and `test_resources.py`; `assets/generalists_bookshop_logo.png` is absent from this checkout.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git reports configured LF-to-CRLF notices only.

The Archive.org provider is registered after Google Books and before Booktopia. Fresh settings use that order; a legacy saved order is retained and Archive.org is appended as enabled when absent. The existing registry-driven Metadata Sources priority list and ISBN Lookup Test expose Archive.org. Search requests only identifier, title, creator, publisher, year, edition, and description for up to ten results. Distinct records are kept separate, and ambiguous candidates are checked by item metadata for the requested ISBN (or valid ISBN-10/13 equivalent), up to three records.

The normal `run_bookledger.bat` launcher opened the application. Manual inspection showed Archive.org in the enabled provider list and independent diagnostic selector; an Archive.org diagnostic run reported a provider lookup error and 0.04 seconds because DNS resolution is unavailable. Direct live requests for all four requested ISBNs likewise failed DNS resolution before receiving an Archive.org response. Consequently, no live candidate quality, description, or server timing is confirmed. Mocked tests cover candidate selection, exact ISBN verification, mapping, errors, timeouts, configuration migration, registry order, and diagnostic fields.

## Poster creation implementation

- `.venv\Scripts\python.exe -m pytest --basetemp=.pytest-tmp-poster tests\test_posters.py tests\test_app_callbacks.py tests\test_uuid_backup_restore.py tests\test_portable_lifecycle.py -q -rs --tb=short` — **69 passed, 1 skipped**.
- `.venv\Scripts\python.exe -m pytest --basetemp=.pytest-tmp-poster -q -rs --tb=short` — **319 passed, 13 skipped**. Skips require the complete Tcl/Tk library or a display; this Python environment is missing Tk files such as `ttk/sizegrip.tcl` and `ttk/scrollbar.tcl`.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git emitted configured LF-to-CRLF notices only.

Automated tests cover schema v8 migration, preset persistence and sequencing, shared background cleanup, relative background resolution and fallback storage, title and price formatting, normalized element geometry, PNG export, backup/restore of templates and poster files, read-only application-assets restore fallback, and purge preservation of unrelated files. Visual inspection and a real launcher/UI smoke test were not possible because Tcl/Tk is incomplete in this environment.

## Mobile connectivity completion (2026-11-02)

- `.venv\\Scripts\\python.exe -m pytest tests\\test_mobile_network.py tests\\test_credential_protection.py tests\\test_mobile_connection.py -q` — **32 passed**.
- `.venv\\Scripts\\python.exe -m pytest -q -rs` — **443 passed, 18 skipped**. All skips require the complete Tcl/Tk library; this environment lacks `ttk/sizegrip.tcl`. The four missing bundled-logo failures are resolved by the intended blank-logo behavior.
- `flutter analyze` — passed with no issues.
- `flutter test` — **54 passed**.
- `dart format --output=none --set-exit-if-changed lib test` — **24 files checked, 0 changed**.
- Android `assembleDebug` — **BUILD SUCCESSFUL** with Android Studio JBR, one Gradle worker, Kotlin in-process, and Kotlin incremental compilation disabled.
- `git diff --check` — passed; Git emitted configured LF-to-CRLF notices.

On the Poco X6, the Android secure-storage write/read probe passed. The client initially rejected its own API paths because its allowlist contained escaped prefix text. After that correction, the desktop returned HTTP 400: Dart had sent a chunked JSON body while the Python handler required `Content-Length`. Setting the byte length fixed the request. QR pairing and manual pairing then both completed; the desktop showed the paired device, authenticated reconnect succeeded, the token survived a full app force-stop/relaunch, and connection recovered after desktop restart and Wi-Fi interruption/recovery. Logs report status/phase only and do not include pairing credentials or device tokens.

The desktop DNS-SD service advertised on the tested Wi-Fi network. Changed-IP recovery has automated ordering coverage, but an IP change was not reproduced on the Poco, so Android NSD discovery after an actual DHCP change remains unverified. Windows Mobile Hotspot pairing and multicast discovery were not physically tested. No Windows Firewall rules were modified. The configured shop logo remained visible; the logo file itself was left untouched.

## Milestone 5 mobile transfer and desktop cataloging (2026-11-15)

- Targeted staging/catalog regression run: `.venv\\Scripts\\python.exe -m pytest tests/test_mobile_incoming.py tests/test_catalog.py tests/test_posters.py -q` — **88 passed**.
- Full Python suite: `.venv\\Scripts\\python.exe -m pytest -q` — **449 passed, 18 skipped**. Skips are Tk/UI tests requiring unavailable Tcl/Tk components.
- `flutter analyze` — **no issues**.
- `flutter test` — **59 passed**.
- `dart format --output=none --set-exit-if-changed lib test` — **24 files checked, 0 changed**.
- Android debug APK: Flutter's `build apk` wrapper hit the known Kotlin incremental-cache cross-drive issue; direct Android Studio JBR Gradle `assembleDebug` succeeded with Kotlin in-process, incremental compilation disabled, and one worker.
- `git diff --check` — passed.

Automated tests cover validated and idempotent staging, duplicate/nullable ISBNs, batch ordering and readiness, transfer callbacks, recovery after restart, and preserving the incoming UUID through durable catalog save. Physical Poco X6 end-to-end transfer/cataloging and native Tk UI interaction were not performed in this turn. No transfer retry behavior was tested against a live desktop/device pair.

## Catalog sorting direction toggle (2026-11-17)

- `.venv\Scripts\python.exe -m pytest -q tests/test_app_callbacks.py -k catalog_sort` — **3 passed**.
- `.venv\Scripts\python.exe -m pytest -q tests/test_app_callbacks.py tests/test_catalog.py` — **130 passed, 1 skipped**.
- `.venv\Scripts\python.exe -m pytest -q -rs` — **497 passed, 19 skipped, 1 failed**. The failure is `test_photo_preview_and_manual_metadata_values_are_preserved`, where the Tk photo preview did not resize after a window geometry change; the same assertion reproduced in isolation and was observed during earlier preview testing. Skips require missing Tcl/Tk files, including `init.tcl`, `ttk/utils.tcl`, and `ttk/sizegrip.tcl`.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git reports configured LF-to-CRLF notices only.

Catalog sorting tests cover Title, Copy ID, and Price in both directions, case-insensitive title comparison, numeric keys, explicit Copy ID tie-breaking, empty and single-row inputs, active filter forwarding, re-sorting refreshed records, direction toggling, and sort preference retention across navigation. The incomplete Tcl/Tk runtime prevented visual verification of the arrow control and its tooltip in the running desktop UI.

## Catalog card second-line clipping (Issue #12 follow-up, 2026-11-17)

- `.venv\Scripts\python.exe -m pytest -q -rs tests/test_catalog_card_text.py tests/test_app_callbacks.py tests/test_catalog.py` — **136 passed, 1 skipped**; the skipped pre-existing display test could not load Tcl/Tk `init.tcl`.
- `.venv\Scripts\python.exe -m pytest -q -rs` — **504 passed, 19 skipped**. Two Tk UI tests could not load Tcl/Tk files; 17 provider diagnostic UI tests require `ttk/sizegrip.tcl`.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git reports configured LF-to-CRLF notices only.

The new widget geometry test passed in the focused run. It checks the measured two-line `ttk.Label` request—including descenders—fits the text area and that short and truncated values keep equal text-area and card heights. Full-suite execution later skipped that Tk test because `tk.tcl` was unavailable. In the available Tk runtime, a 17 px line spacing yielded a 34 px two-line frame while the actual two-line label requested 38 px; the card area now uses the active font/theme label's measured request instead of line spacing alone. Full desktop visual inspection remains pending.

## Catalog card text layout (Issue #12, 2026-11-17)

- `.venv\Scripts\python.exe -m pytest -q -rs tests/test_catalog_card_text.py tests/test_app_callbacks.py tests/test_catalog.py` — **136 passed, 1 skipped**. The skipped display test could not load Tcl/Tk `ttk/sizegrip.tcl`.
- `.venv\Scripts\python.exe -m pytest -q -rs` — **505 passed, 18 skipped**. One UI test could not load `init.tcl`; 17 provider diagnostic UI tests require the missing `ttk/sizegrip.tcl`.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git reports configured LF-to-CRLF notices only.

Pure text tests cover one-line, two-line, overflowing, long unbroken, and empty values. A Tk geometry test passed for mixed short and long text, confirming two-line areas and equal overall card heights; database tests confirm complete title and author values remain in Catalog and More Details. A full app visual review was not performed.

## v1.1.0-rc1 candidate preparation (2026-11-17)

Exact artifacts and evidence are recorded in `docs/RELEASE_CANDIDATE_v1.1.0-rc1.md` and `dist/v1.1.0-rc1/evidence/`.

- `.venv\Scripts\python.exe -m pytest tests\test_release_version.py tests\test_portable_packaging.py -q` — **6 passed**.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-rc1-full` — **516 passed, 18 skipped, 1 failed**. `test_photo_preview_and_manual_metadata_values_are_preserved` failed because the preview height did not grow after geometry resize. An isolated rerun also failed at that assertion. No source or assertion was changed. Skips require missing Tcl/Tk display files.
- `.venv\Scripts\python.exe -m pytest tests\test_uuid_backup_restore.py tests\test_catalog.py -q -rs --basetemp=.pytest-tmp-rc1-migration-backup` — **83 passed** on disposable test data.
- `flutter test --reporter expanded` — **126 passed, 0 failed, 0 skipped**.
- `flutter analyze` — **no issues**.
- `dart format --output=none --set-exit-if-changed lib test` — **35 files, 0 changed**.
- `git diff --check` — passed; configured LF-to-CRLF notices only.
- Production-signed APK built and verified against the historical production certificate. Release notices and resolved Android license graph were inspected; see `THIRD_PARTY_NOTICES.md` and the candidate evidence inventory.
- One-file and fallback ZIPs passed integrity and composition checks. Their embedded APK hashes match the standalone APK. Both were launched from disposable extractions for 12 seconds and closed; no physical acceptance device was used.

Candidate assessment remains **BLOCKED for release approval** because of pending physical transfer and upgrade checks, and known session-only Android capture state. No candidate APK was installed.

## Photo-preview resize test diagnosis (2026-11-18)

`test_photo_preview_and_manual_metadata_values_are_preserved` had asserted that a portrait thumbnail's pixel height must grow when the form height increases at fixed width. This expectation was incorrect: `Image.thumbnail` preserves aspect ratio and fits within both preview bounds, so the unchanged preview width can remain the limiting dimension. The Tk `<Configure>` binding and `_fit_photo_preview` behavior are unchanged. The test now checks the resulting image remains within the actual preview bounds and retains its source aspect ratio, including after requested form resizes. No timer or arbitrary wait was added.

- Focused preview test, five consecutive runs: **5 passed**.
- Related `test_intake_ui.py` and `test_app_callbacks.py`: **92 passed, 1 skipped** on one run. A later run had **92 passed, 1 failed** in the separate minimum-size GUI test (`body_height == viewport_height == 769`); the preview test passed.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-57a-full`: **516 passed, 18 skipped, 1 failed** in `test_pairing_consumes_expiring_credential_and_authenticates_device`. That mobile-connection test passed in three consecutive isolated reruns.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-57a-full-rerun`: **514 passed, 19 skipped, 2 failed** in the separate minimum-size geometry assertion and the preview test's assumption that the window-manager resize request necessarily increases the mapped preview. The preview geometry request may be constrained in the integrated test display.
- Final full suite after the assertion correction: **517 passed, 17 skipped, 1 failed**. The sole failure was again the separate minimum-size geometry test, with body and viewport both measured at 769 px. The target preview test passed.

Classification: the original pixel-height assertion was a **test defect**; the additional whole-suite resize variability is **window/display geometry sensitivity**. Automated runs do not establish physical Windows visual acceptance. No production code changed; candidate artifacts were not rebuilt or altered.

## Reported physical acceptance (recorded November 18, 2026)

The November 18 physical-test report records PASS using accepted v1.1.0-rc1 for Windows portable execution; APK export; Pairing, Forget Pairing, Unpair and reconnection; multiple-instance blocking; Purge with default Clam preserved; all backup/restore features; Android camera controls; Sales, voids, reports and status transitions; updated desktop layout; poster creation; Single Entry including edge cases; and Bulk Entry including partial and full queues. These results are reported, not independently observed. Device/build details and separate fallback physical testing were not supplied.

Production upgrade PASS was reported after first installing the historical production-signed v1.0.0 APK, then installing the exact rc1 APK over it. Android presented an update confirmation and installation succeeded. Post-upgrade settings and pairing persistence were not separately reported as verified.

The remaining display-sensitive minimum-size geometry assertion was accepted as a non-blocking release exception based on reported physical layout testing. The automated suite remains 517 passed, 17 skipped, 1 failed; it is not fully passing. The original preview failure was a corrected test defect; production preview code was unchanged. The transient mobile-connection failure passed three isolated reruns. Session-only pending captures and the prior unreproduced startup ANR remain disclosed limitations.

## Publication and independent verification (November 18, 2026)

BookLedger v1.1.0 is published at https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.1.0 as a stable release (not draft/prerelease). Annotated tag object `794954ae76d052bfbeae196a9396a26e60afeca3` peels to reviewed commit `01dc3990e9fa321e5cf2f815ce509d5a3736e9ac`. The reviewed source was committed and pushed before tag creation and publication.

All four public assets were downloaded independently and SHA-256 verified against final staging and the published manifest. Sizes: Portable 60,133,742 bytes; Fallback 60,982,251 bytes; APK 71,633,402 bytes; SHA256SUMS.txt 317 bytes. Candidate binaries were not rebuilt or modified. Historical v1.0.0 release metadata and its asset records exactly match the pre-publication snapshot. Evidence and downloaded bytes are retained under ignored `build/release58-verification/`.

The accepted automated exception remains 517 passed, 17 skipped, 1 failed (display-sensitive minimum-size assertion); physical acceptance remains documented as reported testing. Session-only pending captures, the prior unreproduced ANR, and unverified post-upgrade settings/pairing persistence remain disclosed. No fresh automated or physical test run is implied by publication verification.

### Historical ANR context clarified (November 18, 2026)

The earlier ANR report concerned a Poco X6 experiencing lag while rapid charging and connected to a PC through TwinDesk. No ANR was reproduced during the subsequent audit, and no root cause has been established. These circumstances are context, not a confirmed explanation or an active verified defect. Historical observations and test results above remain unchanged.

## Configurable currency and SRP investigation (2026-11-20)

- `.venv\Scripts\python.exe -m pytest tests/test_currency.py tests/test_posters.py tests/test_app_callbacks.py -q -rs` — **97 passed, 1 skipped**. The skip requires complete Tcl/Tk libraries that are missing from this Python installation.
- `.venv\Scripts\python.exe -m pytest -q -rs` — **534 passed, 18 skipped**. All skips are Tk UI/display checks unavailable with the installed incomplete Tcl/Tk runtime; no tests failed.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed.
- Read-only Frankfurter v2 smoke requests for PHP/USD and USD/PHP on November 20 returned the documented pair/rate/date shape with observation date 2026-11-20. The supported-code list was checked against `/v2/currencies`. These checks establish response compatibility at that time, not continuing service availability.

Automated rate tests use mocked responses. A single database conversion containing 100 copies, 120 sale-history rows (including voided sales), and 2 SRPs made **one** rate request. Tests cover two-decimal formatting across all 20 codes, decimal half-up rounding, zero and overflow rejection, empty-library changes, Yes/No/Cancel routing, explicit differing source/destination, rate reuse and stale rejection, offline, timeout and malformed responses, transaction rollback, config-write interruption/reconciliation, schema v12 migration without numeric changes, backup/restore of currency/cache/audit state, and purge to PHP. Existing reporting and poster tests pass in the full run.

Live Google Books ISBN checks were rate limited (HTTP 429). The three read-only Booktopia product snapshots matched paperbacks but only one displayed supplier RRP; no documented extraction permission or API was found. Open Library, Archive.org, Big Book API, and Hardcover did not document a usable publisher retail-price field. Automated SRP remains empty; manual SRP remains informational. Physical edition coverage, retailer extraction permission, native Settings rendering, and broader desktop visual behavior were not verified. Refer to the currency source review in `docs/ARCHITECTURE.md` for the source-by-source findings and primary references.

## Update workspace and desktop navigation (2026-11-21)

The desktop **Update** page now sits directly below About and uses the bundled update SVG. It replaces the update popup with an embedded workspace page; Check Again and Open Release Page remain at the bottom. Leaving the page cancels its Tk polling callback while the daemon worker can only write to its private queue. Returning creates a fresh page and starts a new check. The application banner opens the repository and supports keyboard focus, Enter and Space; the standalone Visit GitHub link is gone. The canonical version is at the far right of the persistent workspace footer. The configurable shop logo and left-anchored mobile pairing status remain in the sidebar. Release-note text colors now follow the active ttk theme.

- `.venv\Scripts\python.exe -m pytest tests/test_updates.py tests/test_app_callbacks.py tests/test_resources.py -q -rs` — **124 passed**.
- `.venv\Scripts\python.exe -m pytest -q -rs` — **657 passed, 18 skipped, 1 failed**. The failure is the existing `tests/test_intake_ui.py::test_form_minimum_size_keeps_scrollable_content_reachable`: its requested `960×700` resize remained at `1120×826` in both full-suite runs. Two isolated reruns of that test also failed, leaving the window at `1120×850`; the window manager did not apply the requested size. The intake form and its test were not changed. The new main-shell geometry regression passed at `1000×650` and `960×700`.
- The 18 skips are Tk checks blocked by missing Tcl/Tk files: one cannot load `tk.tcl`, and 17 provider-diagnostic checks require the missing `ttk/sizegrip.tcl`.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed. `git diff --check` — passed (Git reported normal LF-to-CRLF working-copy notices).
- Native Windows source run used a separate temporary library and profile. The embedded page, navigation, footer, banner, pairing-status placement, and release notes were visually reviewed in Light and Dark themes. The live stable check returned v1.1.0 and said no newer stable release was available; Check Again worked. Clicking the banner opened the official repository in Brave. The release notes followed both themes. These checks did not use a frozen package.

The isolated test library and profile were kept separate from existing BookLedger data. No Android files, release assets, GitHub issues, commits, or remote refs were changed. Frozen-package behavior, an actual forced-size native window review, and a native offline-network simulation were not checked in this run.

## Intake-form minimum resize diagnosis (November 21, 2026)

The recurring `test_form_minimum_size_keeps_scrollable_content_reachable` failure was a test-harness timing problem, not a reproduced layout defect. The test changed the transient dialog's parent to `400×300` and immediately requested a `960×700` dialog size. Tk delivers Windows geometry changes asynchronously. The child dialog's existing `<Configure>` wait handled its own resize request, but the fixture did not first wait for the parent window-manager event. The test now waits for the parent to report the requested `400×300` size before requesting the child resize. The child must still reach exactly `960×700`; all prior scrollability, field alignment, preview sizing, and button reachability assertions remain in place. No production code or minimum-size requirements changed.

An isolated geometry replica reported a `1920×1080` screen, Tk scaling `1.333333`, and Windows DPI `96` (100% display scaling). The BookForm window was in normal state, transient to the root, held the expected Tk grab, was resizable in both dimensions, and had minimum size `960×700`; its reported maximum was `3844×1061`. Its requested size initially remained at `1120×850`, then a matching `960×700` `<Configure>` arrived about a quarter-second later. This confirms asynchronous WM geometry delivery; it does not demonstrate a platform-imposed 1120-pixel minimum. In the normally launched application using an isolated library/profile, manual resizing reached the narrow supported width; scrolling the form exposed the Save, Clear, and Cancel controls. This was a visual native check, not evidence of an exact native `960×700` client size.

- The minimum-size regression with parent-event synchronization: **10 consecutive isolated runs passed**.
- `.venv\Scripts\python.exe -m pytest tests/test_intake_ui.py tests/test_app_callbacks.py -q -rs` — **105 passed, 1 skipped**. The skip could not initialize Tk because `init.tcl` is missing from the installed Python runtime.
- `.venv\Scripts\python.exe -m pytest -q -rs` — **657 passed, 19 skipped, 0 failed**. Skips are Tk/display checks blocked by missing `init.tcl`, `tk.tcl`/`ttk/scrollbar.tcl`, or `ttk/sizegrip.tcl` files in the installed runtime.

Earlier November 21 full-suite and isolated failures (the child remained `1120×826` or `1120×850`) are retained above as historical results. The event-order correction was followed by ten passes and a passing full suite; test/display timing can still vary across Windows environments. The standalone geometry run and native UI run used disposable test data and did not touch the user's library.

## Verified update downloads (November 21, 2026)

Current source builds can download and verify eligible release packages without installing or replacing application files. Windows accepts only the ZIP matching the running frozen package; Android accepts only an eligible production-signed build. Both stream to isolated staging storage, enforce HTTPS host/redirect and size constraints, verify the exact release asset against `SHA256SUMS.txt`, and retain the verified file. Windows ZIPs also receive path, layout, size, CRC, and protected-user-data checks. Cancellation and failure remove only the operation's incomplete file. Android signing identity, package name, and version code remain for a separate install workflow.

The public latest stable release was v1.1.0, equal to the current installed/source version. Its release metadata listed the APK (71,633,402 bytes), Windows portable ZIP (60,133,742 bytes), fallback ZIP (60,982,251 bytes), and `SHA256SUMS.txt` (317 bytes). Release metadata and the GitHub asset redirect host were inspected, but no release payload was downloaded: there was no newer eligible version, and source/debug builds cannot use the production download flow. No live package transfer, production-signature continuity, installation, or native-device download was verified.

- `.venv\Scripts\python.exe -m pytest tests/test_updates.py tests/test_update_download.py tests/test_update_archive.py -q -rs` — **63 passed, 1 skipped**. The skipped UI test could not load Tcl/Tk `init.tcl`.
- `.venv\Scripts\python.exe -m pytest -q -rs` — **674 passed, 18 skipped, 0 failed**. One Tk test could not load `tk.tcl`; 17 provider diagnostic UI tests require the missing `ttk/sizegrip.tcl`.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed. `git diff --check` — passed; Git emitted only configured LF-to-CRLF working-copy notices.
- `flutter test test/update_service_test.dart test/update_check_action_test.dart --reporter expanded` — **36 passed**.
- `flutter test --reporter expanded` — **162 passed, 0 failed, 0 skipped**.
- `flutter analyze` — **21 informational deprecations** for existing `package:flutter/material.dart` imports across application and test files; no warnings or errors.
- `dart format --output=none --set-exit-if-changed lib test` — **39 files checked, 0 changed**.
- `flutter build apk --debug` — passed; the debug APK was not installed. The build reports future Gradle/AGP/Kotlin minimum-version warnings from the configured toolchain; see the Android development notes above.

Download tests use synthetic releases and transport fixtures. They cover stream integrity, exact release identity and asset name, case-insensitive manifest duplicates, HTTPS redirect policy, cancellation, bounded sizes, low storage, partial-file cleanup, and preservation of unrelated library files. They do not prove a live release transfer or installer behavior. The desktop source session reports the current v1.1.0 release as up to date, so its real download control is ineligible.

## Simplified update installation workflow (November 21, 2026)

The Windows Update page now displays manual upgrade steps after ZIP verification. Portable instructions replace only `BookLedger.exe`; Fallback instructions replace `BookLedger.exe` and its complete `_internal/` directory together. Both require extracting to a new folder, backing up first, preserving `data/`, `backups/`, configuration and custom files, and avoiding whole-ZIP extraction over a populated app folder. The updater still performs no Windows replacement or rollback.

Android now offers **Install Update** after download verification and native APK inspection confirm the private staged file's SHA-256, package `com.bookledger.mobile`, and a version code higher than the installed build. An explicit confirmation warns that unsent captures may be lost. Native handoff uses Android's package installer and a read-only `FileProvider` URI; the manifest declares `REQUEST_INSTALL_PACKAGES`, and missing per-source permission opens Android settings. The installer retains normal user approval. The app reports success only if the result returns and PackageManager confirms the requested version. Cancellation, permission denial, unavailable installer, and invalid APK paths leave app data untouched. No pending captures are automatically deleted.

Checks run:

- `.venv\Scripts\python.exe -m pytest tests/test_updates.py -q -rs` — **37 passed, 1 skipped**. The skipped Tk test could not initialize the installed Tcl/Tk runtime (`tcl_findLibrary` unavailable).
- `.venv\Scripts\python.exe -m pytest -q -rs` — **676 passed, 17 skipped, 1 failed**. The failure was `tests/test_intake_ui.py::test_form_minimum_size_keeps_scrollable_content_reachable`: after the requested `960×700` resize, the window remained `1120×826`. This is the previously observed display/window-manager geometry assertion, not an update test. Seventeen provider-diagnostic Tk tests were skipped because `ttk/sizegrip.tcl` is missing.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `flutter test test/update_service_test.dart test/update_check_action_test.dart --reporter expanded` — **43 passed**. Installer UI coverage includes wrong package, same version code, rejected APK inspection, explicit capture warning, cancellation, permission guidance, unavailable installer, and widget disposal during handoff.
- `flutter test --reporter expanded` — **169 passed, 0 failed, 0 skipped**.
- `flutter analyze` — **exit 1** with **21 informational `package:flutter/material.dart` deprecations**, and no warnings or errors. These are SDK import notices; analysis was not clean.
- `dart format --output=none --set-exit-if-changed lib test` — **40 files checked, 0 changed**.
- `flutter build apk --debug` — passed. Flutter warned that configured Gradle 9.3.1, AGP 9.1.1, and Kotlin 2.4.10 will soon fall below its supported minimum versions; no dependency changes were made.
- `git diff --check` — passed with configured LF-to-CRLF notices.

No Android device test was run: `adb` is not installed, and the current stable v1.1.0 release is not newer than the installed version. Tests mock the installer interface; the native package installer, production signature continuity, device permission screen, update result callback, pairing/settings persistence after a real upgrade, and pending-capture behavior during process replacement remain unverified. The debug APK was built but not installed. The new `REQUEST_INSTALL_PACKAGES` permission was not exercised on a device. Existing data and release assets were not changed; Issue #22, commits, and remote refs were not touched.

## Intake-form geometry regression (November 21, 2026)

On this Windows/Tk run, the isolated minimum-size test reproduced twice in five unmodified attempts: after the root's `400×300` Configure event, the transient form did not receive the requested `960×700` Configure event within the test's two-second failure timeout and remained at its previous `1120×850` size. A passing Configure trace showed the parent event followed by the child resize request and the child's `960×700` event. This supports a test-harness event-order race; no production layout defect was reproduced.

The regression test now drains pending idle and window events after confirming the parent geometry and before requesting the transient child's resize. It retains the exact `960×700` assertion and all scroll, field alignment, preview resizing, and button-accessibility checks.

- Isolated geometry regression before synchronization: **3 passed, 2 failed** in five consecutive attempts; both failures remained at `1120×850`.
- Isolated geometry regression after synchronization: **10 passed, 0 failed, 0 skipped** in ten consecutive attempts.
- `.venv\Scripts\python.exe -m pytest tests/test_intake_ui.py tests/test_app_callbacks.py -q -rs` — **105 passed, 1 skipped**. The skipped Tk case could not load `tk.tcl` dependencies (`entry.tcl` missing).
- `.venv\Scripts\python.exe -m pytest tests/test_updates.py tests/test_update_archive.py -q -rs` — **52 passed, 1 skipped**. The skipped Tk case could not load `ttk/progress.tcl`.
- `.venv\Scripts\python.exe -m pytest -q -rs` — **675 passed, 19 skipped, 0 failed**. Skips are Tk/display-dependent checks blocked by missing Tcl/Tk files, including `entry.tcl`, `icons.tcl`, and `ttk/sizegrip.tcl`.

These are automated results from the current Windows test environment. They do not establish behavior on other Windows display configurations or replace manual visual acceptance. No Android checks were repeated because no Android code changed.

## v1.2.0-rc1 physical acceptance (November 21, 2026)

All three staged rc1 artifact SHA-256 values were recomputed and matched `dist/v1.2.0-rc1/SHA256SUMS-rc1.txt`. The candidate ZIPs and APK were not modified. Windows tests used freshly extracted Portable and Fallback packages, isolated profiles and disposable libraries; covers were synthetic.

### Fresh Windows candidate checks

| Check | Portable | Fallback |
| --- | --- | --- |
| Fresh extraction, launch, version 1.2.0 display, normal exit | **PASS** | **PASS** |
| Intake, edit, search, and cover photo | **PASS** | **PASS** |
| Catalog | **PASS** | **PASS** |
| Inventory, Acquisitions, Sale History, Reports navigation | **PASS** | **SKIPPED** |
| Sales transaction and report-content accuracy | **SKIPPED** | **SKIPPED** |
| Description shortening | **PASS**; reviewed and selected in an unsaved form | **SKIPPED** |
| ISBN metadata | **PARTIAL**; Open Library and Archive.org returned fields, while Google Books and Booktopia reported provider/HTTP errors | **SKIPPED** |
| Currency change and conversion | **PASS**; isolated PHP-to-USD conversion updated the displayed amount | **SKIPPED** |
| Backup creation | **PASS** | **PASS** |
| Backup restore and restart persistence | **PASS**; restored disposable data/configuration and relaunched | **SKIPPED** |
| Single-instance enforcement | **PASS** | **SKIPPED** |
| Update page, release information and latest stable check | **PASS**; live check reported installed 1.2.0 and latest stable 1.1.0 | **SKIPPED** |
| Offline/network failure and minimum-window reachability | **SKIPPED** | **SKIPPED** |

The metadata and shortening dialogs were canceled after inspection, so neither changed the test library. The Fallback package's initial launch displayed a Windows Firewall prompt; it was canceled without changing firewall settings.

### Manual Windows package replacement

The v1.1.0 Portable and Fallback packages were extracted separately and given disposable books, synthetic cover photos and pre-upgrade backups. For Portable, only `BookLedger.exe` was replaced. For Fallback, `BookLedger.exe` and the complete `_internal/` directory were replaced together; the old runtime directory was preserved separately in the isolated test folder. In each case the rc1 app relaunched as v1.2.0, showed the existing book and cover, and retained the backup file. Both replacement paths **PASS** for the exercised data-retention checks.

Customized v1.1.0 settings were not changed before either replacement, and the pre-upgrade backups were not restored after replacement. Those checks are **SKIPPED**; the package tests establish book/photo/backup-file retention, not custom-setting migration or cross-version restore compatibility.

### Android in-place update

Wireless ADB identified an authorized POCO X6 5G (`23122PCD1G`) on Android 16/API 36. Before installation, production `com.bookledger.mobile` was v1.1.0+2, version code 2, and not debuggable. The candidate was v1.2.0+3, version code 3, min SDK 24 and target SDK 36. The pre-update installed APK and candidate signing certificate SHA-256 matched `539e4a74e133604ec420c1d3a19584200e2a926f19f0ba7b4652de0bb7a85f3d`. `/data` reported 226 GB available of 462 GB.

After explicit owner approval, `adb install -r` completed with `Success`. Package Manager reported `versionName=1.2.0`, `versionCode=3`, and the original `firstInstallTime`. A read-only pull of the installed base APK had SHA-256 `73cc232c1bed24cdf40f96b6d8e3b3c62b9ec774d02b9082d1e328db117a0752`, identical to the staged APK; `apksigner` reported the same certificate SHA-256 as the candidate. The app launched and displayed `BookLedger Mobile · v1.2.0`, and the About page displayed the same version. No uninstall or data clear was performed and no captures were created or modified.

The post-upgrade home page displayed `Not paired`. Because pairing status was not recorded before installation, this does not establish whether a previous pairing was preserved or lost. Existing settings and captures were not inventoried before or after the update. Settings update control, live release check, network-failure handling, repeated checks, light/dark presentation, capture transfer and in-app installer handoff remain **unverified**. The successful ADB replacement does not test the in-app installation flow. The previous status for this physical-test record was **Ready for Physical Acceptance**; see the final reconciliation below. No automated suites were rerun for this documentation update.

## v1.2.0-rc1 final acceptance reconciliation (November 21, 2026)

The owner reports no issues during additional manual testing. The scenarios were not itemized, so this report does not convert any earlier **PARTIAL**, **SKIPPED** or **unverified** result to **PASS**. The exercised Windows package replacements retained disposable books, photos and backups. The production Android package updated in place, launched as v1.2.0, and its installed APK bytes and signer matched the candidate.

No release-blocking defect was identified in the available automated results or the behaviors directly exercised on Windows and Android. Remaining nonblocking exceptions are incomplete Windows scenario coverage (including sales transactions, report accuracy, offline handling and minimum-window reachability), settings migration and cross-version backup restoration, and unverified Android pairing/settings/capture baselines and feature flows. The Android home page showed `Not paired`, but the pre-upgrade state is unknown. The desktop full suite recorded 18 Tcl/Tk skips. Flutter analysis exited 1 with 21 informational deprecations, no warnings and no errors. These limitations are suitable for an explicit release decision, but the owner must review the unchecked source/artifact checklist item and decide whether to accept them.

**Disposition: Ready for Release Approval.** This is a recommendation only; release approval and publication remain pending. No automated suites or physical checks were repeated during this documentation reconciliation.

## v1.2.0 final publication review — November 21, 2026

The accepted files under `dist/v1.2.0-rc1/` were rehashed and matched `SHA256SUMS-rc1.txt`. After owner approval of the corrected Portable and Fallback ZIPs, unchanged production APK, and new SHA-256 manifest for final artifact preparation, the final-named files were copied to `dist/v1.2.0/`. The accepted rc1 directory remains unchanged. Each final ZIP has the same member list and order as its accepted counterpart, passes CRC validation, and differs only in root `README.md` and `mobile/README.md`. The final APK is byte-identical to the accepted APK. The README discrepancy and correction are detailed in the candidate report.

Proposed asset verification:

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `BookLedger-v1.2.0-Windows-x64-Portable.zip` | 60,220,092 | `154584d4a2485a74b96a9250d5481989cd49f4ca37e02a3e1e72abbfae148b5a` |
| `BookLedger-v1.2.0-Windows-x64-Fallback.zip` | 61,053,994 | `46839ebb5ebe26a4c330f27c69521b752e7d0d224f6b69f3308ed7af97a24da0` |
| `BookLedger-v1.2.0-Android.apk` | 70,915,414 | `73cc232c1bed24cdf40f96b6d8e3b3c62b9ec774d02b9082d1e328db117a0752` |
| `SHA256SUMS.txt` | 317 | `021c02de6d10d065e83d6a4920f1e971fdf5a38601121b7c9b6808e214739ed2` |

Fresh extraction and process-start attempts were made for both corrected Windows ZIPs. The executables remained running, but the available probe did not capture a visible window title; GUI launch confirmation remains **SKIPPED**, not passed, and the owner asked that this limitation remain documented. A further PowerShell window-enumeration command was rejected by execution policy before it ran. Previously recorded candidate launch and physical acceptance results remain evidence for the unchanged executable payloads, but do not substitute for visible confirmation of the corrected ZIPs. Both executables were byte-compared with accepted ZIP members and report FileVersion/ProductVersion `1.2.0`; the Fallback archive contains 1,038 files under `_internal/`. The APK reports package `com.bookledger.mobile`, version `1.2.0`, code `3`; `apksigner` verifies it and reports certificate SHA-256 `539e4a74e133604ec420c1d3a19584200e2a926f19f0ba7b4652de0bb7a85f3d`. No desktop or Flutter test suite was rerun because no application source changed. The final checksum manifest was independently recalculated from `dist/v1.2.0/` and matches the listed values.

The candidate acceptance findings and physical-testing limitations remain unchanged. Artifact preparation did not perform any commit, push, tag creation, issue update, asset upload, or GitHub Release. Current `main` is at `7b64159e20d23abb90326a2911ed1b5f44802ea9`, one local commit ahead of `origin/main`; no new Git commit was made during this preparation. The staged final assets are ready for a separate publication decision, with visible-window confirmation still skipped.
