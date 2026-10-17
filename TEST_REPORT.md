# Test report

Date: 2026-10-17

## Automated tests

- Full-suite command: `.venv\Scripts\python.exe -m pytest -q -rs` with `TEMP` and `TMP` redirected to a temporary directory inside the writable project workspace because the sandbox Windows temp location rejected pytest directory creation.
- Result: **41 passed, 2 skipped**.
- Both skips are Tk UI tests: this Python installation has incomplete Tcl/Tk runtime files (`tk.tcl` and supporting Tcl/Tk files), so those windows cannot be initialized reliably.
- Coverage includes service validation and duplicate rules, database v1-to-v2 migration, location registry and safety, contextual asking/transaction prices, retained sales history, backup creation and restoration, merged metadata fallback, and Google Books API-key query behavior.
- Metadata provider calls are mocked in automated tests. The Google Books connectivity action itself was not exercised against the live service.

## Additional checks

- `.venv\Scripts\python.exe -m py_compile src\bookledger\app.py src\bookledger\ui\forms.py src\bookledger\services\catalog.py src\bookledger\services\metadata.py src\bookledger\db\database.py src\bookledger\paths.py` — passed.
- `git diff --check` — passed. Git printed only configured LF-to-CRLF conversion notices.

## Remaining verification

- Native Windows visual review of the new Settings dialogs, Catalog More Details view, Inventory status action, and revised Add/Edit forms remains pending because the installed Tcl/Tk runtime is incomplete.
- Live Google Books connectivity, packaged executable behavior, and larger catalog performance remain unverified.

This is an early development build, not a release candidate. Keep independent backups of important catalog data while testing.
