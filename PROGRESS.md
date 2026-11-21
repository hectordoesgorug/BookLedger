# Development and release status

## v1.2.0 stable release — November 21, 2026

BookLedger v1.2.0 was published as the latest stable release on November 21, 2026. Annotated tag `v1.2.0` targets `3561873822e41c30aaa5445aa37fdaac7a4382c6`; `main` and `origin/main` were at that commit during publication verification. The [GitHub Release](https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.2.0) contains the four approved assets, independently downloaded and verified against their SHA-256 values. The accepted rc1 artifacts remain unchanged at `dist/v1.2.0-rc1/`. Visible-window verification of the corrected Windows ZIPs remains **SKIPPED**; physical acceptance limits remain in the [release checklist](docs/RELEASE_CHECKLIST_v1.2.0.md), [release notes](docs/RELEASE_NOTES_v1.2.0.md), and [candidate report](docs/RELEASE_CANDIDATE_v1.2.0-rc1.md). Exact asset identities and verification are recorded in [TEST_REPORT.md](TEST_REPORT.md).

## Update installation — November 21, 2026

Windows keeps verified downloads manual and now shows package-specific instructions that extract to a separate folder, replace only the Portable executable or the Fallback executable/runtime pair, and preserve library files. Android exposes **Install Update** only after the verified private APK is rechecked for its SHA-256, package ID, and higher version code. It uses Android's package installer with a temporary read-only FileProvider URI grant, per-source install permission guidance, explicit capture-loss confirmation, and post-return version confirmation. No automatic Windows installer, custom manifest-signing framework, silent Android install, or data cleanup was added. The published v1.1.0 release does not contain this updater; a newer production-signed native installation remains unverified.

Verification: Android full Flutter suite **169 passed**; focused update suites **43 passed**; debug APK build passed; Dart formatting checked 40 files with no changes. Flutter analysis exited 1 for **21 informational Material import deprecations**, with no warnings or errors. Focused desktop update tests: **37 passed, 1 Tcl/Tk skip**. Python compilation and `git diff --check` passed. The full desktop suite had **676 passed, 17 skipped, 1 failed** in the known minimum-size intake geometry assertion. No Android device tooling (`adb`) was available. Exact evidence and limitations are in [TEST_REPORT.md](TEST_REPORT.md).

At the time of this historical update-system record, the update installation changes were local. They were subsequently committed and pushed before the v1.2.0 readiness audit. Candidate preparation and publication are recorded separately above; this historical entry describes the state at the time and is not a current Git-status report.

## Update discovery and native UI — November 20–21, 2026 (historical record)

Native source-Windows and isolated debug-Android acceptance now covers light/dark links and dialogs, current v1.1.0 release information, network failures, retry/Back behavior and normal navigation. Native inspection found the Dashboard could hide the status row; the row now reserves its space before the workspace. Desktop **Visit GitHub** was added directly below About, with shared hyperlink styling and keyboard support. Final regressions: **652 desktop passed / 19 Tcl/Tk skipped / 0 failed**, **156 Flutter passed**, and a successful normal Android debug build. Analysis still exits 1 for **21 informational SDK deprecations**. The temporary Android acceptance package was removed after testing; the installed production app was preserved. Details and data-preservation limits are recorded in [TEST_REPORT.md](TEST_REPORT.md).

Earlier verification stabilization recorded **650 desktop tests passed / 18 Tcl/Tk skips / 0 failures**, **156 Flutter tests passed**, three consecutive camera/banner/Settings regression passes and a successful Android debug build with the targeted AGP **9.1.1** patch. Those geometry, camera fixture cleanup and banner decode corrections changed tests without changing production UI behavior at that stage. Native checks then identified the separate workspace/status layout defect corrected above. See [TEST_REPORT.md](TEST_REPORT.md) for exact commands and preserved earlier failures.

