# BookLedger Architecture (initial)

## Modules
- `bookledger.app`: main window, navigation, and page composition.
- `bookledger.ui.forms`: intake/edit form and field-level feedback.
- `bookledger.db.database`: SQLite connection setup, schema, integrity checks, consistent snapshots.
- `bookledger.services.catalog`: validation, duplicate lookup, copy creation/editing, list queries, status and sales rules.
- `bookledger.services.isbn`: ISBN normalization and check-digit validation.
- `bookledger.services.metadata`: provider interface and optional Google Books adapter.
- `bookledger.services.photos`: image orientation, resizing, and JPEG compression.
- `bookledger.services.backups`: verified backup archives and restore workflow.
- `bookledger.paths`: portable data locations.

## Data ownership
`book_records` owns bibliographic metadata shared by an edition/ISBN. `copies` owns physical-copy fields and stable Copy IDs. `sales` records the actual sale price/date and is retained if the copy's current status is later changed. Photo paths are stored relative to the portable data folder so moving the folder does not invalidate image references.

## UI/business boundary
UI callbacks gather input and display service results. Core validation and persistence rules are enforced in `CatalogService` and SQLite constraints. Long-running metadata lookup is run off the UI event callback. The metadata provider can be replaced without changing the catalog schema or form workflow.

## Future Android interface
The desktop remains the source of truth. A future local service should expose only explicit pairing, ISBN submission, photo upload, acknowledgement, and session/capture identifiers. The phone must never open or mutate the SQLite file directly. This local service is intentionally not part of the current build.

## Development stages
1. Data and validation foundation.
2. Intake/edit workflow and duplicate edge cases.
3. Catalog and inventory usability/performance.
4. Sales/reporting and import/export.
5. Backup/restore hardening and recovery testing.
6. Windows packaging and acceptance tests.
7. Android companion after desktop stabilization.
