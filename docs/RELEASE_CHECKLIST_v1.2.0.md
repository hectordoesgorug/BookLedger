# BookLedger v1.2.0 release checklist

**Status:** Ready for Physical Acceptance; no release approval or publication.

## Source and version identity

- [x] Readiness audit at `bc66de2e57e5004164e1a622daac2c2bfdbe8fb4` is pushed on `main`.
- [x] Desktop canonical version is `1.2.0`; Windows file metadata uses the canonical version.
- [x] Android declares `1.2.0+3`; application ID remains `com.bookledger.mobile`. The only previously distributed production code confirmed so far is v1.1.0 code 2.
- [x] Existing production signing configuration and keystore are present outside the repository; no credential values are recorded here.
- [ ] Candidate source and exact artifacts reviewed.

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
- [ ] Physical acceptance of the exact candidate recorded separately.
- [ ] v1.1.0 production upgrade, data/pairing preservation, capture, transfer, and installer behaviors remain pending until tested on isolated data.
- [x] Wireless ADB inspection found one authorized Android 16/API 36 device with production `com.bookledger.mobile` version `1.1.0+2`; no install, uninstall, data clear, or app modification was performed.
- [ ] No newer stable release exists to test a v1.2.0-to-later update.

## Distribution safeguards

- [x] README download links remain pointed at the published v1.1.0 assets.
- [x] Historical v1.0.0 and v1.1.0 release records and artifacts are preserved.
- [x] No commit, push, tag, GitHub Release, or issue update is authorized for this candidate-preparation work.
