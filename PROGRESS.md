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
- [x] Sales view shows Date Sold and actual Price only; revenue summaries use actual transaction prices
- [x] Treeview double-click handlers reject destroyed/stale views and open the clicked Copy ID
- [x] Partial Open Library metadata is merged with Google Books fallback without replacing available values; forms preserve manual values and show missing optional data
- [x] Optional Google Books API key and connectivity test in Settings; key stored outside portable backups with its plain-text tradeoff documented
- [x] Canonical location registry with v1 data migration, add/rename propagation, safe deletion rules, and form/filter choices
- [x] Catalog double-click opens read-only selected-copy details; Inventory double-click retains selected-copy editing
- [x] Add/Edit use one contextual Price field and no Status or Sale Details controls; Inventory provides explicit status changes and sold-copy transaction capture
- [x] Preserve asking price and sale history while editing context-sensitive price; Sales and Reports use transaction amounts
- [x] v1-to-v2 database migration preserves records, copy locations, and sales history
- [x] Full test suite on Windows: 41 passed, 2 skipped (Tcl/Tk runtime files missing in the Python installation)
- [ ] Test GUI manually on Windows (native Windows check pending; installed Tcl/Tk files are incomplete)
- [ ] Package portable Windows executable

## Next stages
1. Visually review the Catalog grid, Inventory table, and Add/Edit layouts on a complete native Windows Tk installation.
2. Add import/export and fuller reports.
3. Add integration and recovery tests.
4. Package the stable desktop app.
5. Build the Android companion after desktop stabilization.
- [ ] Connect BookLedger Mobile to real pairing, ISBN scanning, and photo transfer.
- [x] Backup restoration service and Settings action with verification/confirmation
- [x] Store photo paths relative to the portable data folder
- [x] GUI smoke-tested under a virtual X display across all initial pages
- [x] 41 automated tests passing on Windows; 2 Tk UI tests skipped because Tcl/Tk files are missing
