# Third-party notices

The MIT License in [`LICENSE`](LICENSE) applies to original BookLedger source code only. It does not relicense third-party libraries, platform runtimes, or artwork. This audit snapshot is dated 2026-11-16. It records source and dependency findings; it does not clear a particular release artifact for distribution.

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

The desktop also uses Python's `sqlite3` module and Tkinter/Tcl/Tk. SQLite's core is public domain ([SQLite notice](https://www.sqlite.org/copyright.html)). Python is licensed under PSF-2.0 ([Python license](https://docs.python.org/3.14/license.html)). The package includes the Python runtime license, the bundled Tk `license.terms`, Tcl/Tk 8.6 terms from the [upstream Tcl 8.6 branch](https://github.com/tcltk/tcl/blob/core-8-6-branch/license.terms), and CPython 3.14.6's [third-party license acknowledgements](https://github.com/python/cpython/blob/v3.14.6/Doc/license.rst), covering bundled OpenSSL, Expat, zlib, and other incorporated components.

The Windows one-file candidate is built with 64-bit CPython 3.14.6, PyInstaller 6.22.3, Pillow 12.3.0, ttkbootstrap 2.2.3, qrcode 8.2, zeroconf 0.153.0, and ifaddr 0.2.0. The installed Pillow SBOM and enabled-feature report identify native components linked into Pillow's extensions: FreeType 2.14.3, Little CMS 2.19.1, libavif 1.4.2, libjpeg-turbo 3.1.4.1, libtiff 4.7.1, libwebp 1.6.0, OpenJPEG 2.5.4, and zlib-ng 2.3.3. The installed Pillow 12.3.0 `_avif` extension reports AOM encoder 3.14.1 and dav1d decoder 1.5.3-0-gb546257 through its compiled runtime API; both codecs report enabled. The versioned [Pillow Windows build recipe](https://github.com/python-pillow/Pillow/blob/12.3.0/winbuild/build_prepare.py) and [dependency license directory](https://github.com/python-pillow/Pillow/tree/12.3.0/wheels/dependency_licenses) identify the build configuration and base license texts. AOMedia states its software uses a combination of BSD 3-Clause Clear, its Patent License 1.0, and a related statement; all three materials are supplied under `licenses/Pillow-Dependencies/` ([AOMedia legal terms](https://aomedia.org/about/legal/)). VideoLAN identifies dav1d as BSD-2-Clause ([upstream project](https://images.videolan.org/projects/dav1d.html)). RAQM/FriBiDi and libimagequant were not enabled in this Windows build. Recheck the native component inventory when Pillow changes.

The bundled ttkbootstrap icon font also has a separate MIT license in its installed package at `ttkbootstrap/assets/icons/LICENSE`. It is now included as `licenses/Bootstrap-Icons/LICENSE` alongside the package's main license.

Python/Tcl/Tk DLLs, Pillow extensions and their native libraries, `ifaddr`, BookLedger resources, and ttkbootstrap assets are bundled in `BookLedger.exe`; Zeroconf source, notices, license texts, README, empty `data/` and `backups/`, and the optional Android companion are distributed beside it. At launch, PyInstaller extracts bundled runtime files temporarily; BookLedger stores persistent data beside the executable. License texts for the runtime packages and packaging tools identified in this audit are staged beside the executable.

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

The eight Android Maven coordinates without POM license declarations were inspected individually. A missing POM field alone is not evidence that a dependency is unlicensed.

| Coordinate | License evidence | In the APK |
| --- | --- | --- |
| `com.google.auto.value:auto-value-annotations:1.6.3` | Apache-2.0 boilerplate and Google copyright in the exact [published POM](https://repo1.maven.org/maven2/com/google/auto/value/auto-value-annotations/1.6.3/auto-value-annotations-1.6.3.pom) | No AutoValue package classes in DEX; build-time annotation artifact |
| `com.google.guava:failureaccess:1.0.3` | Apache-2.0; JAR contains `META-INF/LICENSE`; [Guava source](https://github.com/google/guava/tree/v33.5.0) | No FailureAccess classes in DEX |
| `com.google.guava:guava:33.5.0-android` | Apache-2.0; versioned [Guava release](https://github.com/google/guava/releases/tag/v33.5.0) and [LICENSE](https://github.com/google/guava/blob/v33.5.0/LICENSE) | No Guava package classes in DEX |
| `com.google.guava:listenablefuture:9999.0-empty-to-avoid-conflict-with-guava` | Empty conflict-avoidance artifact; JAR has no `.class` entries; [published POM](https://repo1.maven.org/maven2/com/google/guava/listenablefuture/9999.0-empty-to-avoid-conflict-with-guava/listenablefuture-9999.0-empty-to-avoid-conflict-with-guava.pom) | No executable classes |
| `io.flutter:arm64_v8a_release:1.0.0-89c39edfdfae2949f6806e4a315c0c08522238b7` | Flutter engine license bundle pinned to this engine revision | `lib/arm64-v8a/libflutter.so` |
| `io.flutter:armeabi_v7a_release:1.0.0-89c39edfdfae2949f6806e4a315c0c08522238b7` | Flutter engine license bundle pinned to this engine revision | `lib/armeabi-v7a/libflutter.so` |
| `io.flutter:flutter_embedding_release:1.0.0-89c39edfdfae2949f6806e4a315c0c08522238b7` | Flutter engine license bundle pinned to this engine revision | Flutter embedding classes in DEX |
| `io.flutter:x86_64_release:1.0.0-89c39edfdfae2949f6806e4a315c0c08522238b7` | Flutter engine license bundle pinned to this engine revision | `lib/x86_64/libflutter.so` |

Flutter's [licensing FAQ](https://docs.flutter.dev/resources/faq) distinguishes its BSD-3-Clause framework from the engine and its listed dependencies. The Flutter SDK's generated license record and Maven version pin the engine source to revision `89c39edfdfae2949f6806e4a315c0c08522238b7`. The matching official [`sky_engine/LICENSE`](https://github.com/flutter/engine/blob/89c39edfdfae2949f6806e4a315c0c08522238b7/sky/packages/sky_engine/LICENSE) was taken from that revision's published `sky_engine.zip` and is included at `licenses/Android/Flutter-engine-LICENSE.txt`. The Apache-2.0 license text is included at `licenses/Android/Apache-2.0.txt`. The APK also retains Flutter's generated `NOTICES.Z`.

Google's terms describe ML Kit as related software under the Google APIs Terms, restrict reverse engineering/extraction, and explain that processing is on-device while the SDK may contact Google for model/fix/hardware compatibility updates and send usage/performance metrics. For source distribution, the repository identifies dependencies but does not include the resolved SDK or model binaries. The audited APK includes Flutter's compressed `NOTICES.Z` and AndroidX license metadata. All eight POM gaps now have an upstream license or artifact-content finding, with Apache and exact Flutter engine license material supplied alongside the APK. This technical inventory does not replace review of Google's terms or legal review. No separate ML Kit attribution requirement was identified in the reviewed terms.

### Android dependency follow-up — November 17, 2026

At source commit `b50d2cfb900f593779d693dc11accd7b4d88afaa`, comparison of `mobile/pubspec.lock` with the immutable `v1.0.0` tag shows no package-version or checksum change. The only lockfile change promotes `camera_platform_interface` 2.15.0 from transitive to direct **development** dependency so tests can use camera fakes. It was already in the v1.0.0 graph; the new declaration does not itself add a runtime package or new distributable APK code. Direct runtime versions remain `camera` 0.12.2 and `mobile_scanner` 7.5.0, with the other direct packages unchanged. Android Gradle plugin 9.1.0, Kotlin plugin 2.4.0, and Gradle 9.3.1 declarations are unchanged since the tag.

The current `debugRuntimeClasspath` dependency report resolved CameraX 1.6.2, ML Kit barcode scanning 17.3.0, Play Services ML Kit barcode scanning 18.3.1, and Flutter engine revision `89c39edfdfae2949f6806e4a315c0c08522238b7`; this is a debug graph, not a fresh release-runtime license audit. The built debug APK retains `assets/flutter_assets/NOTICES.Z`. The existing Apache 2.0 and revision-matched Flutter engine license texts remain in `licenses/Android/`, and `mobile/README.md` still directs distributors to include those files, this notice, and the privacy notice. No new application permission or BookLedger analytics endpoint was found in the source/manifest review. The earlier Maven POM findings and November 16 audit above remain historical; the exact future release candidate and its complete merged dependency/notice set must be checked before redistribution. This technical comparison is not legal clearance.

## GitHub branding

`mobile/assets/github-mark.png` appears in the mobile home page and About page as an icon on buttons that open the BookLedger GitHub repository. It is a link mark, not the BookLedger app logo. Its SHA-256 is `6D6EF7BEDE0416B6EBEE2014BE5852576DBCE89235FE16EA5C44ED01BD522132`; it is byte-for-byte identical to GitHub's official [GitHub-Mark.png asset](https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png). GitHub's [logo policy](https://docs.github.com/en/site-policy/other-site-policies/github-logo-policy) and [brand guidance](https://brand.github.com/foundations/logo) permit linking use subject to their rules; do not imply GitHub affiliation or endorsement or alter the mark. This is trademark/brand guidance, not a software license grant. The current button use is consistent with linking to the repository; no replacement is needed.

## Privacy and network disclosure

Source review confirmed that BookLedger desktop sends ISBNs and any provider credentials needed by a user-started metadata lookup to the selected metadata provider over HTTPS. Mobile pairing and capture transfer use unencrypted local-network HTTP authenticated by a device token. Transfer fields are ISBN, capture UUID, sequence, capture timestamp, and JPEG; the phone keeps images in app-private temporary storage until acknowledgement, and the desktop stages received captures in portable `data/incoming/` plus its database until cataloged or discarded. These application details are summarized in `README.md` and `mobile/README.md`. Android uses Camera only for still images and declares camera, internet, network-state, and AndroidX's package-scoped dynamic-receiver permission; it does not declare microphone or broad shared-storage permissions. ML Kit processes barcode input on-device, but Google documents possible SDK communications for updates/compatibility and usage/performance metrics ([ML Kit terms](https://developers.google.com/ml-kit/terms)). This is based on source and vendor documentation, not independent network capture.

A user-facing notice is now included at `docs/PRIVACY_NOTICE.md` and staged in the portable ZIP. It identifies the approved public developer handle and public GitHub Issues channel, warns that Issues are public, and describes local storage, provider lookups, local-network pairing/transfers, possible ML Kit communications, and unencrypted user-controlled backups. The developer's legal name, location, and intended release jurisdictions remain unspecified. GitHub Issues may not satisfy a jurisdiction's requirement for a named controller or confidential contact. This source and package review is not a jurisdiction-specific legal assessment. The Philippine National Privacy Commission's [Data Privacy Act information](https://privacy.gov.ph/DATA-PRIVACY-ACT/) describes data-subject information rights, including information about processing and the controller.

## Audit disposition

| Component | License / obligation | Evidence | Status |
|---|---|---|---|
| Zeroconf 0.153.0 | LGPL-2.1-or-later; include source, notices, and practical replacement route | `zeroconf/` source plus `COPYING`; excluded from executable archive; runtime hook loads sibling source; source comparison and disposable-folder replacement launch | Pass for the reviewed technical mechanism; not legal advice |
| CPython 3.14.6 and Tcl/Tk 8.6 | PSF-2.0 and third-party/runtime notices | Python `LICENSE.txt`, CPython 3.14.6 third-party license document, Tcl/Tk and Tk `license.terms` in ZIP | Pass for identified terms |
| Pillow 12.3.0 and enabled native codecs | Pillow MIT-CMU; AOM BSD 3-Clause Clear, Patent License 1.0, and statement; dav1d BSD-2-Clause; other enabled-library notices | Installed SBOM and compiled `_avif` API identify libavif 1.4.2, AOM 3.14.1, and dav1d 1.5.3; all identified license texts and AOM patent materials included | Pass for versioned inventory and identified license materials |
| ttkbootstrap 2.2.3 | Package expression plus separate Bootstrap Icons MIT notice | Package license and `licenses/Bootstrap-Icons/LICENSE` | Pass for identified terms |
| Flutter/Dart and Android graph | Per-component notices; ML Kit terms and privacy disclosure | APK `NOTICES.Z`, AndroidX license metadata, eight POM gaps resolved through artifact/upstream evidence; Android Apache and exact Flutter engine license materials staged | Pass for identified technical notices; terms/legal review remains |
| AI artwork and eight SVG icons | Output ownership subject to law; SVG icons individually marked CC0 | Owner-confirmed source, identical banner hashes, icon path match, and linked individual CC0 pages | Pass for documented artwork inventory, subject to applicable law and inputs |
| GitHub logo image | Trademark/brand linking rules; provenance record | Local image SHA-256 byte-matches GitHub's official asset URL; current use links to the project repository | Pass for provenance and reviewed linking use, subject to policy changes |
| Privacy and networking | Accurate processing, purpose, recipients, retention, and contact disclosure as applicable | `docs/PRIVACY_NOTICE.md` is included in the candidate package; names the approved public handle and warns the Issues channel is public | Notice is prepared; controller identity, jurisdiction, and legal adequacy remain owner/legal-review questions |

## Distribution readiness

| Artifact | Status | Required release work |
| --- | --- | --- |
| Windows portable ZIP | **Conditionally ready for owner review; not legally cleared** | Package notices and public privacy notice are included. Technical AOM/Pillow inventory and Android notice findings are recorded; GitHub asset provenance is verified. Intended jurisdictions and legal adequacy of a public GitHub contact remain unassessed. |
| Android APK | **Production-signed candidate; conditionally ready for owner review** | Original APK remains unchanged, Flutter notices are present, and companion instructions include the privacy notice. This smoke test verified APK export byte identity, not Android installation or upgrade behavior for this ZIP. |

The production-signed APK is `%USERPROFILE%\.bookledger\android\releases\BookLedger-Android-1.0.0+1-permission-audit.apk`. It is 71,616,886 bytes (SHA-256 `C9C82CC92D67F055ED9C2C232FC2294F94AF20C57173ED5B9E456448EE9D39C9`); `apksigner` verified APK Signature Scheme v2, and its certificate SHA-256 (`539e4a74e133604ec420c1d3a19584200e2a926f19f0ba7b4652de0bb7a85f3d`) matches the existing `bookledger-release` signing identity. The package is `com.bookledger.mobile`, version `1.0.0` / code `1`, min SDK 24, target SDK 36. It contains Flutter's compressed `NOTICES.Z`, Flutter engine libraries for arm64-v8a, armeabi-v7a, and x86_64, and the bundled ML Kit barcode model. The manifest retains camera, internet, network-state, and AndroidX's package-scoped dynamic-receiver permission; it excludes `RECORD_AUDIO`, `READ_EXTERNAL_STORAGE`, and `WRITE_EXTERNAL_STORAGE`. Its identity and checksum were not changed during this audit. The owner reported prior physical-device testing of this APK against a packaged Windows executable; this was not a fresh installation/upgrade test of the rebuilt combined ZIP. A prior one-file candidate was also reported tested from local extraction with Clam and portable paths; that does not establish clean-machine compatibility. These findings are not legal advice or final compliance clearance.
