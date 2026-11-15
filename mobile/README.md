 # BookLedger Mobile

Flutter companion application for session-only book capture and local pairing with BookLedger desktop.

Single Entry scans ISBNs and captures front-cover photographs. Bulk Entry queues independently identified ISBN/photo captures in app-private temporary storage, with capacity from 5 to 20. A batch can be finished early by holding Queue. Send marks it ready locally; book/photo transfer is not implemented.

Mobile App Setup pairs to the desktop over the local network using QR or manual IPv4 entry. The device token is stored in Android secure storage. HTTP traffic is unencrypted, so pair only on a trusted network. Reconnection tries the last endpoint, then DNS-SD/mDNS discovery, then saved addresses. QR and manual entry remain available when multicast discovery is unavailable. Windows hotspot discovery has not been physically verified.

## Install the APK

The combined Windows portable ZIP includes the production-signed app at `mobile/BookLedger-Android.apk`. Copy it to an Android device and open it from Files or another package installer. Android may ask you to allow installs from that source; follow its prompt. On Android 8.0 and later, this permission is controlled per source. See [Android's sideloading guidance](https://developer.android.com/distribute/marketing-tools/alternative-distribution). The app ID is `com.bookledger.mobile`; the current version is `1.0.0` (version code `1`). It is a direct APK distribution and is not available through Google Play.

## Permissions and privacy

The app requests Camera access at runtime for ISBN scanning and cover photography. Internet and network-state access support local desktop pairing and reconnection. AndroidX also declares a package-scoped, signature-protected dynamic-receiver permission. The app does not request microphone or broad shared-storage permissions. CameraX writes captured photos to app-private temporary storage; Android's share sheet handles any user-initiated photo sharing.

Pairing and transfers use unencrypted HTTP over the local network, so pair only on a trusted network. Barcode image input and results are processed on-device and are not sent to Google. The bundled ML Kit SDK may contact Google for model updates, fixes, and hardware compatibility information, and sends usage/performance metrics. See [ML Kit Terms and Privacy](https://developers.google.com/ml-kit/terms); make this possible SDK traffic visible to users as applicable.

The APK includes Flutter's generated package notices at `assets/flutter_assets/NOTICES.Z`. Include the repository's `THIRD_PARTY_NOTICES.md` with direct APK distribution; it records Android SDK and ML Kit terms and the release review status.

## Android release signing

The Android application ID is `com.bookledger.mobile`; the current version is `1.0.0+1` (version name `1.0.0`, Android version code `1`). Keep the application ID and release signing key stable. Increase the build number after `+` for every subsequent APK release; Android requires later versions to use a greater version code. See [Android app versioning](https://developer.android.com/studio/publish/versioning) and [app signing](https://developer.android.com/studio/publish/app-signing).

Release builds require an external signing properties file. Store it and the release keystore outside this repository, in a protected user-profile location, and set `BOOKLEDGER_SIGNING_PROPERTIES` to the file path before building. The properties file contains `storeFile`, `storePassword`, `keyAlias`, and `keyPassword` in plaintext, so restrict its file access. Keep encrypted keystore backups in two separate protected locations; store recovery credentials in a password manager, separate from the key, and periodically verify a restored copy can sign a test build. Loss of the key prevents future signed upgrades. Never put signing values in project Gradle files or source control. Release builds fail if the properties file or keystore is missing, incomplete, or inside the repository; they do not fall back to the Android debug key.

From this directory, run `flutter build apk --release`. Flutter writes the APK to `build/app/outputs/flutter-apk/app-release.apk`. Verify it with Android SDK `apksigner` and inspect the application ID, version, permissions, and bundled notices before distribution. For the Windows portable ZIP, stage the verified APK at `release-input/BookLedger-Android.apk` in the repository root, then run `scripts/build_windows_portable.ps1`; the script checks its signature and bundles it at `mobile/BookLedger-Android.apk` without re-signing it.

In BookLedger Desktop, choose **Settings → Mobile App Setup → Export APK**, then save the copy and transfer it to the Android device. Export uses the APK beside `BookLedger.exe` and does not modify the bundled file. For a standalone direct APK release, provide this README and `THIRD_PARTY_NOTICES.md` with the APK.

The production-signed `1.0.0+1` APK uses the existing `bookledger-release` certificate. Android requires future upgrades to use the same signing identity and a greater version code. A previous physical-device test of this APK with a packaged Windows executable was reported by the project owner; that prior test does not verify this newly assembled combined ZIP. Do not uninstall an existing installation for upgrade testing unless its app data has first been safely preserved.

## Development

From this directory:

- `flutter analyze`
- `flutter test`
- `dart format --output=none --set-exit-if-changed lib test`
- `flutter build apk --debug`
