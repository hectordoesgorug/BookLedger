# Development and release status

## v1.1.0 finalization — November 18, 2026

Accepted rc1 binaries are staged unchanged at `dist/v1.1.0/` with official filenames and SHA-256 manifest. Owner physical acceptance and the non-blocking automated geometry exception are recorded in TEST_REPORT.md. Commit/push, annotated tag and GitHub publication await their separate Handover #58 authorizations. No new application development or binary rebuild was performed.

BookLedger v1.0.0 was published on November 16, 2026 as a stable GitHub Release. Annotated tag `v1.0.0` points to `1224f3ec25b8a3715f3b6b4234ed2bf9f180bc5c`. The [Windows portable ZIP](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.0.0/BookLedger-v1.0.0-Windows-x64-Portable.zip), [Android APK](https://github.com/hectordoesgorug/BookLedger/releases/download/v1.0.0/BookLedger-v1.0.0-Android.apk), and checksum manifest are published at the [release page](https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.0.0); the owner confirmed downloading and verifying all three assets. Latest owner-reported physical validation: 15 PASS, 0 FAIL, 0 SKIPPED. Handover #42D is closed. Post-release maintenance and future enhancement planning are active; see the [release checklist](docs/RELEASE_CHECKLIST_v1.0.0.md) and [test report](TEST_REPORT.md).

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
- [ ] At the 2026-11-15 Milestone 5 run, physical end-to-end transfer/cataloging had not yet been performed; the owner later reported passing single/bulk transfer and cataloging with the exact final assets on 2026-11-16 (see [test report](TEST_REPORT.md)). Windows hotspot/mDNS, actual DHCP-change discovery, and native Tk form interaction remain unverified.

## Outstanding acceptance checks

- The 2026-11-15 Windows smoke check used a fresh extraction on the build machine. In the 2026-11-16 owner-reported final-asset session, fresh extraction and launch without Python passed on a Windows 11 laptop; broader device coverage and device/build details were not supplied.
- The 2026-11-15 run did not include physical Android end-to-end transfer. The owner reported that final-asset transfer and cataloging passed on 2026-11-16. Backup/persistence after restart and automatic reconnection after restart were skipped in the initial 2026-11-16 session and reported PASS in a subsequent owner round. The follow-up clarification does not specify whether those reruns used the exact final assets; see [test report](TEST_REPORT.md).
- Windows hotspot/mDNS discovery, actual DHCP-change discovery, and native Tk interaction remain unverified.
- Live metadata provider behavior can change; synthetic fixtures do not establish current provider responses or site markup.

## Post-release issue tracker

GitHub Issues is the primary tracker for development tasks, requirements, acceptance criteria, and issue status. `PROGRESS.md` remains the high-level roadmap and milestone history. Future implementation work should reference the relevant GitHub Issue. Close completed issues in GitHub, and update this file when changes warrant a milestone-level progress update. The following original backlog list retains completed entries for context.

1. [**Dynamic GUI Resizing**](https://github.com/hectordoesgorug/BookLedger/issues/1) (desktop): Adapt Catalog, Inventory, forms, Settings, About, Reports, and other major screens to window resizing. Preserve usable minimum dimensions, spacing, alignment, and appropriate reflow without indiscriminate font scaling.
2. [**Revisit Hardcover and BigBook Providers**](https://github.com/hectordoesgorug/BookLedger/issues/2) (desktop metadata): Reassess lookup reliability, provider behavior, API integration, and field coverage. Do not presume either provider is broken; use current evidence to decide whether behavior should change.
3. [**Single-Instance Desktop Enforcement**](https://github.com/hectordoesgorug/BookLedger/issues/3) (desktop; implemented): Prevent simultaneous instances from using the same portable library and, where feasible, activate the existing window on a second launch. Consider safe locking, distinct library paths, and stale-lock recovery.
4. [**Mobile Photo Background Removal**](https://github.com/hectordoesgorug/BookLedger/issues/4) (Android): Investigate optional background removal for captured cover photos. Prefer offline processing where feasible and preserve original photos.
5. [**Single-Page Mobile Settings**](https://github.com/hectordoesgorug/BookLedger/issues/5) (Android; implemented): Consolidate companion settings into one organized, scrollable page while retaining existing behavior.
6. [**Remove Obsolete Test Secure Storage Button**](https://github.com/hectordoesgorug/BookLedger/issues/6) (Android; implemented): Determine whether the control serves a production purpose. If not, remove the testing UI while preserving production secure-storage behavior and tests.
7. [**Non-AI Book-Description Shortener**](https://github.com/hectordoesgorug/BookLedger/issues/7) (desktop metadata): Investigate deterministic shortening of overly long descriptions that preserves important information and uses no AI service.
8. [**Additional Mobile Camera Controls**](https://github.com/hectordoesgorug/BookLedger/issues/8) (Android; implemented): Consider flash/torch and zoom controls where the camera hardware and APIs support them. Preserve ISBN scanning and cover-photo capture behavior.
9. [**Bulk Metadata Download**](https://github.com/hectordoesgorug/BookLedger/issues/9) (desktop): Allow multiple desktop books to be captured or entered without waiting for each lookup, then retrieve and apply their metadata in a later batch. Mobile batch capture and transfer exist; desktop cataloging and lookup remain one book at a time.
10. [**Merge Libraries**](https://github.com/hectordoesgorug/BookLedger/issues/10) (desktop data management): Import a backup into an existing library with safe identity matching and review instead of replacing the active library. Preserve the local USB handover/backup model; restore currently replaces the active library and does not merge.
