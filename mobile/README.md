 # BookLedger Mobile

Flutter companion application for session-only book capture and local pairing with BookLedger desktop.

Single Entry shows Scan, Manual, and No ISBN inside the camera canvas. Selecting an identifier opens photography; taking a cover photo makes the entry ready for explicit Send when connected. Change preserves the photograph during identifier correction; Cancel change restores the previous identifier. Retake keeps the old photograph until a replacement succeeds, and canceling restores it. The fixed bottom layout is Take Photo / Retake above Send / Clear. Bulk Entry queues independently identified ISBN/photo captures in app-private temporary storage, with capacity from 5 to 20. Bulk uses Queue in the Send position until the batch is ready. Successful Queue automatically opens the next ISBN scan if capacity remains; at capacity it awaits explicit Send. To finish early, close the ISBN scanner with its X button, then hold Queue with no current capture. Early completion is unavailable while scanning or while an unqueued capture is in progress. Send transfers the queued ISBNs, photographs, capture identifiers, order, and timestamps to the paired desktop; the desktop stages the received batch for cataloging.

Mobile App Setup pairs to the desktop over the local network using QR or manual IPv4 entry. The device token is stored in Android secure storage. HTTP traffic is unencrypted, so pair only on a trusted network. Reconnection tries the last endpoint, then DNS-SD/mDNS discovery, then saved addresses. QR and manual entry remain available when multicast discovery is unavailable. Windows hotspot discovery has not been physically verified.

## Install the APK

