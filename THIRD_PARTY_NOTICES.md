# Third-party notices

The MIT License in [`LICENSE`](LICENSE) applies to original BookLedger source code only. It does not relicense third-party libraries, platform runtimes, or artwork.

This is a source-repository audit snapshot dated 2026-11-15, not a complete bill of materials for a future Windows package or Android APK. Python dependency versions below are those installed in the repository's `.venv`; `requirements.txt` and `pyproject.toml` specify ranges and there is no Python lockfile. Mobile package versions are resolved in [`mobile/pubspec.lock`](mobile/pubspec.lock). The Android Maven runtime graph was not resolved during this audit because Java is unavailable in the current environment.

## Python desktop

| Component | Version / role | License and source |
| --- | --- | --- |
| Pillow | 12.3.0; runtime image handling | MIT-CMU; [upstream license](https://github.com/python-pillow/Pillow/blob/12.3.0/LICENSE) |
| ttkbootstrap | 2.2.3; runtime UI | `MIT AND (Apache-2.0 OR BSD-2-Clause)` per package metadata; [versioned package record](https://pypi.org/project/ttkbootstrap/2.2.3/) |
| qrcode | 8.2; runtime QR generation | BSD-3-Clause; [versioned package record](https://pypi.org/project/qrcode/8.2/) |
| zeroconf | 0.153.0; runtime network discovery | LGPL-2.1-or-later; [upstream COPYING](https://github.com/python-zeroconf/python-zeroconf/blob/0.153.0/COPYING) |
| ifaddr | 0.2.0; zeroconf runtime dependency | MIT per package metadata; [versioned package record](https://pypi.org/project/ifaddr/0.2.0/) |
| pytest | 9.1.1; development only | MIT; [upstream license](https://github.com/pytest-dev/pytest/blob/main/LICENSE) |
| PyInstaller | 6.22.3; development packaging tool | GPL-2.0-or-later with an exception for generated application bundles; some files are Apache-2.0. The exception permits distributing PyInstaller-built applications under other terms, subject to their dependencies. [License details](https://pyinstaller.org/en/stable/license.html) |
| pyinstaller-hooks-contrib | 2026.8; development packaging support | Standard hooks are GPL-2.0-or-later; runtime hooks are Apache-2.0. Check which runtime hooks enter a build. [Upstream license](https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/master/LICENSE) |

The desktop also uses Python's `sqlite3` module and Tkinter/Tcl/Tk. SQLite's core is public domain ([SQLite notice](https://www.sqlite.org/copyright.html)). Python is licensed under PSF-2.0 ([Python license](https://docs.python.org/3/license.html)); the Tcl/Tk libraries have their own notices. The precise Python, Tcl, and Tk versions and files that a Windows portable build will include depend on the packaging/runtime selection, which has not yet been made.

## Flutter and Android

Direct Flutter packages resolved in `mobile/pubspec.lock`:

| Package | Version | License and source |
| --- | --- | --- |
| camera | 0.12.2 | BSD-3-Clause; [versioned package license](https://pub.dev/packages/camera/versions/0.12.2/license) |
| mobile_scanner | 7.5.0 | BSD-3-Clause; [versioned package license](https://pub.dev/packages/mobile_scanner/versions/7.5.0/license) |
| path_provider | 2.1.6 | BSD-3-Clause; [versioned package license](https://pub.dev/packages/path_provider/versions/2.1.6/license) |
| share_plus | 13.3.1 | BSD-3-Clause; [versioned package license](https://pub.dev/packages/share_plus/versions/13.3.1/license) |
| permission_handler | 12.0.3 | MIT; [versioned package license](https://pub.dev/packages/permission_handler/versions/12.0.3/license) |
| flutter_secure_storage | 11.2.0 | BSD-3-Clause; [versioned package license](https://pub.dev/packages/flutter_secure_storage/versions/11.2.0/license) |
| cupertino_icons | 1.0.9 | MIT; [versioned package license](https://pub.dev/packages/cupertino_icons/versions/1.0.9/license) |

The locked Flutter graph also contains transitive packages. A scan of the resolved package cache's license files grouped 73 packages as BSD-3-Clause, 13 as MIT, 4 as Apache-2.0, and 2 as Flutter SDK packages; direct runtime packages are listed above. Flutter and Dart SDK components have their own notices; the SDK documents that Flutter applications should expose applicable package and engine licenses through its license registry ([Flutter licensing guidance](https://docs.flutter.dev/resources/faq#which-software-licenses-apply-to-flutter-and-its-dependencies)). The app's current About guide does not expose a license page.

The Android plugin build files declare CameraX 1.6.1 (mobile_scanner) and 1.6.2 (camera), bundled-model ML Kit barcode scanning 17.3.0 by default, optional Play Services ML Kit barcode scanning 18.3.1, Guava 33.5.0-android, Tink 1.23.0, and kotlinx.coroutines 1.11.0. AndroidX, Guava, Tink, and kotlinx.coroutines publish Apache-2.0 notices; sources include [AndroidX](https://github.com/androidx/androidx), [Guava](https://github.com/google/guava), [Tink](https://github.com/tink-crypto/tink-java), and [kotlinx.coroutines](https://github.com/Kotlin/kotlinx.coroutines). ML Kit is Google's SDK, not assumed to be Apache-licensed; review [Google's ML Kit terms](https://developers.google.com/ml-kit/terms) and the chosen bundled or unbundled model before distribution. Exact selected artifacts and their transitive notices remain to be verified from a resolved release Gradle graph.

## Assets and remaining distribution checks

- `mobile/assets/github-mark.png` is a GitHub brand mark, not MIT-licensed project artwork. Follow [GitHub's logo policy](https://docs.github.com/en/site-policy/other-site-policies/github-logo-policy) and [brand usage guidance](https://brand.github.com/foundations/logo); the policy prohibits implying GitHub endorsement or using its logo as the product logo.
- The repository does not record provenance or license terms for its banner, app icon, desktop icons, or generated Android launcher images. Confirm their ownership and permitted redistribution before publishing a binary.
- `zeroconf` is an LGPL-2.1-or-later runtime dependency. A Windows distribution that bundles it must include the applicable LGPL text and satisfy the license's distribution conditions; review the final packaging/linking arrangement before release.
- Before distributing either binary, resolve the Android Gradle graph, identify the exact bundled Python/Tcl/Tk and Pillow components, and include all applicable third-party license texts and notices with the artifacts. This audit does not itself establish that a binary package is ready for redistribution.
