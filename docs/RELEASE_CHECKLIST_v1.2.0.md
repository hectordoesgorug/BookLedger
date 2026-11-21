# BookLedger v1.2.0 release checklist

**Status:** Published as the stable v1.2.0 release on 2026-11-21; independent post-publication verification is recorded below.

The candidate-preparation sections retain their original time-specific evidence and unchecked acceptance items. The publication record below supersedes only their prepublication status; it does not change historical **PARTIAL**, **SKIPPED**, or unverified results.

## Source and version identity

- [x] Readiness audit at `bc66de2e57e5004164e1a622daac2c2bfdbe8fb4` is pushed on `main`.
- [x] Desktop canonical version is `1.2.0`; Windows file metadata uses the canonical version.
- [x] Android declares `1.2.0+3`; application ID remains `com.bookledger.mobile`. The only previously distributed production code confirmed so far is v1.1.0 code 2.
- [x] Existing production signing configuration and keystore are present outside the repository; no credential values are recorded here.
- [x] Candidate source and exact rc1 artifacts reviewed. The accepted Windows ZIPs contain root and mobile READMEs that still describe v1.1.0 as current; this is a publication documentation blocker for those exact ZIPs. The originals remain unchanged.

## Automated verification

- [x] Desktop full suite: 676 passed, 18 skipped, 0 failed. Tcl/Tk runtime files prevent the skipped UI tests from running.
- [x] Desktop focused update/version/packaging/backup/currency suite: 94 passed, 1 skipped, 0 failed. The skipped Tk update-page test cannot load `tk.tcl`.
- [x] Intake minimum-size geometry regression repeated five times: 5 passed, 0 failed.
- [x] Python compilation and dependency consistency passed.
- [x] Flutter full suite: 169 passed, 0 skipped, 0 failed; focused updater/installer suite: 43 passed.
- [x] Dart formatting: 40 files checked, 0 changed.
- [x] Flutter analysis: 21 informational Material import deprecations, no warnings or errors; exit 1. No Dart sources changed for this candidate version update.
- [x] Android debug smoke build and production release APK build passed with the configured toolchain.

## Signed Android candidate

- [x] Production signing configuration and keystore are externally configured and preserved.
- [x] Release APK signature verifies with APK Signature Scheme v2 and its certificate fingerprint matches the published v1.1.0 APK.
- [x] Package ID, name/code, SDK levels, permissions, ABIs, non-debuggable status, Flutter notices, size, and SHA-256 are recorded in the candidate report.
- [x] The external signer configuration remains outside the repository; package scans found no signing material or personal library data.

## Windows distributions

- [x] Isolated 64-bit CPython 3.14.6 environment matches pinned build requirements; `pip check` passes.
- [x] Portable and Fallback packages built with v1.2.0 executable metadata.
- [x] Both contain the exact verified production APK and required notices, including the candidate Flutter engine license bundle.
- [x] ZIP structure, CRC, contents, personal-data exclusion, and executable versions verified.
- [x] Fresh extractions of both packages launch the v1.2.0 dashboard and close normally.

## Candidate staging and native acceptance

- [x] Standalone APK, both Windows ZIPs, and `SHA256SUMS-rc1.txt` staged under `dist/v1.2.0-rc1/` and verified from final bytes.
- [ ] Full physical acceptance of the exact Windows candidate is complete. Partial PASS/PARTIAL/SKIPPED results are recorded in `docs/RELEASE_CANDIDATE_v1.2.0-rc1.md`; sales workflows, offline behavior, minimum-window review, and some content/restore checks remain untested.
- [x] Isolated v1.1.0-to-v1.2.0 manual replacement checks passed for Portable executable-only replacement and Fallback executable plus complete `_internal/` replacement. Test books, cover photos, and pre-upgrade backups remained visible/present.
- [ ] Customized settings preservation and restoring the pre-upgrade backup after package replacement remain unverified for both Windows package types.
- [x] Read-only wireless ADB preflight confirmed one authorized POCO X6 5G, Android 16/API 36, production `com.bookledger.mobile` v1.1.0+2, and 226 GB free on `/data`.
- [x] After owner approval, `adb install -r` updated the production package in place to v1.2.0+3; Package Manager retained the original first-install time, and the installed APK bytes and signing certificate match the staged candidate.
- [x] Owner reports no issues during additional manual acceptance; scenario coverage was not itemized, so prior **PARTIAL** and **SKIPPED** results remain unchanged.
- [ ] Existing pairing state, settings and captures were not inventoried before the upgrade. The post-upgrade home page showed `Not paired`; prior pairing preservation cannot be determined. No captures were created or modified.
- [ ] Mobile Settings update control, live release check, network-failure handling, repeated checks, light/dark presentation, capture transfer and in-app installer handoff remain unverified.
- [x] The Portable candidate's live stable-release check reported v1.1.0 as current and no newer stable release to test an update to.

