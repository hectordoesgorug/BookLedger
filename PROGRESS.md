# Development progress

## Stage 1 — Foundation (in progress)
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
- [x] BookLedger Mobile connection/scan UI simulation, retry rules, and 10-second scan timeout
- [x] Open Library primary metadata lookup with Google Books fallback and per-provider timeouts
- [x] Booktopia HTML provider activated after Open Library and Google Books; it follows only matching ISBN search results, verifies product-page ISBN evidence, and merges supported missing metadata and descriptions without replacing earlier values
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
- [x] Canonical per-copy JPEG filenames and shared staged photo processing for desktop selection and future mobile handoff
- [x] Copy-level Trash, LIFO restore, Clear Trash, explicit recovery retry, protected two-step Purge, and read-only storage verifier
- [x] Provider-derived title normalization with acronym and short-word handling; manual titles remain unchanged
- [x] Backup format minimally includes Trash photo files
- [x] Open Library prefers edition descriptions before notes, excerpts, and linked work descriptions; Google Books scans matching volumes and later ISBN query variants for descriptions without accepting unrelated identifiers
- [x] Full suite after Booktopia integration: `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-booktopia-full-report-final-20261018` — 148 passed; the default pytest temp path is unavailable in this sandbox
- [ ] Live Open Library, Google Books, and Booktopia requests could not be checked because DNS resolution is unavailable in this environment; Booktopia's Terms of Business identify third-party copyright in bibliographic data but do not establish permission for automated metadata retrieval. Manual Windows startup/migration/lifecycle acceptance remains pending
- [ ] Windows packaging and frozen-executable verification (no packaging spec or executable exists)
- [ ] Test GUI manually on Windows (native Windows check pending; installed Tcl/Tk files are incomplete)

## Next stages
1. Visually review the Catalog grid, Inventory table, and Add/Edit layouts on a complete native Windows Tk installation.
2. Add import/export and fuller reports.
3. Expand migration and interrupted-operation recovery tests.
4. Package the stable desktop app.
5. Build the Android companion after desktop stabilization.
- [ ] Connect BookLedger Mobile to real pairing, ISBN scanning, and photo transfer.
