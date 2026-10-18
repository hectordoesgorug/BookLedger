# Test report

Date: 2026-10-18

## Full test suite

- Command: `.venv\Scripts\python.exe -m pytest --basetemp=.pytest-tmp -rs`
- Latest result: **119 passed, 1 skipped**.
- The skipped test was Tk-dependent; this Python installation hit a Tcl initialization error (`invalid command name "tcl_findLibrary"`). Focused intake UI run: `.venv\Scripts\python.exe -m pytest tests/test_intake_ui.py -q -rs --basetemp=.pytest-tmp` — **16 passed**.
- Coverage added for portable-root resolution, legacy database/photo and profile-config migration, source preservation and conflict detection, canonical photos and failed replacement, Trash isolation/LIFO restore/Clear Trash, Purge backup preservation, and read-only photo verification.
- Booktopia coverage uses saved HTML fixtures for matching ISBNs, mismatches, missing descriptions, malformed/unexpected pages, and ISBN-10/13 equivalence; mocked requests cover redirect policy, HTTP 404, fallback ordering, and response-size bounds.
- Existing coverage includes catalog validation/status/sales, backup creation and restoration, metadata provider fallback/title normalization, and UI callback targeting.

## Additional checks

- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git reports configured LF-to-CRLF conversion notices on edited files.

## Remaining verification

- Manual Windows GUI acceptance remains pending. Tk initialized in the final exact run, but earlier runs showed that the installed Tcl/Tk runtime can intermittently fail on missing scripts.
- No packaged executable or packaging specification exists, so frozen-path behavior is unit-tested but packaging is not verified.
- Legacy migration and Clear Trash/Purge have isolated tests but still need manual acceptance testing against a copy of real user data before release.
- Live Booktopia connectivity and its sample ISBN URL could not be verified from this environment because DNS/network access failed. Indexed Booktopia product pages show a title slug followed by `/book/{ISBN}.html`; runtime handling follows only HTTPS Booktopia redirects and validates final URL/page ISBN evidence. Other live provider connectivity and larger-catalog performance were not verified.

This remains an early development build. Keep independent backups of important catalog data while testing.
