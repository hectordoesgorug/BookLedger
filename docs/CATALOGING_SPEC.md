# BookLedger Cataloging Specification v1.0

> This document preserves the original cataloging and inventory requirements. Some implementation details and validation status have since changed; see [Architecture](ARCHITECTURE.md), the [mobile guide](../mobile/README.md), and the [release checklist](RELEASE_CHECKLIST_v1.0.0.md) for current behavior and release status.

## Principles
- Portable, offline-first Windows desktop application; SQLite is the local source of truth.
- One bibliographic record can own multiple individually tracked physical copies.
- No mandatory migration from the legacy Bookseller database.
- The Android companion communicates with the desktop over its local interface and never edits SQLite directly.

## Bibliographic fields
Required: Title, Author, Genre.
Optional: ISBN, Book Details/synopsis, Publisher/imprint, Publication year, Edition, Page count, SRP.

## Approved genres
Science; Social Science; Politics; Fiction; Medical; History; Art; Biography; Humor; Religion/New Age; Children; General Knowledge; Miscellaneous.
Philosophy and Linguistics are categorized under Social Science. Metadata-returned genres outside the approved list remain visible but must be manually recategorized before saving.

## Physical-copy fields
System-generated stable Copy ID; required Format, Condition, Photo, and Price; Location defaults to `Not Specified`; status; stable copy number. Price is the user's valuation and intended selling price in PHP and must be finite and greater than PHP 0. Exactly one photo is stored per physical copy; photos are compressed for portable storage. Locations are canonical values managed in Settings. Existing copy locations are migrated into the registry; renaming updates all assigned copies, and referenced locations cannot be deleted. `Not Specified` is the fixed default.

## Statuses
- Available: default status; otherwise unlisted sale inventory.
- Not for Sale: user intends to keep the copy.
- Listed: the user has listed the copy on a marketplace.
- Sold: specifically marked sold; marking it records the current Price and the local date.
New copies are Available. Add/Edit do not expose status controls; Catalog and Inventory context menus provide explicit status actions. The action for the current status is disabled. Leaving Not for Sale or Sold asks for confirmation; leaving Available or Listed does not. Leaving Sold requires selecting a predefined void reason, records the void timestamp and reason with that sale, and retains the transaction in Sale History excluded from completed-sales revenue.

## Validation
Required inputs: Title, Author, Genre, Format, Condition, Price > PHP 0, Photo.
No validation modal dialogs. On Save, highlight all missing/invalid fields in red and show inline explanations. Keep form values. ISBN-10/ISBN-13 check digits are validated with explicit manual override. ISBN itself is optional.

## Duplicate rules
- Exact ISBN match: ask whether to add another physical copy; reuse the existing bibliographic record if confirmed.
- Different ISBN: separate bibliographic record, even if title/author match.
- No ISBN: matching title and author prompts the user to decide whether it is an additional copy or a distinct book.
- Copy IDs and display copy numbers remain stable; sold copy numbers are not reused.

## Metadata states
`Retrieving…`, `No data`, `Lookup failed`, and `Manual entry` are distinct. Optional missing metadata is stored as null. Failed lookups do not erase manual input and do not block saving when required fields are otherwise valid. Metadata provenance belongs in detail views, not the main catalog list.

The intake UI uses the enabled metadata providers in the order configured in Settings. The registry order is Open Library, Google Books, Archive.org, Booktopia, Bigbook, then Hardcover; the original four are enabled by default, while Bigbook and Hardcover start disabled. Each later enabled provider fills supported empty fields without replacing earlier provider or manual values. Lookup stops after title, author, genre, publisher, and publication year are available; edition, format, synopsis, and page count are optional enrichment. Provider request timeouts are bounded. A missing ISBN record is reported separately from timeout, network, and provider failures. The Add Book form offers retry for technical failures. Google Books works without an API key in the current integration; an optional key and connectivity test are available in Settings. Provider credentials are stored locally; backups may contain configuration credentials and are not encrypted.

## Android companion and intake
The Android companion scans an ISBN or accepts manual/no-ISBN entry, captures front-cover photographs, and transfers single captures or queued batches to the desktop over the local network. It does not manage the library itself. The desktop stages received captures and catalogs them through the existing Add Book form, one capture at a time. Pairing and transfer use unencrypted local HTTP; pair on a trusted network. See the [mobile guide](../mobile/README.md) for pairing, transfer, permission, and recovery details.

