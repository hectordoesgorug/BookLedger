# BookLedger v1.2.0 release checklist

**Status:** Not Ready for Publication Authorization; corrected Windows packages require owner review.

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
- [ ] Owner has reviewed and accepted the proposed final-named Windows ZIPs and their new hashes. Until then, neither proposed ZIP supersedes the accepted rc1 file.
- [ ] Fresh extraction and launch of the corrected proposed Windows ZIPs remain pending owner acceptance of those replacements.

## Final release-gate assessment

- [x] No application defect was identified in the recorded automated checks or directly exercised Windows and Android behaviors.
- [ ] Full physical scenario coverage is not claimed. Windows sales transactions, report accuracy, offline behavior, minimum-window reachability, selected Fallback features, changed-settings migration and post-upgrade backup restoration remain **SKIPPED** or unverified.
- [ ] Android pairing, settings and capture baselines were not recorded before update; the post-update app showed `Not paired`. Preservation of those previous states cannot be determined. Mobile update UI, network failure, repeated checks, theme presentation, transfer and in-app installer remain unverified.
- [ ] Existing physical-test exceptions remain documented and are assessed as nonblocking if accepted by the owner. Independently, stale bundled README content blocks publication of the current accepted Windows ZIPs until corrected proposed packages are reviewed and accepted.
- [ ] Release approval and publication have not been granted or performed.

## Distribution safeguards

- [ ] README download links use final v1.2.0 filenames but resolve only after the release is published; the unchanged v1.1.0 release assets remain available historically.
- [x] Historical v1.0.0 and v1.1.0 release records and artifacts are preserved.
- [x] No commit, push, tag, GitHub Release, or issue update is authorized for this candidate-preparation work.
