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
- [x] Delete Book and Create Poster menu entries are present; deletion remains non-destructive pending separate policy approval and poster generation is unimplemented
- [x] Full test suite on Windows: 78 passed, 2 skipped (Tcl/Tk runtime files missing in the Python installation)
- [ ] Test GUI manually on Windows (native Windows check pending; installed Tcl/Tk files are incomplete)
- [ ] Package portable Windows executable

## Next stages
1. Visually review the Catalog grid, Inventory table, and Add/Edit layouts on a complete native Windows Tk installation.
2. Add import/export and fuller reports.
3. Add integration and recovery tests.
4. Package the stable desktop app.
5. Build the Android companion after desktop stabilization.
- [ ] Connect BookLedger Mobile to real pairing, ISBN scanning, and photo transfer.
