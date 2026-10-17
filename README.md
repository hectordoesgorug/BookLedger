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
- Optional Google Books metadata lookup adapter; manual cataloging remains possible.
- Inline form validation (no validation dialog for missing/invalid fields).
- Local database backup with photo files and integrity verification.
- Search/filter catalog and inventory, basic dashboard, sales view, settings, and summary report.

This is an early development build, not a release candidate. Fuller reporting, exports/imports, additional metadata providers, Android integration, and Windows packaging are still planned. Multi-record duplicate selection and restore behavior have initial implementations and require broader edge-case testing.

## Run from source
Requires Python 3.10+ and Tkinter. On Windows, run `run_bookledger.bat`; or install manually:

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -e .
python -m bookledger
```

On Linux/macOS, install Tk support for your Python distribution, then `pip install -e .` and run `python -m bookledger`.

## Run tests

```bash
pip install -e .[dev]
pytest -q
```

## Portable data
When run from source, data is stored in `BookLedger_Data/` in the project root. In a packaged build, data is stored next to the executable. Backups include a SQLite snapshot and compressed copy photos.

## Important
- Online metadata lookup requires internet access; cataloging does not.
- The Android companion is not included in this build.
- Do not treat this early build as the sole storage location for irreplaceable catalog data until backup/restore testing is complete.