Local source changes implement explicit stable GitHub release checks for desktop and Android for [Issue #22](https://github.com/hectordoesgorug/BookLedger/issues/22). The desktop link sits beside the workspace status; Android's action follows Clear Data. Both show versions, release notes, errors and unsupported builds without automatic checking or data/settings changes. These changes are not in the published v1.1.0 binaries.

The previous design proposal for staged Windows activation and custom signed manifests has been superseded by the simpler manual Windows and Android system-installer workflow in [docs/UPDATE_SYSTEM.md](docs/UPDATE_SYSTEM.md). Historical download verification and UI outcomes remain in [TEST_REPORT.md](TEST_REPORT.md).

## v1.1.0 finalization — November 18, 2026

Accepted rc1 binaries are staged unchanged at `dist/v1.1.0/` with official filenames and SHA-256 manifest. Reported physical acceptance and the non-blocking automated geometry exception are recorded in TEST_REPORT.md. The reviewed documentation was committed and pushed before the annotated tag and stable GitHub Release were published. All four published downloads passed independent size/SHA-256 verification. No new application development or binary rebuild was performed.

BookLedger v1.0.0 was published on November 16, 2026 as a stable GitHub Release. Annotated tag `v1.0.0` points to `1224f3ec25b8a3715f3b6b4234ed2bf9f180bc5c`. The [Windows portable ZIP](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.0.0/BookLedger-v1.0.0-Windows-x64-Portable.zip), [Android APK](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.0.0/BookLedger-v1.0.0-Android.apk), and checksum manifest are published at the [release page](https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.0.0); the November 16 report records all three assets as downloaded and verified. Latest reported physical validation: 15 PASS, 0 FAIL, 0 SKIPPED. Post-release maintenance and future enhancement planning are active; see the [release checklist](docs/RELEASE_CHECKLIST_v1.0.0.md) and [test report](TEST_REPORT.md).

## Android Issue #16 (November 17, 2026; implemented)

Implemented the fixed 2×2 intake actions, canvas identifier choices, automatic photograph readiness, photo-preserving Change/Retake, and next-book scanning after successful Bulk Queue. Transfer protocol and acknowledgment rules are unchanged. The implementation and subsequent control refinements are committed on `main`; they have not been published in a new release. Automated verification and device limitations are recorded in TEST_REPORT.md and the Android release-readiness audit.

Post-release Android issues #6, #5, #8, #19, and #16 are implemented in the current source. Their release readiness, including remaining live-transfer and production-upgrade checks, is assessed in [the November 17 Android audit](docs/ANDROID_RELEASE_READINESS_AUDIT.md).

## Implemented desktop milestones
- [x] Modular package structure
- [x] SQLite schema for bibliographic records, copies, sales, and metadata
- [x] Catalog service and core validation
- [x] ISBN check digit validation with override support
- [x] Photo compression service
- [x] Optional Google Books adapter
- [x] Main Tkinter shell and initial screens
- [x] Local backup archive with integrity verification
- [x] Cataloging specification and README
- [x] Backup restoration service and Settings UI
- [x] Windows launcher and development extra documented; pytest remains a development dependency
- [x] Close SQLite connections reliably after success and exceptions; verify backup creation and restoration on Windows
- [x] Add Book two-panel layout with independently scrolling form, photo preview, simulation status, and two-row actions
- [x] Field-specific validation messages below inputs with valid-value clearing and finite positive price validation
- [x] Initial BookLedger Mobile connection/scan UI simulation, retry rules, and timeout behavior; the implemented companion and transfer workflow is recorded below
- [x] Open Library primary metadata lookup with Google Books fallback and per-provider timeouts
- [x] Booktopia HTML provider activated after Open Library and Google Books; it follows matching ISBN search results and uses a canonical-redirected direct ISBN fallback on HTTP search errors, verifies product-page ISBN evidence, and merges supported missing metadata and descriptions without replacing earlier values
- [x] Archive.org Advanced Search provider added after Google Books and before Booktopia by default, with bounded candidate checks, per-provider ISBN Lookup Test support, and legacy provider-order preservation
- [x] Open Library no longer supplies Book Details/Synopsis from descriptions, notes, excerpts, or linked works while retaining supported bibliographic fields
- [x] Booktopia accepts an explicitly tab-linked Description panel or a matching schema.org Book description after rejecting known bibliographic notes and retailer boilerplate; generic meta descriptions and unassociated `itemprop="description"` are ignored
- [x] Service validation rejects non-finite or unrepresentable copy and sale prices and unapproved genres
- [x] Dashboard distinguishes all physical copies from distinct bibliographic records and status counts
- [x] Catalog photo-card grid and sortable Inventory table share copy records and ordered Genre, Condition, Location, Status filters
- [x] Sales view shows Date Sold and Price only; revenue summaries use retained sale history entries
- [x] Treeview double-click handlers reject destroyed/stale views and open the clicked Copy ID
- [x] Partial Open Library metadata is merged with Google Books fallback without replacing available values; forms preserve manual values and show missing optional data
- [x] Optional Google Books API key and connectivity test in Settings; key stored outside portable backups with its plain-text tradeoff documented
- [x] Canonical location registry with v1 data migration, add/rename propagation, safe deletion rules, and form/filter choices
- [x] Catalog double-click opens read-only selected-copy details; Inventory double-click retains selected-copy editing
- [x] Catalog and Inventory share an eight-option right-click menu, target the copy under the pointer, and disable its current status action
- [x] Status transition confirmation policy, automatic local-date sale capture, and sold-price locking implemented
- [x] Sold transitions append sale history; reversing status preserves recorded revenue, and re-selling creates another retained event
- [x] Sold copies have gray thumbnail tint/red SOLD label and sort after non-sold copies in Catalog and Inventory
- [x] Add/Edit use one Price field and no Status or Sale Details controls; status changes are context-menu only
- [x] Google Books API Settings entry shows config status and supports connectivity test without requiring a key
- [x] v1-to-v3 database migration preserves location and sale values while enabling multiple sale events per copy
- [x] Portable `data/` paths, root-level backups, legacy storage copy/verification, conflict detection, and recovery rename
- [x] Schema v4 migration adds Trash and durable storage-operation records while preserving copy identity and relationships
- [x] Canonical per-copy JPEG filenames and shared staged photo processing for desktop selection and incoming mobile photos
- [x] Copy-level Trash, LIFO restore, Clear Trash, explicit recovery retry, protected two-step Purge, and read-only storage verifier
- [x] Provider-derived title normalization with acronym and short-word handling; manual titles remain unchanged
- [x] Backup format minimally includes Trash photo files
- [x] Open Library synopsis candidates are excluded; Google Books scans matching volumes and later ISBN query variants for descriptions without accepting unrelated identifiers
- [x] Full suite after Booktopia integration: `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-booktopia-full-report-final-20261018` — 148 passed; the default pytest temp path is unavailable in this sandbox
- [x] Booktopia synopsis regression and full suite: 59 focused tests passed; full suite `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-booktopia-synopsis-full` — 149 passed, 1 Tk display test skipped because Tcl/Tk is incomplete
- [x] Latest synopsis policy run: focused provider tests 64 passed; full suite 155 passed with no skips; intake UI tests 18 passed with no skips; compileall and `git diff --check` passed
- [x] Booktopia error-response bodies are read within the existing size limit and accepted only for a canonical requested-ISBN product URL with matching page ISBN evidence and supported metadata; unverified/error-only bodies retain provider errors
- [x] If Booktopia's ISBN search returns an HTTP error without a verified product page, the provider makes one direct ISBN URL request and accepts data only after a same-site redirect to a canonical product URL with matching page ISBN evidence and supported metadata
- [x] Direct ISBN fallback regression and full suite: 36 Booktopia tests passed; `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-direct-isbn-full-final2` — 160 passed, 1 skipped because Tcl/Tk is incomplete; compileall and `git diff --check` passed
- [ ] Test GUI manually on Windows (native Windows check pending; installed Tcl/Tk files are incomplete)

## Configurable metadata provider registry
- [x] Central registry for Open Library, Google Books, Archive.org, and Booktopia with implemented status and provider field support
- [x] Settings controls for enable/disable, functional drag-and-drop priority, and Restore Defaults
- [x] Versioned root `config.json`, per-user fallback for read-only roots, malformed-config preservation, and Purge persistence
- [x] Configured lookup order with field-level first-value-wins merge and completion at title, author, genre, publisher, and publication year; edition, format, synopsis, and page count remain optional
- [x] Focused tests: 91 passed; full suite: 170 passed, 2 Tk tests skipped because Tcl/Tk files are missing; compileall and `git diff --check` passed
- [ ] Native Tk UI runtime acceptance remains pending because the installed Tcl/Tk files are incomplete

## Poster creation
- [x] Poster Setup canvas with background upload, movable/resizable book fields, font-size control, and reusable sequential presets
- [x] Copy context menu exports a copy-specific PNG using normalized template coordinates, title shortening rules, current copy price, and replacement confirmation
- [x] Schema v8 stores template definitions; relative background paths support portable app assets and a managed-data fallback
- [x] Backups/restores include poster templates, managed backgrounds, and generated posters; Purge removes poster-owned files while preserving unrelated app assets
- [ ] Manual Windows visual inspection remains pending; this environment's Tk tests are skipped when Tcl/Tk is incomplete

## Mobile companion and transfer
- [x] Local-only desktop pairing/connection API, QR/manual pairing, DPAPI-protected desktop token, Android secure storage, DNS-SD/NSD discovery, and reconnection
- [x] Poco X6 Wi-Fi pairing, authentication, process restart persistence, desktop restart recovery, and Wi-Fi interruption recovery
- [x] Mobile ISBN choices (scan barcode, manual numeric entry, or no ISBN), UUID capture identity, single and batch transfer with per-capture acknowledgments and retry of unacknowledged captures
- [x] Desktop validates and atomically stages incoming JPEGs under `data/incoming/`; transfer retries are idempotent by capture UUID
- [x] Incoming captures remain outside ordinary inventory until cataloged through the existing Add Book form; saved copies retain the incoming UUID to recover safely after restart
- [x] Sequential cataloging, explicit discard, incomplete-batch recovery, and Add/Edit locking during active reception
- [ ] At the 2026-11-15 Milestone 5 run, physical end-to-end transfer/cataloging had not yet been performed; a subsequent November 16 report records successful Single/Bulk transfer and cataloging with the exact final assets (see [test report](TEST_REPORT.md)). Windows hotspot/mDNS, actual DHCP-change discovery, and native Tk form interaction remain unverified.

## Outstanding acceptance checks

- The 2026-11-15 Windows smoke check used a fresh extraction on the build machine. The reported November 16 final-asset session passed fresh extraction and launch without Python on a Windows 11 laptop; broader device coverage and device/build details were not supplied.
- The 2026-11-15 run did not include physical Android end-to-end transfer. The November 16 report records successful final-asset transfer and cataloging. Backup/persistence after restart and automatic reconnection after restart were skipped in the initial session and reported PASS in a subsequent round. The follow-up clarification does not specify whether those reruns used the exact final assets; see [test report](TEST_REPORT.md).
- Windows hotspot/mDNS discovery, actual DHCP-change discovery, and native Tk interaction remain unverified.
- Live metadata provider behavior can change; synthetic fixtures do not establish current provider responses or site markup.

## Post-release issue tracker

GitHub Issues is the primary tracker for development tasks, requirements, acceptance criteria, and issue status. `PROGRESS.md` remains the high-level roadmap and milestone history. Future implementation work should reference the relevant GitHub Issue. Close completed issues in GitHub, and update this file when changes warrant a milestone-level progress update. The following original backlog list retains completed entries for context.

1. [**Dynamic GUI Resizing**](https://github.com/hectordoesgorug/BookLedger/issues/1) (desktop): Adapt Catalog, Inventory, forms, Settings, About, Reports, and other major screens to window resizing. Preserve usable minimum dimensions, spacing, alignment, and appropriate reflow without indiscriminate font scaling.
2. [**Metadata Provider Reassessment**](https://github.com/hectordoesgorug/BookLedger/issues/2) (desktop metadata; open): Hardcover and Bigbook compatibility repairs are implemented and sampled live. Fresh provider settings enable Hardcover immediately ahead of Booktopia; Bigbook remains optional and disabled, and saved preferences are preserved. [ISBNdb, Goodreads, and WorldCat feasibility findings](docs/METADATA_PROVIDER_FEASIBILITY.md) await review and an agreed disposition before closing the expanded issue. OAuth remains a separate assessment.
3. [**Single-Instance Desktop Enforcement**](https://github.com/hectordoesgorug/BookLedger/issues/3) (desktop; implemented): Prevent simultaneous instances from using the same portable library and, where feasible, activate the existing window on a second launch. Consider safe locking, distinct library paths, and stale-lock recovery.
4. [**Mobile Photo Background Removal**](https://github.com/hectordoesgorug/BookLedger/issues/4) (Android): Investigate optional background removal for captured cover photos. Prefer offline processing where feasible and preserve original photos.
5. [**Single-Page Mobile Settings**](https://github.com/hectordoesgorug/BookLedger/issues/5) (Android; implemented): Consolidate companion settings into one organized, scrollable page while retaining existing behavior.
6. [**Remove Obsolete Test Secure Storage Button**](https://github.com/hectordoesgorug/BookLedger/issues/6) (Android; implemented): Determine whether the control serves a production purpose. If not, remove the testing UI while preserving production secure-storage behavior and tests.
7. [**Non-AI Book-Description Shortener**](https://github.com/hectordoesgorug/BookLedger/issues/7) (desktop metadata): Investigate deterministic shortening of overly long descriptions that preserves important information and uses no AI service.
8. [**Additional Mobile Camera Controls**](https://github.com/hectordoesgorug/BookLedger/issues/8) (Android; implemented): Consider flash/torch and zoom controls where the camera hardware and APIs support them. Preserve ISBN scanning and cover-photo capture behavior.
9. [**Bulk Metadata Download**](https://github.com/hectordoesgorug/BookLedger/issues/9) (desktop): Allow multiple desktop books to be captured or entered without waiting for each lookup, then retrieve and apply their metadata in a later batch. Mobile batch capture and transfer exist; desktop cataloging and lookup remain one book at a time.
10. [**Merge Libraries**](https://github.com/hectordoesgorug/BookLedger/issues/10) (desktop data management): Import a backup into an existing library with safe identity matching and review instead of replacing the active library. Preserve the local USB handover/backup model; restore currently replaces the active library and does not merge.

## Configurable Currency and SRP — Issue #20

Implemented in source; release and Git operations remain separate. Currency defaults to PHP, persists in SQLite with a configuration mirror, and supports the 20 validated Frankfurter codes. Users can change notation without changing numeric values or explicitly convert retained asking prices, sale history (including voided events), and SRPs with a dated rate, recovery backup, atomic database transaction, and conversion audit. Currency formatting uses the code and symbol with two decimals. Automated SRP remains unintegrated: Google Books list prices describe Google eBookstore availability and the bounded live ISBN checks were rate limited; no physical-edition list-price source was verified. November 20 verification: full suite **534 passed, 18 skipped**; focused currency/poster/app tests **97 passed, 1 skipped**; live Frankfurter pair response compatibility checked. See [test report](TEST_REPORT.md) for details and limits.
