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
- [x] Run all automated tests on Windows (13 passed)
- [x] Close SQLite connections reliably after success and exceptions; verify backup creation and restoration on Windows
- [x] Add Book two-panel layout with independently scrolling form, photo preview, simulation status, and two-row actions
- [x] Field-specific validation messages below inputs with valid-value clearing and finite positive price validation
- [x] BookLedger Mobile connection/scan UI simulation, retry rules, and 10-second scan timeout
- [x] Open Library primary metadata lookup with Google Books fallback and per-provider timeouts
- [x] Service validation rejects non-finite or unrepresentable copy and sale prices and unapproved genres
- [x] Dashboard distinguishes all physical copies from distinct bibliographic records and status counts
- [x] Catalog photo-card grid and sortable Inventory table share copy records and ordered Genre, Condition, Location, Status filters
- [x] Sales view shows Date Sold and actual Price only; revenue summaries use actual transaction prices
- [x] Full test suite on Windows: 31 passed, 2 skipped (Tcl/Tk files missing in the Python installation)
- [ ] Test GUI manually on Windows (virtual-display smoke test passed; native Windows check pending)
- [ ] Package portable Windows executable

## Next stages
1. Complete and test persistence/restore behavior.
2. Finish intake/edit workflows and duplicate selection edge cases.
3. Visually review the Catalog grid, Inventory table, and Add Book layout on a complete native Windows Tk installation.
4. Add import/export and fuller reports.
5. Add integration and recovery tests.
6. Package the stable desktop app.
7. Build the Android companion after desktop stabilization.
- [ ] Connect BookLedger Mobile to real pairing, ISBN scanning, and photo transfer.
- [x] Backup restoration service and Settings action with verification/confirmation
- [x] Store photo paths relative to the portable data folder
- [x] GUI smoke-tested under a virtual X display across all initial pages
- [x] 31 automated tests passing on Windows; 2 Tk UI tests skipped because Tcl/Tk files are missing
