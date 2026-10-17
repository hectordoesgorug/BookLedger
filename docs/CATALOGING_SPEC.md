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
System-generated stable Copy ID; required Format, Condition, Photo, and Price; optional Location (defaults to `Not Specified`); status; stable copy number. Price is the user's valuation and intended selling price in PHP and must be finite and greater than PHP 0. Exactly one photo is stored per physical copy; photos are compressed for portable storage.

## Statuses
- Available: default status; otherwise unlisted sale inventory.
- Not for Sale: user intends to keep the copy.
- Listed: the user has listed the copy on a marketplace.
- Sold: specifically marked sold; requires actual sale price and sale date.
Statuses are editable. Historical sale data is retained if status later changes.

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

The current intake UI tries Open Library first and Google Books second. Each provider request has an independent 10-second timeout. A missing ISBN record is reported separately from timeout, network, and provider failures. The Add Book form offers retry only for a technical failure.

## Intake companion mockup
The Add Book form includes a photo preview and a BookLedger Mobile status area. Connection and ISBN scanning are simulated for UI testing; actual phone pairing, networking, scanning, and photo transfer are outside this build. Scan attempts time out after 10 seconds. The preview exposes a photo handoff point for a future companion integration.

## Sales
When marking Sold, record actual sale price (> PHP 0) and sale date. Keep the original Price unchanged. No returns, reservations, or pending-sale status in v1.

The Sales view lists completed transactions with Copy ID, Title, Author, Date Sold, and the actual transaction Price. It omits current status. Revenue summaries sum retained actual sale prices, including historical sales when a copy's current status later changes.

## Dashboard, Catalog, and Inventory
Dashboard shows Total Copies (all physical copies, including Sold), Distinct Titles (bibliographic records counted once), and one counter for each copy status.

Catalog is a searchable, sortable thumbnail grid with one card per physical copy. Each card shows its photo, unique Copy ID, title, author, and current selling price; Sold copies have a clear SOLD overlay. Opening a card edits that specific copy. Inventory remains a detailed sortable copy table with Copy ID, Title, Author, Format, Condition, Location, Price, and Status. Both views use the same records and filters in this order: Genre, Condition, Location, Status. Sold copies remain in historical views and are not deleted or renumbered.

## Storage and safety
Database, photos, and backups live in the portable data folder. Backups include a consistent SQLite snapshot and photos. Core desktop functions work offline and without a paired phone. Assume one active database writer. Restoration must be validated and tested before release.
