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
- [x] Owner-reported final physical smoke session (2026-11-16) used the exact verified v1.0.0 release assets: 13 PASS, 2 SKIPPED, 0 FAIL. The Windows 11 laptop fresh-extraction/launch, core desktop workflows, Android installation and companion workflows, pairing, single/bulk transfer, cataloging, and duplicate handling were reported successful. Device-specific details and whether Android was a fresh install or upgrade were not supplied. See `TEST_REPORT.md` for the full matrix and limitations.
- [x] The owner intentionally skipped backup/persistence after restart and automatic reconnection after restart in the final physical session, reporting that both had been rigorously tested previously. They remain SKIPPED for this session, not known defects or wholly untested features. Historical evidence does not establish these scenarios on the exact final release assets.
- [x] Privacy notice, third-party notices, and companion distribution materials are present.
- [x] Focused release-version and packaging tests, plus the full Python suite, passed.
- [x] No local or remote `v1.0.0` tag was present during this preparation; GitHub currently lists no Releases.

## Prepared files

| File | Size | SHA-256 |
| --- | ---: | --- |
| `BookLedger-v1.0.0-Windows-x64-Portable.zip` | 60,086,257 bytes | `339AEBED62A374C4BBBCAD4AF05FB9AE44C5C9C4FA830E94C85B1AC6E670AF50` |
| `BookLedger-v1.0.0-Android.apk` | 71,616,886 bytes | `C9C82CC92D67F055ED9C2C232FC2294F94AF20C57173ED5B9E456448EE9D39C9` |
| `SHA256SUMS.txt` | 205 bytes | `D29486F169997730764350005002FAB63FB0DEE3A57FFF8AB4441C057BCA73F3` |

The same hashes are recorded in `dist/SHA256SUMS.txt`.

## Owner approval and publication pending

- [ ] Review the prepared source and documentation state; explicitly authorize any commit or push.
- [ ] Confirm that `v1.0.0` is the public release version and authorize creation of the `v1.0.0` tag.
- [x] Owner selected GitHub Issues as the public contact route and accepted the existing disclosures without asserting jurisdiction-specific legal compliance. Legal compliance has not been established.
- [x] The public GitHub About description matches the approved owner-provided wording (checked 2026-11-16).
- [x] Owner accepted the two final-session skips as residual risks. The owner-reported physical test record is documented above and in `TEST_REPORT.md`; the two scenarios remain unverified on the exact final release assets.
- [ ] After approval, publish the tag and GitHub Release with the prepared notes and both artifacts.
- [ ] After publication, download each asset from GitHub and compare it with the corresponding `SHA256SUMS.txt` entry.
