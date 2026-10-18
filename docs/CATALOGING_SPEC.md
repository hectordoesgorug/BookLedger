# BookLedger Cataloging Specification v1.0

## Principles
- Portable, offline-first Windows desktop application; SQLite is the local source of truth.
- One bibliographic record can own multiple individually tracked physical copies.
- No mandatory migration from the legacy Bookseller database.
- A future Android companion communicates through a defined local interface; it never edits SQLite directly.

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
New copies are Available. Add/Edit do not expose status controls; Catalog and Inventory context menus provide explicit status actions. The action for the current status is disabled. Leaving Not for Sale or Sold asks for confirmation; leaving Available or Listed does not.

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

The current intake UI tries Open Library first and Google Books second. Google Books fills fields missing from a partial Open Library result without replacing populated provider values. Provider results fill blank form fields only, preserving manual entry. Provider-derived titles are normalized to title case using short-word and common-acronym conventions; manual titles retain their capitalization. Optional missing fields show No Data and remain NULL when saved. Each provider request has an independent 10-second timeout. A missing ISBN record is reported separately from timeout, network, and provider failures. The Add Book form offers retry only for a technical failure. Google Books works without an API key in the current integration; an optional key and connectivity check are available in Settings. A supplied key is stored as plain text in portable `data/assets/google_books.json` and excluded from portable backups.

## Intake companion mockup
The Add Book form includes a photo preview and a BookLedger Mobile status area. Connection and ISBN scanning are simulated for UI testing; actual phone pairing, networking, scanning, and photo transfer are outside this build. Scan attempts time out after 10 seconds. The preview exposes a photo handoff point for a future companion integration.

## Sales
Add/Edit presents one Price field. It is editable for unsold copies and locked while Sold. Marking Sold validates the current Price and records that amount and today's local date without asking for separate sale details. The Sales table is an append-only history of price/date events; moving away from Sold leaves history and revenue intact, and a later transition to Sold appends another event. Status reversal does not void revenue or represent a refund. No returns, reservations, or pending-sale status in v1.

The Sales view lists recorded sale events with Copy ID, Title, Author, Date Sold, and Price. It omits current status. Revenue summaries sum all retained sale events, including historical events when a copy's current status later changes.

## Dashboard, Catalog, and Inventory
Dashboard shows active Total Copies (including Sold), titles with at least one active copy, and one counter for each active copy status. Copies in Trash and their sales events are excluded from ordinary views and revenue.

Catalog is a searchable, sortable thumbnail grid with one card per active physical copy. Each card shows its photo, unique Copy ID, title, author, and Price; Sold copies have a gray cover overlay and red SOLD text. Double-click opens a read-only More Details view for that exact copy. Catalog and Inventory right-click menus offer View Details, Create Poster, the four Mark as status actions, Edit Book, and Delete Book in that order. Create Poster is not implemented. Delete Book moves only the selected copy and its photo into Trash without deleting the row or its sales history. Inventory remains a detailed sortable copy table with Copy ID, Title, Author, Format, Condition, Location, Price, and Status; double-click opens Edit for the clicked copy. Both views use the same active records and filters in this order: Genre, Condition, Location, Status. Sold copies sort after all other statuses, with the selected ordinary sort applied within both groups. Sold copy numbers are retained.

## Storage and safety
The source project root is the portable root during development; a frozen application uses the executable directory. Database, canonical `photos/{copy_id}.jpg`, Trash photos, and provider settings live beneath `data/`. Root-level `backups/` remains separate and Purge preserves it. Startup detects legacy `BookLedger_Data/` and profile Google Books settings before creating a new database, copies the files, validates the destination, then renames the legacy folder to a `.migrated` recovery folder. If both legacy and portable databases exist, startup stops for manual conflict resolution. Schema v4 adds Trash and durable storage-operation rows; migrations preserve copy IDs/codes/copy numbers, sales, and book relationships. Keep a backup before automatic migration.

Delete moves exactly one copy to Trash. Ordinary catalog, inventory, dashboard, sales, and revenue views exclude trashed copies. Restore Latest in Settings reverses deletions in LIFO order and keeps the original copy identity and sales history. Clear Trash requires confirmation, deletes trashed sales and copies transactionally, removes only unshared photos, and removes a bibliographic record only when no copies remain. Purge warns about its scope, then requires typing `PURGE`; only managed `data/` content is removed, while root backups and bundled resources remain. Verify Database is read-only and reports integrity, foreign-key, operation-journal, path, and photo-tree issues. Interrupted file operations are explicitly retryable from Settings.

Each copy photo is staged, decoded, compressed, and installed as a canonical JPEG. Add Book and the future mobile photo event use the same PhotoService processing. Replacement uses atomic same-volume replacement only after the new image is ready. Backups receive only the minimal compatibility addition of the `trash/` photo tree; broader backup redesign is deferred. Core desktop functions work offline and without a paired phone. Assume one active database writer. No packaged executable is currently available for frozen-layout acceptance testing.
