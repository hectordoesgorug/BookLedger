# BookLedger (early desktop foundation)

BookLedger is a fresh, modular rebuild of a personal book collection and inventory manager. It is designed for portable Windows use, offline-first cataloging, and eventual integration with an Android ISBN/photo companion.

## Current implementation
- Modular Python package and Tkinter desktop shell.
- SQLite schema separating bibliographic records, physical copies, and sale records.
- Four statuses: Available, Not for Sale, Listed, Sold.
- Approved 13-genre list and save-blocking validation for unfamiliar genres.
- ISBN-10/ISBN-13 check-digit validation with manual override.
- Individual-copy IDs and stable copy numbers.
- Photo import/compression with per-copy photo storage.
- Open Library primary metadata lookup, Google Books fallback/enrichment, and a final Booktopia HTML lookup for supported missing fields; manual cataloging remains possible. ISBN identifiers are validated and provider values fill empty fields only.
- Add Book intake form with photo preview, inline validation, and clear/retry/cancel actions.
- BookLedger Mobile connection and ISBN scanning are testable UI simulations; no phone networking is included.
- Inline form validation (no validation dialog for missing/invalid fields).
- Local database backup with photo files and integrity verification.
- Catalog photo-card grid and detailed sortable Inventory table over the same active physical-copy records, with Genre, Condition, Location, and Status filters.
- Catalog cards open a read-only More Details view; Inventory double-click edits the selected copy. Catalog and Inventory share right-click actions for details, poster placeholder, status changes, edit, and moving a selected copy to Trash.
- Canonical locations can be added, renamed (including updating assigned copies), and deleted when unused.
- Dashboard counters distinguish active physical copies (including Sold) from titles with active copies. Sales and revenue summaries exclude copies in Trash and use retained Price and Date Sold events.
- Per-copy canonical JPEG photos, copy-level Trash, LIFO restore, permanent Clear Trash, two-step Purge, and read-only database/photo verification.

This is an early development build, not a release candidate. Fuller reporting, exports/imports, additional metadata providers, Android integration, and Windows packaging are still planned. Portable migration and storage recovery need broader manual Windows acceptance testing.

## Run from source
Requires Python 3.10+ and Tkinter. On Windows, run `run_bookledger.bat`; it creates `.venv` if needed, checks the editable install and runtime dependencies, and launches the `bookledger` console entry point. If setup or startup fails, the launcher displays the diagnostic and waits before closing.

For manual installation, create a virtual environment and install the project in editable mode:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\bookledger.exe
```

On Linux/macOS, install Tk support for your Python distribution, then run `python -m venv .venv`, `python -m pip install -e .`, and `.venv/bin/bookledger` (activate `.venv` first if preferred).

## Development setup and tests

Install the development extra into the same virtual environment used to run tests. It includes pytest and PyInstaller; pytest is a development dependency, not an application runtime dependency.

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

On Windows, use `.venv\Scripts\python.exe -m pip install -e ".[dev]"` and `.venv\Scripts\python.exe -m pytest -q` (or activate `.venv` first and use the commands above).

## Metadata settings

Open **Settings → Google Books API** to save an optional API key or test connectivity. Google Books works without a key. If provided, the key is stored as plain text in `data/assets/google_books.json`, excluded from portable backups, and never logged. Open Library remains primary, Google Books is the fallback/enrichment provider, and Booktopia runs last when it can still fill supported fields. The skip check includes missing Book Details/Synopsis for Google Books and Booktopia. The Add Book form displays separate activity and final outcomes for all three providers alongside the overall result.

Open Library requests valid ISBN-13 and ISBN-10 keys for 978 ISBNs. It supplies supported bibliographic fields but never fills Book Details/Synopsis from edition descriptions, notes, excerpts, or linked-work descriptions. Google Books tries the exact ISBN query, the explicit `isbn:` query, and the equivalent ISBN form if needed; it accepts only volumes with a matching ISBN. Booktopia makes a bounded HTTPS request to its ISBN search page and follows at most two same-site product links whose URL contains the requested ISBN or its valid equivalent. It then requires matching ISBN evidence in the product page before accepting metadata. From matching schema.org Book data it can fill title, author, publisher, publication year, edition, page count, and recognized print format. For Book Details, it uses a Description panel only when the `#pdp-tab-description` tab explicitly identifies that panel through an HTML relationship such as `aria-controls`, `href`, or the panel's `aria-labelledby`. If no linked panel is available, a matching schema.org Book description is considered after filtering known bibliographic notes and retailer boilerplate. Generic `description`/Open Graph metadata and unassociated `itemprop="description"` text are not used. If no usable source remains, Book Details stays empty. Booktopia does not fill the ISBN, BookLedger Price, or SRP. Language and series are not currently stored by the form. Open Library and Google Books values take precedence, and all provider values fill empty controls only. In particular, an existing page count is preserved when Booktopia reports a different value.

