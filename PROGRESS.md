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
- [x] Run/repair all automated tests
- [ ] Test GUI manually on Windows (virtual-display smoke test passed; native Windows check pending)
- [ ] Package portable Windows executable

## Next stages
1. Complete and test persistence/restore behavior.
2. Finish intake/edit workflows and duplicate selection edge cases.
3. Strengthen catalog filters and copy detail navigation.
4. Add import/export and fuller reports.
5. Add integration and recovery tests.
6. Package the stable desktop app.
7. Build the Android companion after desktop stabilization.
- [x] Backup restoration service and Settings action with verification/confirmation
- [x] Store photo paths relative to the portable data folder
- [x] GUI smoke-tested under a virtual X display across all initial pages
- [x] 10 automated tests passing