The combined Windows portable ZIP includes the production-signed app at `mobile/BookLedger-Android.apk`. The separately published v1.0.0 APK is named `BookLedger-v1.0.0-Android.apk`. Copy either APK to an Android device and open it from Files or another package installer. Android may ask you to allow installs from that source; follow its prompt. On Android 8.0 and later, this permission is controlled per source. See [Android's sideloading guidance](https://developer.android.com/distribute/marketing-tools/alternative-distribution). The app ID is `com.bookledger.mobile`; the current source targets unpublished candidate `v1.1.0-rc1`, version `1.1.0` (version code `2`). Development debug APKs from `main` are unpublished and cannot establish production-signed upgrade compatibility. This is a companion app that uses BookLedger Desktop to manage the transferred inventory, not a standalone inventory manager. It is distributed by sideloading and is not available through Google Play.

BookLedger Mobile stays in portrait and keeps the display awake while it is in the foreground. The device's power button can still lock the screen manually. Android's normal display timeout applies while the app is in the background; returning to BookLedger restores the foreground behavior.

During live cover-photo preview, use the torch button for continuous light, the zoom slider for supported 0.5× steps up to 3.0×, and the Guide button to cycle between L-frame, 3×3 grid, 4×4 grid, and Off. Some cameras do not support the 0.5× stop. Zoom and Guide selections are remembered on the device across capture sessions and app restarts. The guide overlays are alignment aids only and are not added to captured photos. Camera controls disappear after capture; Retake restores the selected preferences.

## Permissions and privacy

The app requests Camera access at runtime for ISBN scanning and cover photography. Internet and network-state access support local desktop pairing and reconnection. AndroidX also declares a package-scoped, signature-protected dynamic-receiver permission. The app does not request microphone or broad shared-storage permissions. CameraX writes captured photos to app-private temporary storage; Android's share sheet handles any user-initiated photo sharing.

Pairing and transfers use unencrypted HTTP over the local network, so pair only on a trusted network. Pairing registers a short-lived pairing credential and then a device token; the token authenticates later requests and the phone's device name is sent during pairing. A transfer sends the capture ISBN, photograph, capture identifier, order, and timestamp. Pending captures and queue metadata are session-only: process termination can lose the queue even if temporary photographs remain. Keep the app open until the desktop acknowledges the transfer; a process interruption can leave temporary files until app or Android cleanup. The desktop retains received captures in its portable `data/incoming/` storage and database until each capture is cataloged or discarded. Desktop databases, photos, configuration, backups, and staged incoming files are not encrypted.

Barcode image input and results are processed on-device and are not sent to Google by BookLedger. The bundled ML Kit SDK may contact Google for model updates, fixes, and hardware compatibility information, and sends usage/performance metrics. See [ML Kit Terms and Privacy](https://developers.google.com/ml-kit/terms); make this possible SDK traffic visible to users as applicable. The app does not implement its own analytics or telemetry; this source review does not independently observe network traffic.

The APK includes Flutter's generated package notices at `assets/flutter_assets/NOTICES.Z`. Include the repository's `LICENSE`, `THIRD_PARTY_NOTICES.md`, and `licenses/Android/` with direct APK distribution. That folder supplies the Apache 2.0 text and Flutter engine license bundle for this APK's engine revision.

For the desktop and companion data-handling summary, see the [BookLedger Privacy Notice](../docs/PRIVACY_NOTICE.md). In a standalone APK distribution, include that notice alongside this README, `LICENSE`, `THIRD_PARTY_NOTICES.md`, and `licenses/Android/`.

## Android release signing

The Android application ID is `com.bookledger.mobile`; the current source targets `1.1.0+2` (version name `1.1.0`, Android version code `2`) for unpublished candidate `v1.1.0-rc1`. Keep the application ID and release signing key stable. Increase the build number after `+` for every subsequent APK release; Android requires later versions to use a greater version code. See [Android app versioning](https://developer.android.com/studio/publish/versioning) and [app signing](https://developer.android.com/studio/publish/app-signing).

Release builds require an external signing properties file. Store it and the release keystore outside this repository, in a protected user-profile location, and set `BOOKLEDGER_SIGNING_PROPERTIES` to the file path before building. The properties file contains `storeFile`, `storePassword`, `keyAlias`, and `keyPassword` in plaintext, so restrict its file access. Keep encrypted keystore backups in two separate protected locations; store recovery credentials in a password manager, separate from the key, and periodically verify a restored copy can sign a test build. Loss of the key prevents future signed upgrades. Never put signing values in project Gradle files or source control. Release builds fail if the properties file or keystore is missing, incomplete, or inside the repository; they do not fall back to the Android debug key.

From this directory, run `flutter build apk --release`. Flutter writes the APK to `build/app/outputs/flutter-apk/app-release.apk`. Verify it with Android SDK `apksigner` and inspect the application ID, version, permissions, and bundled notices before distribution. For the Windows portable ZIP, stage the verified APK at `release-input/BookLedger-Android.apk` in the repository root, then run `scripts/build_windows_portable.ps1`; the script checks its signature and bundles it at `mobile/BookLedger-Android.apk` without re-signing it.

In BookLedger Desktop, choose **Settings → Mobile App Setup → Export APK**, then save the copy and transfer it to the Android device. Export uses the APK beside `BookLedger.exe` and does not modify the bundled file. For a standalone direct APK release, provide this README, the repository `LICENSE` and `THIRD_PARTY_NOTICES.md`, `docs/PRIVACY_NOTICE.md`, and the `licenses/Android/` directory with the APK.

The production-signed `1.0.0+1` APK uses the existing `bookledger-release` certificate. Android requires future upgrades to use the same signing identity and a greater version code. The maintainer reported that the initial 2026-11-16 physical smoke session used the exact final Windows ZIP and APK and passed Android workflows and desktop transfers. In a subsequent maintainer-reported round, the two restart scenarios skipped in that session were reported PASS. Device details, Android fresh-install versus upgrade status, and whether the follow-up round used the exact final assets were not supplied; see the [test report](../TEST_REPORT.md). Do not uninstall an existing installation for upgrade testing unless its app data has first been safely preserved.

## Development

From this directory:

- `flutter analyze`
- `flutter test`
- `dart format --output=none --set-exit-if-changed lib test`
- `flutter build apk --debug`
