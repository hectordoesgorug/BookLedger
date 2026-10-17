# BookLedger Architecture (initial)

## Modules
- `bookledger.app`: main window, navigation, and page composition.
- `bookledger.ui.forms`: intake/edit form and field-level feedback.
- `bookledger.db.database`: SQLite connection setup, versioned schema migration, canonical locations, integrity checks, consistent snapshots.
- `bookledger.services.catalog`: validation, duplicate lookup, copy creation/editing, canonical location management, contextual price and explicit status/sales rules.
- `bookledger.services.isbn`: ISBN normalization and check-digit validation.
- `bookledger.services.metadata`: replaceable provider adapters, with Open Library primary and Google Books fallback; each request has its own 10-second timeout and lookup misses are distinct from technical failures.
- `bookledger.services.photos`: image orientation, resizing, and JPEG compression.
- `bookledger.services.backups`: verified backup archives and restore workflow.
- `bookledger.paths`: portable data locations.

## Data ownership
`book_records` owns bibliographic metadata shared by an edition/ISBN. `copies` owns physical-copy fields, the one current Price, and stable Copy IDs. `sales` is an append-only history of Price/date events; status reversals keep their recorded history and do not void revenue. A later transition back to Sold appends another event. Photo paths are stored relative to the portable data folder so moving the folder does not invalidate image references.

## UI/business boundary
UI callbacks gather input and display service results. Core validation and persistence rules are enforced in `CatalogService` and SQLite constraints. Long-running metadata lookup runs off the UI event thread, with results passed back through a UI queue. The Add Book form includes a photo preview and simulated BookLedger Mobile connection and ISBN scanning controls. The metadata provider can be replaced without changing the catalog schema or form workflow.

Catalog and Inventory share `CatalogService.list_copies()` and the same physical-copy rows. Catalog presents one photo card per copy, including stable Copy ID, Price, and a gray overlay/red SOLD marker; double-click opens read-only More Details. Inventory presents a sortable detailed table; double-click edits the clicked row. Both expose the same eight-option right-click context menu. Status changes use the menu only, disable the current status, and confirm transitions away from Not for Sale or Sold. Both views filter in the order Genre, Condition, Location, Status using the canonical location registry. Sold rows sort last after filtering, with the selected ordinary sort applied inside each status group. Dashboard copy/status counts query physical copies, while Distinct Titles counts bibliographic records once each. Price is editable until Sold and is then locked. Sales and revenue use every retained event's Price and date.

The v1-to-v3 migration seeds canonical locations from existing copy location strings, preserves sale history, renames the historical amount column to `price_minor`, and allows multiple sale events per copy. User Google Books settings are stored in the operating-system user profile rather than the portable data folder and are excluded from backups. The API key is optional for current public Google Books requests; if configured, it is stored as plain text under the user's account access controls.

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
