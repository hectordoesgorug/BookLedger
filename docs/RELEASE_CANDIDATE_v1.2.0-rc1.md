# BookLedger v1.2.0-rc1 candidate report

**Candidate status:** Published as stable v1.2.0, with disclosed verification limitations
**Publication:** Approved and published on November 21, 2026 as [BookLedger v1.2.0](https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.2.0).
**Preparation date:** November 21, 2026

This report preserves the prepublication checks, approval gates, and staging details as historical evidence. References below to pending publication, branch positions, and local artifact paths describe those reviews, not the current repository or local filesystem. Subsequent stable publication and independent asset verification are recorded in the [release checklist](RELEASE_CHECKLIST_v1.2.0.md#stable-release-publication-and-independent-verification--2026-11-21) and [test report](../TEST_REPORT.md#v120-stable-publication-and-independent-verification--2026-11-21). The documented acceptance limitations remain unchanged.

The candidate was prepared from the source following readiness audit commit `bc66de2e57e5004164e1a622daac2c2bfdbe8fb4` and is represented by commit `4b486a5eaf2ef83a304860d7c464220a97aba004` on `main`. At the initial final review, branch `main` was at `d4f918113e97ea6fea04f84d68837e9bc0e21004`. The accepted rc1 artifacts and published v1.1.0 assets were unchanged during that review. The repository README used final v1.2.0 asset names in preparation for publication.

## Version and toolchain

- Desktop canonical version and both Windows executable FileVersion/ProductVersion values: `1.2.0`.
- Android: `1.2.0+3`, application ID `com.bookledger.mobile`. The published v1.1.0 APK and connected production installation are `1.1.0+2`; version code `3` is higher.
- Flutter 3.50.0, Dart 3.14.0, Android Gradle Plugin 9.1.1, Gradle 9.3.1, Java 25.0.4, Android SDK Build Tools 36.0.0, min SDK 24, target/compile SDK 36. Java source/target and Kotlin JVM target remain 17.
- `settings.gradle.kts` declares Kotlin plugin 2.4.0, while Gradle's loaded plugin/compiler classes report 2.4.10; Flutter's dependency validator reports 2.4.10. Gradle's embedded Kotlin is 2.2.21 and is not the Android app compiler. This is declaration-to-runtime version drift, not a failed compile: debug and production release builds both succeed. No Kotlin or Gradle dependency change was needed.
- Flutter reports future minimums of Gradle 9.5.0, AGP 9.3.1, and Kotlin 2.4.20, along with deprecated AGP 9 plugin configuration warnings. These are maintenance warnings; the release build completed with normal dependency validation enabled.

## Automated verification

| Check | Result |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest -q -rs` | **676 passed, 18 skipped, 0 failed**. Skips require Tcl/Tk files absent from the installed Python runtime (`init.tcl` and `ttk/sizegrip.tcl`). |
| Focused desktop updates, downloads, archive, version, packaging, backup/restore and currency command | **94 passed, 1 skipped, 0 failed**. The skipped Tk update-page test cannot load `tk.tcl`. |
| Minimum-size intake regression, five separate invocations | **5 passed, 0 failed** at the exact `960×700` requirement. |
| Desktop release-version test | **3 passed** after refreshing the project's editable package metadata to `1.2.0`. |
| Python compilation, `.venv` and pinned Windows build-environment `pip check`, and final `git diff --check` | **Passed**. |
| `flutter test --reporter expanded` | **169 passed, 0 skipped, 0 failed**. |
| Focused updater/installer Flutter tests | **43 passed, 0 skipped, 0 failed**. |
| `flutter analyze` | **21 informational `package:flutter/material.dart` deprecations, 0 warnings, 0 errors; exit 1**. No Dart source changed for the version update. |
| `dart format --output=none --set-exit-if-changed lib test` | **40 files checked, 0 changed**. |
| Android debug APK smoke build | **Passed** from an isolated project copy; the first attempt lacked generated `.dart_tool/package_config.json`, then passed after resolving the locked Flutter packages in that copy. |
| Android production release APK build | **Passed** with the external signing configuration; Flutter completed `assembleRelease` in 401.9 seconds. |

The first full desktop run during the version edit had **673 passed, 19 skipped, and 2 failed** because the release-version test still expected v1.1.0 file metadata and the local editable distribution still reported 1.1.0. Both causes were corrected before the final full run. The first isolated Android debug attempt failed because generated Flutter package metadata was not copied; it was resolved within the isolated build tree. No application tests were suppressed or weakened.

The candidate Windows packaging pass initially exposed a Fallback staging-layout error: runtime files were placed beside the executable rather than under `_internal/`. The extracted application failed to load `python314.dll`. The staging layout was corrected, a fresh extraction launched the dashboard and displayed `Version 1.2.0`, and the application closed normally. The final archives use that corrected layout.

## Android candidate

`dist/v1.2.0-rc1/BookLedger-v1.2.0-rc1-Android.apk` is **70,915,414 bytes** with SHA-256 `73cc232c1bed24cdf40f96b6d8e3b3c62b9ec774d02b9082d1e328db117a0752`. `apksigner` verified APK Signature Scheme v2. Its certificate SHA-256, `539e4a74e133604ec420c1d3a19584200e2a926f19f0ba7b4652de0bb7a85f3d`, matches the published v1.1.0 APK downloaded and verified as 71,633,402 bytes with SHA-256 `26e09dd5eba9cba6f4b9863c0118063c403f285a92a31c700b0a86dce4c0f854`.

The APK has package `com.bookledger.mobile`, version name `1.2.0`, version code `3`, min SDK 24, target/compile SDK 36, and ABIs `arm64-v8a`, `armeabi-v7a`, and `x86_64`. It is not debuggable or test-only. Permissions are Camera, Internet, network state, AndroidX's package-scoped dynamic-receiver permission, and `REQUEST_INSTALL_PACKAGES`. The update `FileProvider` is non-exported, grants temporary URI access, and uses the `com.bookledger.mobile.update-files` authority. Flutter's generated `NOTICES.Z` is present.

The current release runtime graph contains 98 resolved Maven coordinates and is documented in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). `mobile/pubspec.lock` is unchanged. The candidate uses Flutter engine revision `371f77202a73e8dff57a8b3bff75bca55c090aee`; its matching SDK engine license bundle is included as `licenses/Android/Flutter-engine-LICENSE-371f7720.txt`. The older engine license remains for the historical release record. Technical notice coverage is not legal clearance.

## Windows candidates and checksums

The portable and fallback packages use 64-bit CPython 3.14.6 and the exact versions in `requirements-windows-build.txt`. Both executable resources report FileVersion and ProductVersion `1.2.0`. The two final ZIPs passed CRC and layout checks, contain the exact standalone production APK, and include project, privacy, third-party, Python/Tcl/Tk, runtime, Android, and Flutter-engine license materials. No database, configuration, backup, keystore, or signing-properties file is present.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `BookLedger-v1.2.0-rc1-Windows-x64-Portable.zip` | 60,242,067 | `b1b06ace51b1c0cc849279c00255528b7796b6a85659a3bea425c52a24138645` |
| `BookLedger-v1.2.0-rc1-Windows-x64-Fallback.zip` | 61,091,024 | `5011a8366c2619d61f4843867e5c32ebb955547045e3103fa9472eba9413e629` |
| `BookLedger-v1.2.0-rc1-Android.apk` | 70,915,414 | `73cc232c1bed24cdf40f96b6d8e3b3c62b9ec774d02b9082d1e328db117a0752` |

The final checksum file is `dist/v1.2.0-rc1/SHA256SUMS-rc1.txt`; all three entries were recomputed from the final staged bytes. Both final ZIPs include the candidate engine license in addition to the Android APK's generated notices. Both ZIPs were freshly extracted and launched on Windows 11 x64. The initial Portable startup measurement was invalid because its probe watched the PyInstaller one-file bootloader parent, which has no GUI window, instead of the child process. The corrected process-tree measurements and comparison with v1.1.0 are recorded below. They show the rc1 Portable dashboard within 2.2–3.6 seconds, not more than 120 seconds. All measured windows closed normally.

### Portable startup investigation — November 21, 2026

The exact rc1 Portable ZIP (`60,242,067` bytes; SHA-256 `b1b06ace51b1c0cc849279c00255528b7796b6a85659a3bea425c52a24138645`), rc1 Fallback ZIP (`61,091,024` bytes; SHA-256 `5011a8366c2619d61f4843867e5c32ebb955547045e3103fa9472eba9413e629`), and the published [v1.1.0 Portable ZIP](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.1.0/BookLedger-v1.1.0-Windows-x64-Portable.zip) (`60,133,742` bytes; SHA-256 `6ae46145f019c6b3bc7638e5cc97c78a9caeee6138e88124af6b5be5ba1bf276`) were tested without modifying the staged candidate files.

Measurements were made on Windows 11 Home x64, build 26200, with real-time antivirus protection enabled. Both C: and E: are local NTFS volumes. Fresh disposable extractions, `LOCALAPPDATA`/`APPDATA` profiles, and PyInstaller temp folders were used. The measured duration starts at launching the executable and ends when the visible window title is `BookLedger · Book collection manager`. “First” means first launch after extraction, not a forced cold OS file cache; no system caches or security settings were changed. Every displayed window accepted a normal close request and its process tree exited normally.

| Package and location | Root process created (+08:00) | Time to BookLedger window |
| --- | --- | ---: |
| v1.2.0-rc1 Portable, executable and temp on E: | 13:49:51.214 first | 2.257 s |
| v1.2.0-rc1 Portable, executable and temp on E: | 13:50:10.764 warm | 2.214 s |
| v1.2.0-rc1 Portable, executable and temp on E: | 13:53:55.309 diagnostic | 3.617 s |
| v1.2.0-rc1 Portable, executable and temp on C: | 13:52:33.696 first | 2.996 s |
| v1.2.0-rc1 Portable, executable and temp on C: | 13:52:39.413 warm | 2.657 s |
| v1.2.0-rc1 Portable, executable and temp on C: | 13:53:49.599 diagnostic | 2.597 s |
| v1.2.0-rc1 Fallback, extracted on E: | 13:50:31.899 first | 1.317 s |
| v1.2.0-rc1 Fallback, extracted on E: | 13:50:35.406 warm | 1.094 s |
| Published v1.1.0 Portable, extracted on E: | 13:50:52.351 first | 1.975 s |
| Published v1.1.0 Portable, extracted on E: | 13:50:57.305 warm | 2.429 s |

The Portable executable is 25,480,919 bytes. In diagnostic runs, the one-file bootloader created a child process about 1.0 seconds after the parent on E: and 1.3 seconds after the parent on C:. At window creation, its temporary `_MEI` extraction contained 1,038 files totaling 47,078,088 bytes. The app process used about 0.9–1.2 CPU seconds before the BookLedger window was observed. Fallback avoids one-file extraction and reached its window about 1.1–1.3 seconds after launch. These measurements support normal extraction overhead of roughly a second, with additional application initialization; they show no candidate-specific, two-minute stall.

**Classification: Environmental limitation (process-selection error in the measurement harness).** Watching only the process returned by `Start-Process` did not find a window even though the PyInstaller child already displayed the dashboard; that probe could wait past 120 seconds while monitoring the windowless parent. This explains the long wait in the initial investigation probe. The earlier reported >120-second observation is consistent with the same error, but its original instrument was unavailable, so its exact provenance cannot be confirmed. No application or packaging change is indicated by these runs. No Defender event or performance trace was collected, so small run-to-run variation is not attributed to antivirus scanning or a specific disk bottleneck.

## Windows physical acceptance — November 21, 2026

The exact staged Portable and Fallback ZIPs were extracted into isolated test directories and run with disposable library/profile data. All three staged artifact SHA-256 values were recomputed and matched `SHA256SUMS-rc1.txt`; none of the candidate artifacts was changed.

| Check | Portable | Fallback |
| --- | --- | --- |
| Fresh extraction, launch, v1.2.0 display, normal exit | **PASS** | **PASS** |
| Book intake, edit, search, and photo preview/catalog handling | **PASS** | **PASS** |
| Catalog navigation | **PASS** | **PASS** |
| Inventory, Acquisitions, Sale History, Reports navigation | **PASS** | **SKIPPED** |
| Sales transaction workflow and report-content accuracy | **SKIPPED** | **SKIPPED** |
| Description shortening | **PASS** (comparison reviewed; shortened text selected in an unsaved form) | **SKIPPED** |
| ISBN metadata lookup | **PARTIAL** (title, author, genre, edition, publisher and page count returned; Open Library and Archive.org succeeded, while Google Books and Booktopia reported provider/HTTP errors) | **SKIPPED** |
| Currency selection and conversion | **PASS** (isolated PHP-to-USD conversion; displayed value updated) | **SKIPPED** |
| Backup creation | **PASS** | **PASS** |
| Backup restoration and restart persistence | **PASS** (restored the isolated library/configuration and relaunched; book and USD display remained) | **SKIPPED** |
| Single-instance enforcement | **PASS** | **SKIPPED** |
| Update page, current version, stable-release result and release notes | **PASS** (live check reported installed 1.2.0, latest stable 1.1.0 and no newer release) | **SKIPPED** |
| Offline/network-failure message | **SKIPPED** | **SKIPPED** |
| Minimum-window-size reachability review | **SKIPPED** | **SKIPPED** |

The metadata and shortening forms were canceled after review, so those results did not alter the disposable catalog. The provider errors did not prevent the successful providers from filling metadata. The live update request was made from the isolated Portable test app. The test app's first Fallback launch displayed a Windows Firewall prompt; it was canceled without changing firewall settings.

The owner reports no issues during additional manual Windows testing. The tested scenarios were not itemized, so the individual **PARTIAL** and **SKIPPED** results above remain unchanged.

### Manual v1.1.0-to-v1.2.0 upgrade

Both upgrade checks used separately extracted v1.1.0 packages and disposable libraries. Each v1.1.0 library contained a book, synthetic cover photo, and a backup created before replacement. The exact candidate package contents were then applied following the documented manual replacement steps.

| Check | Portable | Fallback |
| --- | --- | --- |
| Replace only `BookLedger.exe` / replace `BookLedger.exe` and complete `_internal/` | **PASS** | **PASS** |
| Relaunch at version 1.2.0 | **PASS** | **PASS** |
| Existing book and photo remain visible | **PASS** | **PASS** |
| Pre-upgrade backup remains present | **PASS** | **PASS** |
| Customized v1.1.0 settings survive replacement | **SKIPPED** (no custom setting was changed in the source library) | **SKIPPED** (no custom setting was changed in the source library) |
| Restore the pre-upgrade backup after replacement | **SKIPPED** | **SKIPPED** |

These results verify library and photo retention for both documented replacement methods and preservation of the pre-upgrade backup files. They do not establish preservation of customized settings or restore compatibility across these particular package replacements.

## Android in-place update — November 21, 2026

Read-only preflight identified an authorized POCO X6 5G (`23122PCD1G`, Android 16/API 36) connected over wireless ADB. Before installation, production `com.bookledger.mobile` was version `1.1.0+2`, version code 2, and not debuggable. The candidate APK is version `1.2.0+3`, version code 3, min SDK 24, target SDK 36, and not debuggable. The installed pre-update APK and candidate had matching signing certificate SHA-256 `539e4a74e133604ec420c1d3a19584200e2a926f19f0ba7b4652de0bb7a85f3d`.

`/data` reported 226 GB available of 462 GB. After owner approval, `adb install -r` installed the exact candidate APK successfully as an in-place update. Package Manager reported version name `1.2.0`, version code 3, and an unchanged `firstInstallTime`. The installed APK was pulled read-only; its SHA-256 exactly matched the staged APK (`73cc232c1bed24cdf40f96b6d8e3b3c62b9ec774d02b9082d1e328db117a0752`) and its signer certificate matched the candidate. The app launched and displayed `BookLedger Mobile · v1.2.0`; the About page also displayed v1.2.0. No uninstall or data clear was performed, and no captures were created or modified.

The home page displayed `Not paired` after the update, but the pairing state was not recorded before installation, so preservation or loss of a prior pairing cannot be determined. Existing captures and user settings were not inventoried before or after the update. The owner reports no issues during additional manual testing of the updated app, but did not provide a scenario list; the mobile Settings update control, release check, network-failure message, repeated checks, and light/dark presentation therefore remain unverified. The `adb install -r` command confirms package replacement, not the in-app update installer flow. No newer stable release exists to test a v1.2.0-to-later update. The 18 Tcl/Tk skips and 21 Flutter analysis infos remain as reported in Automated verification above.

## Final release-gate assessment — November 21, 2026

No release-blocking defect was identified in the recorded automated checks or the Windows and Android behaviors exercised directly. The exact candidate artifact hashes match the manifest; the installed Android APK matches the candidate bytes and production signing certificate; the in-place update and app launch succeeded. The owner reports no issues during additional manual testing, with no itemized scenario coverage.

The following limitations remain documented and were not converted to passes: Windows sales transactions, report-content accuracy, offline handling and minimum-window reachability; selected Fallback feature workflows; changed-settings migration and cross-version backup restoration; and Android pairing/settings/capture baselines, update UI and capture transfer. The automated desktop suite has 18 Tcl/Tk skips, and Flutter analysis exits 1 with 21 informational deprecations and no warnings or errors. These are nonblocking for seeking release approval, provided the owner reviews the remaining source/artifact checklist item and accepts the disclosed limits. The pre-upgrade Android pairing, settings and capture states cannot be reconstructed from the available evidence.

## Candidate assessment

**Ready for Publication Authorization, with disclosed limitations.** The approved final ZIPs correct the stale v1.1.0 README text and links that pointed to files absent from the packages. The original rc1 ZIPs remain unchanged. The owner approved the corrected Windows ZIPs, unchanged APK and new manifest for final artifact preparation. Visible-window confirmation on fresh extractions remains **SKIPPED**; this and the previously documented Windows/Android acceptance limitations are retained. No release tag, issue change, or GitHub Release has been made.

## Final publication review — November 21, 2026

The candidate source remains commit `4b486a5eaf2ef83a304860d7c464220a97aba004`. The initial final review was performed at `d4f918113e97ea6fea04f84d68837e9bc0e21004`; current `main` is `7b64159e20d23abb90326a2911ed1b5f44802ea9`, one local commit ahead of `origin/main`. Changes since the candidate source are acceptance/release documentation only. The accepted files in `dist/v1.2.0-rc1/` were not modified.

Inspection of the accepted ZIPs found that the root README still calls v1.1.0 the latest published release and links to the v1.1.0 Android APK. The packaged `mobile/README.md` also presents v1.1.0 as current. Several relative README links also pointed to files not included in the ZIPs, including the update guide, architecture notes, test report, and banner image. The repository READMEs now describe v1.2.0, use its final filenames while clearly stating it is unpublished, and link to the versioned GitHub files so packaged copies can reach those resources after the v1.2.0 tag is published.

The owner approved the corrected final Windows ZIPs, the unchanged production APK, and the new checksum manifest for final artifact preparation. The accepted rc1 files remain preserved in `dist/v1.2.0-rc1/`; byte-identical copies of the approved final asset set are staged under `dist/v1.2.0/`. Each final ZIP passed CRC validation and has the same member list as its accepted counterpart; only the root and mobile README payloads differ. The final APK is byte-identical to the accepted APK. Fresh-extraction process-start attempts were made for both ZIPs, but the GUI window was not independently observed by the available title probe. A further PowerShell window-enumeration check was rejected by the execution policy before it ran. Visible-window confirmation remains **SKIPPED**, as accepted for this preparation step. Final hashes, manifests, package contents, version metadata, signing identity, and documentation links were rechecked after staging.

| Approved final asset | Bytes | SHA-256 | Candidate relationship |
| --- | ---: | --- | --- |
| `BookLedger-v1.2.0-Windows-x64-Portable.zip` | 60,220,092 | `154584d4a2485a74b96a9250d5481989cd49f4ca37e02a3e1e72abbfae148b5a` | Accepted candidate payload with corrected root/mobile READMEs |
| `BookLedger-v1.2.0-Windows-x64-Fallback.zip` | 61,053,994 | `46839ebb5ebe26a4c330f27c69521b752e7d0d224f6b69f3308ed7af97a24da0` | Accepted candidate payload with corrected root/mobile READMEs |
| `BookLedger-v1.2.0-Android.apk` | 70,915,414 | `73cc232c1bed24cdf40f96b6d8e3b3c62b9ec774d02b9082d1e328db117a0752` | Byte-identical copy of accepted candidate APK |
| `SHA256SUMS.txt` | 317 | `021c02de6d10d065e83d6a4920f1e971fdf5a38601121b7c9b6808e214739ed2` | Manifest for the three final assets |

The original rc1 hashes remain the accepted-candidate values in the preceding table. The final manifest was independently recomputed from `dist/v1.2.0/` and matches its three staged assets. No tag or release has been created. Proposed tag: `v1.2.0`. Proposed release title: `BookLedger v1.2.0`.

After separate publication authorization, the sequence is: commit the approved release documentation and staging decisions; push the reviewed commit to `main`; create and push annotated tag `v1.2.0` on that commit; create release `BookLedger v1.2.0` with the approved notes; upload both Windows ZIPs, the Android APK and `SHA256SUMS.txt`; independently download and verify all four files; confirm GitHub marks v1.2.0 latest stable; and check the README download links. Issue #22 and the unresolved SRP/provider issues remain unchanged in this review.
