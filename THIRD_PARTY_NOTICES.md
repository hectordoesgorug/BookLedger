# Third-party notices

The MIT License in [`LICENSE`](LICENSE) applies to original BookLedger source code only. It does not relicense third-party libraries, platform runtimes, or artwork. This audit snapshot is dated 2026-11-15. It records source and dependency findings; it does not clear a particular release artifact for distribution.

## AI-generated artwork

The project owner confirmed that ChatGPT generated the BookLedger application icon and banner. The banner is present at `assets/banner.png` and `mobile/assets/banner.png`; these two files have identical SHA-256 hashes. The application icon assets are `assets/icon.ico` and `mobile/assets/icon/app_icon.png`; Flutter uses the latter as the launcher-icon source in `mobile/pubspec.yaml`.

OpenAI's [Terms of Use](https://openai.com/policies/terms-of-use/) say that, as between OpenAI and the user and to the extent permitted by law, the user owns Output and OpenAI assigns any right, title, and interest it may have. The terms also say outputs may not be unique. This supports use of the generated artwork subject to applicable law and rights in any inputs; it does not establish copyright eligibility, exclusivity, or a particular level of copyright protection. No OpenAI artwork attribution requirement was identified in those terms. The confirmed provenance is recorded here for traceability.

## SVG Repo desktop icons

