# Test report

Date: 2026-10-18

## Full test suite

- Requested command: `.venv\Scripts\python.exe -m pytest`
- Final result: **91 passed, 0 skipped**.
- The sandbox blocked pytest's default Windows temporary-directory creation. The exact requested command was rerun with elevated filesystem access and completed with all tests passing.
- Earlier runs intermittently skipped one Tk-dependent intake UI test because this Python installation is missing Tcl/Tk runtime files (the missing file varied between `icons.tcl`, `notebook.tcl`, and other toolkit scripts). The final exact run initialized Tk successfully and did not skip it.
- Isolated workspace-temp command: `.venv\Scripts\python.exe -m pytest --basetemp=.pytest-work -q` — **91 passed, 0 skipped** on its final run.
- Coverage added for portable-root resolution, legacy database/photo and profile-config migration, source preservation and conflict detection, canonical photos and failed replacement, Trash isolation/LIFO restore/Clear Trash, Purge backup preservation, and read-only photo verification.
- Existing coverage includes catalog validation/status/sales, backup creation and restoration, metadata provider fallback/title normalization, and UI callback targeting.

## Additional checks

- `.venv\Scripts\python.exe -m compileall -q src/bookledger tests` — passed.
- `git diff --check` — passed; Git reports configured LF-to-CRLF conversion notices on edited files.

## Remaining verification

- Manual Windows GUI acceptance remains pending. Tk initialized in the final exact run, but earlier runs showed that the installed Tcl/Tk runtime can intermittently fail on missing scripts.
- No packaged executable or packaging specification exists, so frozen-path behavior is unit-tested but packaging is not verified.
- Legacy migration and Clear Trash/Purge have isolated tests but still need manual acceptance testing against a copy of real user data before release.
- Live provider connectivity and larger-catalog performance were not verified.

This remains an early development build. Keep independent backups of important catalog data while testing.