## Sales
Add/Edit presents one Price field. It is editable for unsold copies and locked while Sold. Marking Sold validates the current Price and records that amount and today's local date without asking for separate sale details. Sale History retains price/date events. Moving away from Sold requires one of `Marked Sold by Mistake`, `Cancelled Order`, `Returned Order`, or `Test`; the active transaction receives its void timestamp and reason atomically with the copy status update, while its original price/date remain unchanged. A later transition to Sold records a new active transaction using the current Price and date. No returns, reservations, or pending-sale status in v1.

The Sale History view lists recorded sale events with Copy ID, Title, Author, Date Sold, and Price. It omits current status and does not edit copies. Voided events remain visible and are styled gray with a red strikethrough. Double-click opens the read-only View Details window, including the complete Sale History / Void Log for that physical copy. Revenue summaries sum active, non-voided sale events only. Sale History sorting is in-memory and never changes stored records.

## Reports
Inventory Summary counts active physical copies and distinct bibliographic records. Inventory Valuation sums each active copy's recorded Price across all statuses for Total Library Value; Expected Revenue includes only Available and Listed copies. Sales Revenue sums active, non-voided actual sale-event prices, never current copy valuations. Trashed copies and their sales are excluded from ordinary reports.

Monthly Revenue groups completed sale events by their recorded Date Sold. The earliest navigable month is the month of the earliest active bibliographic record's `created_at` date; if no active dated record exists, historical navigation is disabled. Books by Genre counts active physical copies by their assigned genre.

## Dashboard, Catalog, and Inventory
Dashboard shows active Total Copies (including Sold), titles with at least one active copy, and one counter for each active copy status. Copies in Trash and their sales events are excluded from ordinary views and revenue.

Catalog is a searchable, sortable thumbnail grid with one card per active physical copy. Each card shows its photo, unique Copy ID, title, author, and Price; title and author each use a two-line area, with longer text ellipsized in the card. More Details shows the complete stored values. Sold copies have a gray cover overlay and red SOLD text. Double-click opens a read-only More Details view for that exact copy. Catalog and Inventory right-click menus offer View Details, Create Poster, the four Mark as status actions, Edit Book, and Delete Book in that order. Create Poster uses the selected reusable template and the chosen physical copy's current bibliographic fields, asking before replacing an existing PNG. Poster Setup provides a freeform template canvas with movable/resizable fields and background upload. Delete Book moves only the selected copy and its photo into Trash without deleting the row or its sales history. Inventory remains a detailed sortable copy table with Copy ID, Title, Author, Format, Condition, Location, Price, and Status; double-click opens Edit for the clicked copy. Both views use the same active records and filters in this order: Genre, Condition, Location, Status. Sold copies sort after all other statuses, with the selected ordinary sort applied within both groups. Sold copy numbers are retained.

## Storage and safety
The source project root is the portable root during development; a frozen application uses the executable directory. Versioned provider order and enabled state live in root `config.json` (with a per-user fallback when the portable root is not writable); Google Books credentials remain separately under `data/assets/`. Database, canonical `photos/{copy_id}.jpg`, and Trash photos live beneath `data/`. Root-level `backups/` remains separate, and Inventory Purge preserves both backups and provider configuration. Startup detects legacy `BookLedger_Data/` and profile Google Books settings before creating a new database, copies the files, validates the destination, then renames the legacy folder to a `.migrated` recovery folder. If both legacy and portable databases exist, startup stops for manual conflict resolution. Schema v4 adds Trash and durable storage-operation rows; schema v5 adds explicit sale voiding and enforces at most one active sale per copy; schema v6 adds the transaction-level void reason. Migrations preserve copy IDs/codes/copy numbers, original sale values, and book relationships. Keep a backup before automatic migration.

Delete moves exactly one copy to Trash. Ordinary catalog, inventory, dashboard, sales, and revenue views exclude trashed copies. Restore Latest in Settings reverses deletions in LIFO order and keeps the original copy identity and sales history. Clear Trash requires confirmation, deletes trashed sales and copies transactionally, removes only unshared photos, and removes a bibliographic record only when no copies remain. Purge warns about its scope, then requires typing `PURGE`; only managed `data/` content is removed, while root backups and bundled resources remain. Verify Database is read-only and reports integrity, foreign-key, operation-journal, path, and photo-tree issues. Interrupted file operations are explicitly retryable from Settings.

Each copy photo is staged, decoded, compressed, and installed as a canonical JPEG. Incoming mobile photos are staged and validated before desktop cataloging. Replacement uses atomic same-volume replacement only after the new image is ready. Backups include the managed photos, Trash, assets, posters, and configuration; restore replaces the current library and does not merge it. Core desktop functions work offline and without a paired phone. Assume one active database writer. The v1.0.0 Windows and Android release assets are published; see the release checklist for publication and acceptance records.
