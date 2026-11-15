 # BookLedger Mobile

Flutter companion application for session-only book capture and local pairing with BookLedger desktop.

Single Entry scans ISBNs and captures front-cover photographs. Bulk Entry queues independently identified ISBN/photo captures in app-private temporary storage, with capacity from 5 to 20. A batch can be finished early by holding Queue. Send marks it ready locally; book/photo transfer is not implemented.

Mobile App Setup pairs to the desktop over the local network using QR or manual IPv4 entry. The device token is stored in Android secure storage. HTTP traffic is unencrypted, so pair only on a trusted network. Reconnection tries the last endpoint, then DNS-SD/mDNS discovery, then saved addresses. QR and manual entry remain available when multicast discovery is unavailable. Windows hotspot discovery has not been physically verified.

Barcode scanning uses the bundled Google ML Kit model. Scanned image input and barcode results are processed on the device and are not sent to Google. ML Kit may contact Google for model updates, fixes, and hardware compatibility information, and sends usage and performance metrics. See [ML Kit Terms and Privacy](https://developers.google.com/ml-kit/terms); disclose this SDK traffic to users as applicable. The APK includes Flutter's generated package notices at `assets/flutter_assets/NOTICES.Z`. For direct APK releases, also attach the repository's `THIRD_PARTY_NOTICES.md`, which records Android SDK and ML Kit terms and the release review status.

## Android release signing

The Android application ID is `com.bookledger.mobile`; the current version is `1.0.0+1` (version name `1.0.0`, Android version code `1`). Keep the application ID and release signing key stable. Increase the build number after `+` for every subsequent APK release; Android requires later versions to use a greater version code. See [Android app versioning](https://developer.android.com/studio/publish/versioning) and [app signing](https://developer.android.com/studio/publish/app-signing).

Release builds require an external signing properties file. Store it and the release keystore outside this repository, in a protected user-profile location, and set `BOOKLEDGER_SIGNING_PROPERTIES` to the file path before building. The properties file contains `storeFile`, `storePassword`, `keyAlias`, and `keyPassword` in plaintext, so restrict its file access. Keep encrypted keystore backups in two separate protected locations; store recovery credentials in a password manager, separate from the key, and periodically verify a restored copy can sign a test build. Loss of the key prevents future signed upgrades. Never put signing values in project Gradle files or source control. Release builds fail if the properties file or keystore is missing, incomplete, or inside the repository; they do not fall back to the Android debug key.

From this directory, run `flutter build apk --release`. Flutter writes the APK to `build/app/outputs/flutter-apk/app-release.apk`. Verify it with Android SDK `apksigner` and inspect the application ID, version, permissions, and bundled notices before distribution. For the Windows portable ZIP, copy the verified APK to `release-input/BookLedger-Android.apk` at the repository root, then run `scripts/build_windows_portable.ps1`; that script rejects debug-signed APKs and places the accepted file at `mobile/BookLedger-Android.apk`. For a standalone GitHub release, attach the same APK and `THIRD_PARTY_NOTICES.md`.

The previously generated local release APK is signed with the Android debug certificate and is not distributable. A production-signed APK cannot upgrade an installation signed with that different debug key. Do not uninstall an existing installation to test upgrades unless its app data has first been safely preserved. No emulator or Android device was available for installation or upgrade checks during the current release preparation.

## Development

From this directory:

- `flutter analyze`
- `flutter test`
- `dart format --output=none --set-exit-if-changed lib test`
- `flutter build apk --debug`