The eight desktop navigation icons in `assets/` were compared with the supplied [Office Duotone Minimalist Icons collection](https://www.svgrepo.com/collection/office-duotone-minimalist-icons/). Their SVG path data matches these individual SVG Repo entries:

| BookLedger file | SVG Repo entry | Individual page |
| --- | --- | --- |
| `assets/icon-acquisitions.svg` | `global-display` (530431) | [SVG 530431](https://www.svgrepo.com/svg/530431/global-display) |
| `assets/icon-catalog.svg` | `picture` (530429) | [SVG 530429](https://www.svgrepo.com/svg/530429/picture) |
| `assets/icon-dashboard.svg` | `align-two-columns` (530428) | [SVG 530428](https://www.svgrepo.com/svg/530428/align-two-columns) |
| `assets/icon-help.svg` | `help` (530436) | [SVG 530436](https://www.svgrepo.com/svg/530436/help) |
| `assets/icon-inventory.svg` | `copy` (530424) | [SVG 530424](https://www.svgrepo.com/svg/530424/copy) |
| `assets/icon-reports.svg` | `pie-chart` (530435) | [SVG 530435](https://www.svgrepo.com/svg/530435/pie-chart) |
| `assets/icon-sale history.svg` | `trend-analysis` (530427) | [SVG 530427](https://www.svgrepo.com/svg/530427/trend-analysis) |
| `assets/icon-settings.svg` | `set-up` (530434) | [SVG 530434](https://www.svgrepo.com/svg/530434/set-up) |

Each individual page identifies the icon as **CC0**. SVG Repo's [licensing page](https://www.svgrepo.com/page/licensing/) describes CC0 as allowing copying, modifying, distributing, and using the work without asking permission or providing attribution. Attribution is not required; the source links are retained here. The item pages are inconsistent about displaying the collection name (some show a generic “SVG Vector” label), but the path-data matches and each individual page's CC0 designation were verified. No icon in this inventory has unresolved source or license status.

## Python desktop

Python versions below are those installed in the repository `.venv`; `requirements.txt` and `pyproject.toml` specify ranges and there is no Python lockfile.

| Component | Version / role | License and source |
| --- | --- | --- |
| Pillow | 12.3.0; runtime image handling | MIT-CMU; [upstream license](https://github.com/python-pillow/Pillow/blob/12.3.0/LICENSE) |
| ttkbootstrap | 2.2.3; runtime UI | `MIT AND (Apache-2.0 OR BSD-2-Clause)` per package metadata; [versioned package record](https://pypi.org/project/ttkbootstrap/2.2.3/) |
| qrcode | 8.2; runtime QR generation | BSD-3-Clause; [versioned package record](https://pypi.org/project/qrcode/8.2/) |
| zeroconf | 0.153.0; runtime network discovery | LGPL-2.1-or-later; [upstream COPYING](https://github.com/python-zeroconf/python-zeroconf/blob/0.153.0/COPYING) |
| ifaddr | 0.2.0; zeroconf runtime dependency | MIT per package metadata; [versioned package record](https://pypi.org/project/ifaddr/0.2.0/) |
| pytest | 9.1.1; development only | MIT; [upstream license](https://github.com/pytest-dev/pytest/blob/main/LICENSE) |
| PyInstaller | 6.22.3; development packaging tool | GPL-2.0-or-later with an exception for generated application bundles; some files are Apache-2.0. The exception does not remove obligations from bundled dependencies. [License details](https://pyinstaller.org/en/stable/license.html) |
| pyinstaller-hooks-contrib | 2026.8; development packaging support | Standard hooks are GPL-2.0-or-later; runtime hooks are Apache-2.0. Check which runtime hooks enter a build. [Upstream license](https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/master/LICENSE) |

The app imports `zeroconf` directly from `src/bookledger/services/mobile_discovery.py`. The installed distribution metadata and versioned upstream COPYING identify LGPL-2.1-or-later. In the Windows candidate, PyInstaller excludes Zeroconf from its executable; the version 0.153.0 `.py` sources, `py.typed`, and `COPYING` are placed in the sibling `zeroconf/` directory. A runtime hook puts the executable directory on `sys.path`, and a successful frozen launch confirmed the external package imports. This leaves the LGPL library source replaceable without rebuilding the executable. Its `COPYING` file sits beside the source, avoiding a duplicate under `licenses/`; the README explains replacement and requires preserving COPYING and marking changes. This implements the anticipated replaceable-library path for LGPL section 6; verify it again against the exact release bundle and applicable legal review. The PyInstaller exception addresses PyInstaller's own license only. No changes to Zeroconf were made.

The desktop also uses Python's `sqlite3` module and Tkinter/Tcl/Tk. SQLite's core is public domain ([SQLite notice](https://www.sqlite.org/copyright.html)). Python is licensed under PSF-2.0 ([Python license](https://docs.python.org/3/license.html)). The candidate includes the Python license, the bundled Tk `license.terms`, and the Tcl/Tk 8.6 license text from the [upstream Tcl 8.6 branch](https://github.com/tcltk/tcl/blob/core-8-6-branch/license.terms). The resolved package includes Tcl/Tk 8.6 runtime files; recheck the license set if the build Python version changes.

The Windows one-file candidate is built with 64-bit CPython 3.14.6, PyInstaller 6.22.3, Pillow 12.3.0, ttkbootstrap 2.2.3, qrcode 8.2, zeroconf 0.153.0, and ifaddr 0.2.0. Python/Tcl/Tk DLLs, `ifaddr`, BookLedger resources, and ttkbootstrap assets are bundled in `BookLedger.exe`; Zeroconf source, notices, license texts, README, empty `data/` and `backups/`, and the optional Android companion are distributed beside it. At launch, PyInstaller extracts bundled runtime files temporarily; BookLedger stores persistent data beside the executable. The build includes license texts for the runtime packages and packaging toolchain identified in this audit.

## Flutter and Android

Direct Flutter package versions are resolved in [`mobile/pubspec.lock`](mobile/pubspec.lock):

| Package | Version | License and source |
| --- | --- | --- |
| camera | 0.12.2 | BSD-3-Clause; [versioned package license](https://pub.dev/packages/camera/versions/0.12.2/license) |
| mobile_scanner | 7.5.0 | BSD-3-Clause; [versioned package license](https://pub.dev/packages/mobile_scanner/versions/7.5.0/license) |
| path_provider | 2.1.6 | BSD-3-Clause; [versioned package license](https://pub.dev/packages/path_provider/versions/2.1.6/license) |
| share_plus | 13.3.1 | BSD-3-Clause; [versioned package license](https://pub.dev/packages/share_plus/versions/13.3.1/license) |
| permission_handler | 12.0.3 | MIT; [versioned package license](https://pub.dev/packages/permission_handler/versions/12.0.3/license) |
| flutter_secure_storage | 11.2.0 | BSD-3-Clause; [versioned package license](https://pub.dev/packages/flutter_secure_storage/versions/11.2.0/license) |
| cupertino_icons | 1.0.9 | MIT; [versioned package license](https://pub.dev/packages/cupertino_icons/versions/1.0.9/license) |

The locked Flutter graph also contains transitive Dart packages. A scan of the resolved package cache's license files grouped 73 packages as BSD-3-Clause, 13 as MIT, 4 as Apache-2.0, and 2 as Flutter SDK packages. Flutter and Dart SDK components have their own notices; Flutter describes the framework's BSD-3-Clause license, engine dependencies, and the license registry in its [licensing FAQ](https://docs.flutter.dev/resources/faq#which-software-licenses-apply-to-flutter-and-its-dependencies). The app's current About guide does not expose a license page, so a release should provide the applicable Dart and engine notices through a license screen or accompanying notice material.

### Resolved Android release graph

The configured Gradle wrapper resolved `:app:releaseRuntimeClasspath` using the existing Android Studio JBR (OpenJDK 25.0.4); no JDK was installed and no persistent environment setting was changed. The build dependency report completed successfully. It resolved 101 unique external Maven coordinates: 82 with Apache-2.0 POM metadata, one CameraX coordinate with Apache-2.0 and BSD-3-Clause metadata, 6 with ML Kit Terms of Service metadata, 4 with Android Software Development Kit License metadata, and 8 without a license declaration in their Maven POM. The absent POM declaration is not itself evidence of an unlicensed component.

Key selected Android components include CameraX 1.6.2 (including `camera-core`, whose POM lists Apache-2.0 and BSD-3-Clause), bundled-model ML Kit barcode scanning 17.3.0, Google Play Services ML Kit barcode 18.3.1, Guava 33.5.0-android, Tink 1.23.0, and kotlinx.coroutines 1.11.0. `mobile_scanner` defaults to the bundled ML Kit model; its unbundled Play Services mode is optional. The resolved ML Kit modules declare Google's [ML Kit Terms of Service](https://developers.google.com/ml-kit/terms); they are not treated as Apache-licensed. Google Play Services artifacts refer to the [Android Software Development Kit License](https://developer.android.com/studio/terms). AndroidX, Guava, Tink, and kotlinx.coroutines use Apache-2.0; relevant upstream sources include [AndroidX](https://github.com/androidx/androidx), [Guava](https://github.com/google/guava), [Tink](https://github.com/tink-crypto/tink-java), and [kotlinx.coroutines](https://github.com/Kotlin/kotlinx.coroutines). Guava's bundled support artifacts and Google's AutoValue annotations have upstream Apache-2.0 licensing, although the relevant Maven POMs do not state a license. Those four coordinates are `com.google.auto.value:auto-value-annotations:1.6.3`, `com.google.guava:failureaccess:1.0.3`, `com.google.guava:guava:33.5.0-android`, and `com.google.guava:listenablefuture:9999.0-empty-to-avoid-conflict-with-guava`; the AutoValue [upstream license](https://github.com/google/auto/blob/main/LICENSE) and Guava license are Apache-2.0. Four Flutter engine Maven artifacts likewise omit POM license metadata: `io.flutter:arm64_v8a_release`, `io.flutter:armeabi_v7a_release`, `io.flutter:flutter_embedding_release`, and `io.flutter:x86_64_release`, all at `1.0.0-89c39edfdfae2949f6806e4a315c0c08522238b7`. Their notices must be taken from the Flutter engine/SDK license material for the release build.

Google's terms describe ML Kit as related software under the Google APIs Terms, restrict reverse engineering/extraction, and explain that processing is on-device while the SDK may contact Google for model/fix/hardware compatibility updates and send usage/performance metrics. For source distribution, the repository identifies dependencies but does not include the resolved SDK or model binaries. An APK using the default bundled model distributes those components, so the release must include applicable notices and review privacy disclosures for the SDK's possible network communications. No separate ML Kit attribution requirement was identified in the reviewed terms. Confirm the exact built APK contents and notices before release; source-only review does not clear APK redistribution.

## GitHub branding

`mobile/assets/github-mark.png` appears in the mobile home page and About page as an icon on buttons that open the BookLedger GitHub repository. It is a link mark, not the BookLedger app logo. GitHub's [logo policy](https://docs.github.com/en/site-policy/other-site-policies/github-logo-policy) and [brand guidance](https://brand.github.com/foundations/logo) permit linking use subject to their rules; do not imply GitHub affiliation or endorsement or alter the mark. This is trademark/brand guidance, not a software license grant. The current button use is consistent with linking to the repository. The exact image file provenance was not independently established; keep the original source record if available.

## Distribution readiness

| Artifact | Status | Required release work |
| --- | --- | --- |
| Windows portable ZIP | **Combined one-folder candidate previously built; one-file candidate under validation** | Fresh-extraction startup and portable paths were checked locally for the earlier candidate. Test this exact one-file artifact on an independent clean Windows system, then recheck its notices before public distribution. |
| Android APK | **Production-signed candidate bundled; public release not cleared** | Provide the APK with the permissions and privacy guidance in `mobile/README.md`, and recheck the exact artifact and notices before distribution. Prior physical-device testing is recorded below; it did not test the combined ZIP. |

The production-signed APK used in the combined candidate is `%USERPROFILE%\.bookledger\android\releases\BookLedger-Android-1.0.0+1-permission-audit.apk`. It is 71,616,886 bytes (SHA-256 `C9C82CC92D67F055ED9C2C232FC2294F94AF20C57173ED5B9E456448EE9D39C9`); `apksigner` verified APK Signature Scheme v2, and its certificate SHA-256 (`539e4a74e133604ec420c1d3a19584200e2a926f19f0ba7b4652de0bb7a85f3d`) matches the existing `bookledger-release` signing identity. The package is `com.bookledger.mobile`, version `1.0.0` / code `1`, min SDK 24, target SDK 36. It contains Flutter's compressed `NOTICES.Z`, Flutter engine libraries for arm64-v8a, armeabi-v7a, and x86_64, and the bundled ML Kit barcode model. The manifest retains camera, internet, network-state, and AndroidX's package-scoped dynamic-receiver permission; it excludes `RECORD_AUDIO`, `READ_EXTERNAL_STORAGE`, and `WRITE_EXTERNAL_STORAGE`. BookLedger uses CameraX only for still photos stored in app-private cache, does not record video, and shares app-owned files through Android's share sheet. The production-signed APK is staged for the current one-file build and will be included as `BookLedger/mobile/BookLedger-Android.apk`. The app has no in-app license page; the ZIP includes Flutter notices in the APK and repository third-party notices alongside the app. `mobile/README.md` documents sideload installation, permissions, local unencrypted pairing, ML Kit processing and possible SDK network traffic. The project owner reported prior physical-device testing of the signed APK against a packaged Windows executable; this is not a new test of the combined ZIP. This candidate was also tested from a fresh local extraction with Clam selected and portable configuration/database paths; that does not establish clean-machine compatibility. These findings do not establish legal advice or final-artifact compliance; recheck the exact dependencies and assets selected for each release.