Open Library accepts a response keyed to the queried ISBN when identifiers are absent but rejects conflicting identifiers. Google Books records without a matching identifier and Booktopia pages without matching ISBN evidence are reported as unverified rather than confirmed misses. A matching Booktopia page with an explicit unavailable message or structured `OutOfStock`, `Discontinued`, or `SoldOut` state is shown as **Product unavailable**; HTTP errors, including 404 responses, remain provider errors. A search page with no verifiable result is not called an ISBN miss. Google Books and Booktopia may populate Book Details; Open Library does not. Sparse matching records, confirmed misses, unverified results, unavailable products, and provider errors have separate statuses. Provider errors are summarized without technical details. Provider-derived titles are normalized; manually entered values remain unchanged. Lookup runs in a worker thread, while status and form updates are applied on Tk's UI thread; clearing the form or changing the ISBN prevents stale results from being applied.

Booktopia is an HTML-based, best-effort source rather than a stable metadata API. The checked [Terms of Business](https://www.booktopia.com.au/termsOfBusiness) state that bibliographic data is copyrighted by Nielsen Book Services, publishers, or their licensors; they do not establish permission for automated metadata retrieval. BookLedger makes a user-triggered, bounded lookup rather than a scheduled or systematic crawl, and does not bypass access controls. Use remains subject to Booktopia's policies and future page changes. Live raw HTML and the current tab-to-panel relationship could not be verified in the development environment; deterministic fixtures test the explicit relationship parser using synthetic markup only.

## Price and status behavior

Add and Edit use one **Price** field. It is editable while a copy is unsold and locked while Sold. The context menu's **Mark as Sold** records the current Price and today's local date without asking for separate sale details. New copies start as Available. Status reversals retain their historical sale events; marking Sold again adds a new event. A copy moved to Trash retains its sales rows but is excluded from Sales and revenue until restored. Clear Trash permanently removes the selected trashed copies and their sales history. Create Poster remains a placeholder. Schema v4 adds Trash and durable storage-operation records and rebuilds legacy `copies` only to add the missing book foreign key and AUTOINCREMENT guarantee while preserving IDs. Back up before opening an older database.

## Portable data
The portable root is the source project root in development, or the executable's directory in a packaged build. Writable files use `data/bookledger.sqlite3`, `data/photos/{copy_id}.jpg`, `data/trash/`, `data/assets/`, and root-level `backups/`. Resolution does not depend on the current working directory. On startup, a legacy `BookLedger_Data/` database and files are copied and checked before the old folder is renamed to `BookLedger_Data.migrated` as a recovery copy. If both legacy and portable databases exist, startup stops with a conflict message. An existing profile Google Books setting is copied and validated into portable data, then its old profile copy is removed; a conflict stops startup for manual resolution. Backups include the SQLite snapshot and both active and trashed photos; broader backup redesign is still pending.

In **Settings**, Restore Latest reverses the most recent Trash action (LIFO). Clear Trash requires confirmation and permanently removes trashed copy records, related sales events, and photos not referenced elsewhere. Purge requires a warning confirmation followed by typing `PURGE`; it removes only the managed `data/` contents and retains root-level backups. Verify Database is read-only and reports database, foreign-key, recovery-operation, and photo-tree problems. Retry Storage Recovery is an explicit action for interrupted file operations.

## Deferred storage resilience

Interruption during backup creation or restoration, photo capture or replacement, legacy migration, conflicting legacy/portable data states, and unexpected shutdown between storage-operation steps need additional resilience testing and hardening. These are deferred edge cases, not confirmed failures; normal-operation tests do not establish their safety. Backup/restore and interruption recovery will be addressed in a dedicated future workstream.

An approved follow-up is a separate, explicit orphan-file cleanup action. **Verify Database** must remain read-only; cleanup must recheck both database and pending-operation references, ask for confirmation, and report exactly which files were removed or retained. That cleanup action is outside the current implementation scope.

## Important
- Online metadata lookup (Open Library, Google Books, and Booktopia) requires internet access; cataloging does not.
- BookLedger Mobile is not connected in this build; connection and scanning controls simulate phone events.
- Do not treat this early build as the sole storage location for irreplaceable catalog data until backup/restore testing is complete.
