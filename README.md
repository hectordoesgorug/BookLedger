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
- Optional Open Library metadata lookup with Google Books fallback; manual cataloging remains possible.
- Add Book intake form with photo preview, inline validation, and clear/retry/cancel actions.
- BookLedger Mobile connection and ISBN scanning are testable UI simulations; no phone networking is included.
- Inline form validation (no validation dialog for missing/invalid fields).
- Local database backup with photo files and integrity verification.
- Catalog photo-card grid and detailed sortable Inventory table over the same physical-copy records, with Genre, Condition, Location, and Status filters.
- Catalog cards open a read-only More Details view; Inventory double-click edits the selected copy. Catalog and Inventory have the same right-click actions for details, poster placeholder, status changes, edit, and safe delete placeholder.
- Canonical locations can be added, renamed (including updating assigned copies), and deleted when unused.
- Dashboard counters distinguish all physical copies (including Sold) from distinct bibliographic records. Sales and revenue summaries use recorded Price and Date Sold events.

This is an early development build, not a release candidate. Fuller reporting, exports/imports, additional metadata providers, Android integration, and Windows packaging are still planned. Multi-record duplicate selection and restore behavior have initial implementations and require broader edge-case testing.

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

Open **Settings → Google Books API** to save an optional API key or test connectivity. This Google Books integration currently works without a key. If provided, the key is stored as plain text in your Windows user profile (`%LOCALAPPDATA%\BookLedger\google_books.json`), protected by that account's file access controls; it is not stored in the project or included in portable BookLedger backups. Anyone with access to that Windows account can read it. Open Library remains the primary provider and missing fields from it are filled from Google Books where available. Provider values fill empty form fields only.

## Price and status behavior

Add and Edit use one **Price** field. It is editable while a copy is unsold and locked while Sold. The context menu's **Mark as Sold** records the current Price and today's local date without asking for separate sale details. New copies start as Available. Status reversals retain their historical sale events and revenue; marking Sold again adds a new history event. No refund or revenue-void workflow is defined. Create Poster and Delete Book are listed as context-menu placeholders; Delete Book does not delete data until the copy, photo, and sales-history policy is separately approved. Schema v3 migrates existing locations and sale records without dropping historic amounts or dates; make a backup before opening an older database with the updated application.

## Portable data
When run from source, data is stored in `BookLedger_Data/` in the project root. In a packaged build, data is stored next to the executable. Backups include a SQLite snapshot and compressed copy photos.

## Important
- Online metadata lookup requires internet access; cataloging does not.
- BookLedger Mobile is not connected in this build; connection and scanning controls simulate phone events.
- Do not treat this early build as the sole storage location for irreplaceable catalog data until backup/restore testing is complete.
