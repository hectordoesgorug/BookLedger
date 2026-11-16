# BookLedger v1.0.0 Release Checklist

This checklist separates preparation checks from owner-controlled publication steps. A completed local check does not mean a GitHub Release has been published.

## Preparation completed

- [x] Initial source baseline was clean `main`, synchronized with `origin/main` at `9aea676e0dcd6dd33b01e559cc55a497d6eea3a6`.
- [x] Android release identity verified: `com.bookledger.mobile`, version name `1.0.0`, version code `1`.
- [x] Desktop release version set to `1.0.0` from the package's canonical version declaration.
- [x] One-file release and one-folder fallback builds both embed FileVersion/ProductVersion `1.0.0`.
- [x] Versioned Windows ZIP and standalone Android APK prepared without changing APK bytes.
- [x] SHA-256 checksums generated and checked against the exact release files.
- [x] Windows ZIP integrity and package contents verified; no user database, private configuration, keystore, or signing properties are included.
- [x] APK signature and certificate verified; APK identity and version checked.
- [x] Windows smoke test passed from a fresh temporary extraction on the build machine. Clean-machine compatibility is not established by this check.
- [x] Privacy notice, third-party notices, and companion distribution materials are present.
- [x] Focused release-version and packaging tests, plus the full Python suite, passed.
- [x] No local or remote `v1.0.0` tag was present during this preparation; GitHub currently lists no Releases.

## Prepared files

| File | Size | SHA-256 |
| --- | ---: | --- |
| `BookLedger-v1.0.0-Windows-x64-Portable.zip` | 60,086,257 bytes | `339AEBED62A374C4BBBCAD4AF05FB9AE44C5C9C4FA830E94C85B1AC6E670AF50` |
| `BookLedger-v1.0.0-Android.apk` | 71,616,886 bytes | `C9C82CC92D67F055ED9C2C232FC2294F94AF20C57173ED5B9E456448EE9D39C9` |

The same hashes are recorded in `dist/SHA256SUMS.txt`.

## Owner approval and publication pending

- [ ] Review the prepared source and documentation state; explicitly authorize any commit or push.
- [ ] Confirm that `v1.0.0` is the public release version and authorize creation of the `v1.0.0` tag.
- [ ] Confirm intended release jurisdictions and whether the public GitHub Issues privacy contact is sufficient; obtain any required legal review or private contact details.
- [ ] Decide whether additional clean-machine Windows and physical Android installation/upgrade tests are required before publication.
- [ ] After approval, publish the tag and GitHub Release with the prepared notes and both artifacts.
- [ ] After publication, download each asset from GitHub and compare it with the corresponding `SHA256SUMS.txt` entry.
