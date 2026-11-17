# BookLedger v1.1.0 release checklist

**Status:** Internal v1.1.0-rc1 preparation; unpublished. See [candidate report](RELEASE_CANDIDATE_v1.1.0-rc1.md) for exact results, evidence paths, hashes, warnings, and readiness classification. Unchecked items are PENDING unless stated otherwise. Historical v1.0.0 records remain unchanged.

## Source and identity

- [x] Starting clean `main`: `8b4b904d83627c4b11ae749dd83d32bc8b46d8bc`; local `origin/main` and queried remote match.
- [x] Handover #56 documentation and post-v1.0.0 changes inspected; historical tag peels to `1224f3ec25b8a3715f3b6b4234ed2bf9f180bc5c`.
- [x] Canonical desktop version is `1.1.0`; setuptools metadata and desktop footer use that source.
- [x] Android declaration is `1.1.0+2`; application ID remains `com.bookledger.mobile`; About reads `BuildConfig.VERSION_NAME`.
- [x] Changelog and draft GitHub release notes prepared and labeled unpublished.
- [ ] Final source changes reviewed and authorized for commit by owner.

## Automated verification

- [x] Focused version/packaging suite: 6 passed.
- [ ] Desktop full suite has no unresolved failures. Initial candidate run: 516 passed, 18 skipped, 1 failed; preview resize regression also failed alone. See report.
- [x] Flutter tests: 126 passed, 0 failed, 0 skipped.
- [x] Flutter analysis: no issues.
- [x] Dart formatting: 35 files, 0 changed.
- [x] Migration and backup/restore focused compatibility: 83 passed on disposable data.
- [x] Final `git diff --check` passed.

## Signed Android candidate

- [x] Existing external signing system used without credential changes.
- [x] Release signature integrity verified by Android SDK tools (v2).
- [x] Certificate SHA-256 matches historical production APK.
- [x] APK ID, version name/code, permissions, SDK levels, and non-debuggable flag inspected.
- [x] Exact release APK notices and resolved release dependency graph inspected; eight existing Maven POM license gaps are documented for owner review.
- [x] Standalone APK byte size and SHA-256 recorded.

## Windows packages and distribution integrity

- [x] Pinned Windows x64 build environment checked without dependency upgrades.
- [x] One-file build completed through established build script.
- [x] One-folder fallback built from existing specification.
- [x] Both executable FileVersion/ProductVersion resources verified as `1.1.0`.
- [x] Both final ZIPs pass CRC/integrity and structure checks.
- [x] Both embedded APKs are byte-identical to the verified standalone signed candidate.
- [x] Project license, privacy notice, third-party notices, Android engine/Apache licenses, Python/Tcl/Tk and runtime notices included.
- [x] Zeroconf is distributed as replaceable sibling source with COPYING.
- [x] No user databases, private configuration, signing properties, keystores, or personal files included.
- [x] Disposable extractions of both final ZIPs observed launching and exiting on the build machine for 12 seconds.
- [x] Versioned final candidates and SHA-256 manifest verified from final bytes.
- [x] Existing v1.0.0 archives, APK, checksum manifest, tag, and historical release documents verified unchanged.

## Owner physical acceptance — all PENDING for this exact candidate

Record artifact SHA-256, machine/device model, OS/build, date, tester, and PASS/FAIL/SKIPPED for every scenario. Use only disposable library data for acceptance. The report identifies exact artifact paths. Prior debug checks and owner reports do not complete these boxes.

### Windows — test both Portable and Fallback ZIPs

- [ ] Fresh extraction; launch and normal exit; no Python installation required on a second Windows 11 x64 machine.
- [ ] Version/About/footer reads `1.1.0`; navigate Catalog and Inventory.
- [ ] Add/edit/search subtitles; check short/long Catalog titles, Inventory and Details; resize photo previews.
- [ ] Catalog sorting/card sizing and Sales transitions/history.
- [ ] Backup and restore a disposable library; restart and verify photos, subtitles, copy IDs, sales, and recovery archive.
- [ ] Same-library second instance rejected; separate extracted library works independently.
- [ ] Mobile App Setup status and APK export; exported SHA-256 matches standalone candidate.
- [ ] One-file and one-folder startup, paths, settings persistence, and exit behavior.

### Android — exact production-signed rc1 APK

- [ ] About and home version read `1.1.0`; bounded repeated cold/warm startup observations with timings; record any ANR and logs.
- [ ] Real ISBN scan, manual ISBN, and No ISBN.
- [ ] Take Photo, Change, canceled/successful Retake; preserve original photo until replacement succeeds.
- [ ] Torch, supported zoom stops, guide modes, and remembered preferences.
- [ ] Single Entry Send and desktop acknowledgment.
- [ ] Five-entry Bulk capture/transfer, entry ordering, capture IDs, and automatic scanner advancement.
- [ ] Partial-batch early completion; capacity 20 if practical (otherwise record SKIPPED).
- [ ] Reconnect, retry after interruption, and background/foreground recovery.
- [ ] Confirm session-only capture limitation is understood; do not treat process-kill recovery as implemented.

### Desktop/Android integration

- [ ] Authenticated QR/manual pairing to a disposable library.
- [ ] Single and Bulk transfer acknowledged only after durable receipt; catalog each on desktop.
- [ ] Ordering/capture IDs preserved; duplicate retry does not create duplicates.
- [ ] Interrupt connection/acknowledgment, reconnect, retry, and verify cleanup only after success.

### Android in-place upgrade

- [ ] Begin with production-signed v1.0.0 (`com.bookledger.mobile`, code 1, production certificate); record existing settings/pairing.
- [ ] Install the exact production-signed rc1 APK (code 2) in place with owner authorization; do not uninstall or clear data.
- [ ] Verify settings and pairing preserved, version/About, scanning, capture, reconnection, and transfers.

The November 17 audit left a debug-signed app installed. A debug installation is not a production upgrade baseline and may reject the production certificate. Do not resolve this by automatically uninstalling or clearing data; the owner must arrange an appropriate production baseline/device.

## Owner decision and publication — intentionally PENDING

- [ ] Codigo review completed; unresolved automated failure and warnings dispositioned.
- [ ] Owner physical acceptance completed on exact candidate artifacts.
- [ ] Owner accepts session-only captures and known limitations; startup/upgrade/integration concerns resolved.
- [ ] Owner reviews license/privacy material and intended distribution requirements; technical checks are not legal clearance.
- [ ] Owner approves release and separately authorizes commit/push.
- [ ] Owner separately approves Git tag creation/push from reviewed source.
- [ ] Owner separately authorizes GitHub Release publication and public asset upload.
- [ ] Post-publication assets downloaded and SHA-256 verified against approved final manifest.

No commit, push, tag, publication, candidate installation, cleanup, or historical-asset replacement is authorized by completing this preparation checklist.
