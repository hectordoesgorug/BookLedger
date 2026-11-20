# BookLedger v1.0.0 Release Checklist

This checklist records v1.0.0 preparation and publication. Historical preparation checks retain the state that applied when each check was performed.

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
- [x] The reported final-asset physical smoke session (2026-11-16) used the exact verified v1.0.0 release files: 13 PASS, 2 SKIPPED, 0 FAIL. Windows and Android core workflows, pairing, transfer, cataloging, and duplicate handling were reported successful. Device-specific details and whether Android was a fresh install or upgrade were not supplied.
- [x] In a subsequent reported round on 2026-11-16, both previously skipped scenarios—Windows backup/persistence after restart and Android/desktop automatic reconnection after restart—passed. The latest cumulative result is 15 PASS, 0 FAIL, 0 SKIPPED; the original session's 13 PASS / 2 SKIPPED record remains historical. The follow-up clarification does not specify whether these reruns used the exact final release assets. See `TEST_REPORT.md` for details and limits.
- [x] Privacy notice, third-party notices, and companion distribution materials are present.
- [x] Focused release-version and packaging tests, plus the full Python suite, passed.
- [x] No local or remote `v1.0.0` tag or GitHub Release existed during initial preparation; publication is recorded below.

## Prepared files

| File | Size | SHA-256 |
| --- | ---: | --- |
| `BookLedger-v1.0.0-Windows-x64-Portable.zip` | 60,086,257 bytes | `339AEBED62A374C4BBBCAD4AF05FB9AE44C5C9C4FA830E94C85B1AC6E670AF50` |
| `BookLedger-v1.0.0-Android.apk` | 71,616,886 bytes | `C9C82CC92D67F055ED9C2C232FC2294F94AF20C57173ED5B9E456448EE9D39C9` |
| `SHA256SUMS.txt` | 205 bytes | `D29486F169997730764350005002FAB63FB0DEE3A57FFF8AB4441C057BCA73F3` |

The same hashes are recorded in `dist/SHA256SUMS.txt`.

## Publication completed

- [x] Release review and publication approval were completed.
- [x] The annotated `v1.0.0` tag points to `1224f3ec25b8a3715f3b6b4234ed2bf9f180bc5c`.
- [x] Public stable GitHub Release published on November 16, 2026: [BookLedger v1.0.0](https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.0.0). It is not a draft or prerelease.
- [x] All three release assets were downloaded and their SHA-256 values checked against `SHA256SUMS.txt`.
- [x] Latest reported physical validation: 15 PASS, 0 FAIL, 0 SKIPPED. The earlier 13 PASS / 2 SKIPPED session and follow-up remain in `TEST_REPORT.md`.
- [x] GitHub Issues was selected as the public contact route; the existing disclosures were accepted without asserting jurisdiction-specific legal compliance. Legal compliance has not been established.
- [x] The public GitHub About description matches the approved wording (checked 2026-11-16).
- [x] Release publication is complete. Post-release maintenance and future enhancement planning are active.
