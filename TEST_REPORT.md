# Test report

Date: 2026-10-18

## Automated tests

- Full-suite command: `.venv\Scripts\python.exe -m pytest`.
- Result: **78 passed, 2 skipped**.
- The Windows sandbox required pytest's `TEMP` and `TMP` directories to be redirected to a temporary folder inside the project workspace; the test command itself was unchanged.
- Both skipped tests are Tk UI tests in `tests/test_intake_ui.py`. The installed Python runtime cannot find Tcl's `init.tcl`, so the tests cannot initialize their Tk windows. This is an environment limitation, not a passing UI verification.
- Coverage includes catalog validation and status transitions, sold-last ordering and presentation, location migration and rename propagation, append-only sale history and v1-to-v3 migration, backup and restore, metadata fallback and settings behavior, and context-menu callback targeting.
- Provider calls are mocked. Live Google Books connectivity and native GUI behavior were not verified.

## Additional checks

- `.venv\Scripts\python.exe -m py_compile src\bookledger\app.py src\bookledger\ui\forms.py src\bookledger\services\catalog.py src\bookledger\services\metadata.py src\bookledger\db\database.py src\bookledger\paths.py` — passed.
- `git diff --check` — passed. Git emitted only configured LF-to-CRLF conversion notices.

## Remaining verification

- Native Windows visual review remains pending because this Python installation's Tcl/Tk runtime is incomplete.
- Live Google Books connectivity, packaged executable behavior, and larger-catalog performance remain unverified.

This is an early development build, not a release candidate. Keep independent backups of important catalog data while testing.