## Final package review — November 21, 2026

- [x] Recomputed SHA-256 values for all accepted rc1 artifacts; all match `SHA256SUMS-rc1.txt`. ZIP CRC/layout, embedded APK identity, executable versions, license notices and data/signing-material exclusions were checked.
- [x] Root and Android READMEs were updated to identify v1.2.0 and its final asset names without claiming publication. Links to documentation omitted from the archives now target the versioned GitHub files. Proposed repackaged Windows ZIPs use the corrected documents; the standalone APK is byte-identical to the accepted candidate.
- [x] Owner approved the corrected final-named Windows ZIPs, unchanged production APK, and new SHA-256 manifest for final artifact preparation. Accepted rc1 files remain preserved; approved final files are staged at `dist/v1.2.0/`.
- [ ] Fresh-extraction visible-window verification of the corrected Windows ZIPs is **SKIPPED**. Process-start attempts did not capture a window; a follow-up window-enumeration command was blocked by execution policy. This limitation remains disclosed and was accepted for final artifact preparation.

## Final release-gate assessment

- [x] No application defect was identified in the recorded automated checks or directly exercised Windows and Android behaviors.
- [ ] Full physical scenario coverage is not claimed. Windows sales transactions, report accuracy, offline behavior, minimum-window reachability, selected Fallback features, changed-settings migration and post-upgrade backup restoration remain **SKIPPED** or unverified.
- [ ] Android pairing, settings and capture baselines were not recorded before update; the post-update app showed `Not paired`. Preservation of those previous states cannot be determined. Mobile update UI, network failure, repeated checks, theme presentation, transfer and in-app installer remain unverified.
- [x] Existing physical-test exceptions remain documented and were assessed as nonblocking for publication; prior **PARTIAL**, **SKIPPED**, and unverified results remain unchanged. The stale bundled README issue is corrected in the owner-approved final ZIPs; the original rc1 ZIPs remain unchanged and are not staged as final assets.
- [x] Publication and post-publication verification are recorded below.

## Distribution safeguards

- [x] README download links use final v1.2.0 filenames. The versioned README links and public release URLs were checked after publication; all returned HTTP 200. The v1.1.0 release assets remain available historically.
- [x] Historical v1.0.0 and v1.1.0 release records and artifacts are preserved.
- [x] The publication added only the authorized annotated tag and GitHub Release; no source commit or issue was changed. The v1.2.0 release tag targets the approved source commit.

## Stable release publication and independent verification — 2026-11-21

- [x] Stable GitHub Release [BookLedger v1.2.0](https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.2.0) was published on 2026-11-21, is not a draft or prerelease, and is the latest stable release.
- [x] Annotated tag `v1.2.0` (tag object `8e4ae20ff0ddb83195bf239e60a66fce38ba004c`) resolves to approved commit `3561873822e41c30aaa5445aa37fdaac7a4382c6`. At publication verification, `main` and `origin/main` both matched that commit.
- [x] All four public assets were downloaded into `build/v1.2.0-public-verification/`; downloaded sizes and SHA-256 values match both the approved values and GitHub's asset digests.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `BookLedger-v1.2.0-Windows-x64-Portable.zip` | 60,220,092 | `154584d4a2485a74b96a9250d5481989cd49f4ca37e02a3e1e72abbfae148b5a` |
| `BookLedger-v1.2.0-Windows-x64-Fallback.zip` | 61,053,994 | `46839ebb5ebe26a4c330f27c69521b752e7d0d224f6b69f3308ed7af97a24da0` |
| `BookLedger-v1.2.0-Android.apk` | 70,915,414 | `73cc232c1bed24cdf40f96b6d8e3b3c62b9ec774d02b9082d1e328db117a0752` |
| `SHA256SUMS.txt` | 317 | `021c02de6d10d065e83d6a4920f1e971fdf5a38601121b7c9b6808e214739ed2` |

- [x] The public checksum manifest contains matching entries for the Portable ZIP, Fallback ZIP, and APK. Both ZIPs pass CRC validation and have the expected single-root layouts (`BookLedger/`, 75 entries; `Fallback/`, 1,116 entries).
- [x] The APK reports package `com.bookledger.mobile`, version `1.2.0`, version code `3`; `apksigner` verifies it and reports the production certificate SHA-256 `539e4a74e133604ec420c1d3a19584200e2a926f19f0ba7b4652de0bb7a85f3d`.
- [x] All 16 v1.2.0-tagged file, release-page, and asset URLs referenced by the root and Android READMEs returned HTTP 200. The release candidate report and checklist links also returned HTTP 200.
- [ ] Visible-window verification of the corrected Windows ZIPs remains **SKIPPED** as documented above; no publication step changes that result.
