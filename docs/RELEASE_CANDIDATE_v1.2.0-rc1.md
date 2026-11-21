# BookLedger v1.2.0-rc1 candidate report

**Candidate status:** Ready for Physical Acceptance  
**Release approval:** Not assessed; no release has been published.  
**Preparation date:** November 21, 2026

The candidate was prepared from the source following readiness audit commit `bc66de2e57e5004164e1a622daac2c2bfdbe8fb4` and is represented by commit `4b486a5eaf2ef83a304860d7c464220a97aba004` on `main`. Candidate artifacts remain staged locally; the published v1.1.0 release assets and README download links are unchanged.

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

## Device checks and remaining limits

Read-only ADB diagnostics found one authorized POCO X6 5G running Android 16/API 36 with production `com.bookledger.mobile` version `1.1.0+2`, not debuggable. No package was installed, removed, replaced, or cleared, and no pairing state or captures were modified.

Production-signed in-place upgrade, settings/pairing preservation, camera/scanning, capture transfer, Android installer prompts, and update installation remain unverified on a device. No newer stable release exists to test a v1.2.0-to-later update. Desktop physical acceptance beyond the fresh-extraction startup check also remains pending. The 18 Tcl/Tk skips and 21 Flutter analysis infos remain as reported above.

## Candidate assessment

**Ready for Physical Acceptance.** All three versioned candidate assets and a checksum manifest are staged in `dist/v1.2.0-rc1/`; the Portable startup delay was not reproduced with process-tree-aware measurement and does not currently block physical acceptance. This classification is not release approval. Android upgrade and feature acceptance remain pending. No release tag, issue change, or GitHub Release has been made.
