# BookLedger Architecture (initial)

## Modules
- `bookledger.app`: main window, navigation, and page composition.
- `bookledger.ui.forms`: intake/edit form and field-level feedback.
- `bookledger.db.database`: SQLite connection setup, versioned schema migration, canonical locations, integrity checks, consistent snapshots.
- `bookledger.services.catalog`: validation, duplicate lookup, copy creation/editing, canonical location management, contextual price and explicit status/sales rules.
- `bookledger.services.isbn`: ISBN normalization and check-digit validation.
- `bookledger.services.metadata`: replaceable provider adapters, with Open Library primary and Google Books fallback; each request has its own 10-second timeout and lookup misses are distinct from technical failures.
- `bookledger.services.photos`: image orientation, resizing, and JPEG compression.
- `bookledger.services.lifecycle`: durable trash, restore, clear, purge, and explicit recovery of file/database operations.
- `bookledger.services.verification`: read-only relational and managed-photo-tree consistency checks.
- `bookledger.services.backups`: verified backup archives and restore workflow.
- `bookledger.paths`: portable data locations and verified legacy-file migration.

## Data ownership
`book_records` owns bibliographic metadata shared by an edition/ISBN. `copies` owns physical-copy fields, the one current Price, and stable Copy IDs. `sales` is an append-only history of Price/date events; status reversals keep their recorded history and do not void revenue. A later transition back to Sold appends another event. Photo paths are stored relative to the portable data folder so moving the folder does not invalidate image references.

## Copy identity
On a fresh database, SQLite generates `copies.id` as an `INTEGER PRIMARY KEY AUTOINCREMENT`; `CatalogService.create_copy()` reads that row ID and formats the human-facing `copy_code` as `BL-` plus the ID padded to at least six digits. The primary key is the internal identity used by queries, callbacks, and copy-specific operations. `copy_code` is displayed, searchable, and used in messages, but current application logic does not parse it to recover an ID or use its formatting as the identity rule. IDs are unique within one database, not globally across separate databases or restored snapshots. Restoring an older backup also restores its earlier ID sequence. Schema v4 rebuilds legacy `copies` once to add AUTOINCREMENT and the book-record foreign key while copying IDs, codes, copy numbers, and values verbatim. The display code can grow beyond six digits as IDs grow.

## UI/business boundary
UI callbacks gather input and display service results. Core validation and persistence rules are enforced in `CatalogService` and SQLite constraints. Long-running metadata lookup runs off the UI event thread, with provider activity, provider outcomes, and the overall result passed back through a UI queue and applied on Tk's thread. Each provider outcome distinguishes a confirmed miss, a matched record with sparse metadata, and categorized lookup failures; user-visible diagnostics avoid raw exception details. Operation IDs and the requested ISBN guard against stale callbacks after an ISBN change, form clear, or newer lookup. Open Library remains primary; Google Books is called for fallback/enrichment as needed. Provider-derived titles are normalized, and values are merged into empty controls only. The Add Book form includes a photo preview and simulated BookLedger Mobile connection and ISBN scanning controls. The metadata provider can be replaced without changing the catalog schema or form workflow.

Catalog and Inventory share `CatalogService.list_copies()` and the same active physical-copy rows; trashed and pending storage-operation rows are filtered centrally. Catalog presents one photo card per copy, including stable Copy ID, Price, and a gray overlay/red SOLD marker; double-click opens read-only More Details. Inventory presents a sortable detailed table; double-click edits the clicked row. Both expose the same right-click context menu; Delete moves exactly one copy to Trash. Dashboard counts and ordinary sales/revenue exclude copies in Trash. Restore preserves the row and its sales events; Clear Trash permanently removes those sales events and conditionally removes an unreferenced bibliographic record.

Schema v4 includes `trash_entries` and `storage_operations`. Trash metadata references the original copy row and records its previous status and deletion order. Storage operations make interrupted photo install/replace/trash/restore/cleanup detectable and expose explicit retry. Database transactions and file moves are coordinated by services; a filesystem operation is not considered complete while its durable journal remains.

## Portable storage and migration
`AppPaths` resolves the project root during source development and the executable directory when frozen. Writable application data is under `data/`: `bookledger.sqlite3`, `photos/{copy_id}.jpg`, `trash/{copy_id}.jpg`, and `assets/google_books.json`. Root-level `backups/` is preserved by Purge. Startup detects legacy `BookLedger_Data/` before database initialization, snapshots SQLite through its backup API, copies photos/assets/backups, checks the copied database, canonicalizes referenced old photos to per-ID JPEGs, and only then renames the legacy folder to a `.migrated` recovery folder. Both-database conflicts stop startup. Provider configuration is copied from `%LOCALAPPDATA%`, validated, and removed from its old profile path only when the portable value matches; a differing or invalid configuration stops startup for manual resolution. Its value is never printed.

New and replacement images are processed through `PhotoService` into `photos/.staging/` and become canonical only once fully decoded and compressed. New copies reserve their generated ID in SQLite and journal the canonical installation; replacements use same-volume atomic replacement so the old image remains until the staged replacement is ready. Mobile photo handoff and Choose Photo both call the same staging service.

## Trash and verification
Delete journals then moves one canonical photo to `trash/{copy_id}.jpg` and inserts a `trash_entries` row without deleting the copy or its sales history. Restore selects the latest Trash entry (LIFO), moves the original photo back, and removes Trash metadata only after the file move. Clear Trash deletes selected sales/copy/trash rows in a transaction, removes bibliographic records only when no copies remain, then removes unshared files; a cleanup failure remains in `storage_operations` for explicit retry. Purge requires two UI confirmations including the exact word `PURGE`, clears only resolved children within `data/`, and retains root backups.

`VerificationService` does not mutate data. It checks SQLite integrity and foreign keys, copy identities, Trash consistency, unresolved storage operations, canonical and safe photo paths, missing active/trashed photos, unreferenced files, shared paths, and staging residue. Warnings do not trigger cleanup. Backup changes are limited to including `trash/` alongside the existing SQLite snapshot and `photos/` tree.

The optional Google Books setting is stored as plain text in portable `data/assets/google_books.json` and excluded from backups. On startup, an existing profile setting is copied into that location without logging its value and its profile copy is removed only after validation. Purge therefore removes the migrated setting without startup copying it back.

## Future Android interface
The desktop remains the source of truth. A future local service should expose only explicit pairing, ISBN submission, photo upload, acknowledgement, and session/capture identifiers. The phone must never open or mutate the SQLite file directly. This local service is intentionally not part of the current build; the current intake controls only simulate connection and scan events.

## Development stages
1. Data and validation foundation.
2. Intake/edit workflow and duplicate edge cases.
3. Catalog and inventory usability/performance.
4. Sales/reporting and import/export.
5. Backup/restore hardening and recovery testing.
6. Windows packaging and acceptance tests.
7. Android companion after desktop stabilization.
