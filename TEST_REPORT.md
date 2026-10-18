# Test report

Date: 2026-10-18

## Full test suite

- Command: `.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-meta-full-final-20261018 -rs`
- Latest result: **139 passed in 18.99s; no skips or failures**.
- The previously documented working-tree baseline was 133 passed; six deterministic regression tests were added, bringing the current collection to 139 passing tests.
- Focused metadata command: `.venv\Scripts\python.exe -m pytest tests/test_metadata.py -q --basetemp=.pytest-tmp-meta-final-20261018` — **35 passed**.
- Focused intake UI command: `.venv\Scripts\python.exe -m pytest tests/test_intake_ui.py -q --basetemp=.pytest-tmp-intake-final-20261018` — **17 passed, 1 skipped** because Tk could not initialize (`invalid command name "tcl_findLibrary"`). This display-dependent skip did not recur in the full-suite run.
- The metadata regression tests cover the ten legacy reference ISBNs (`9780060515195`, `9780345351739`, `9780330352888`, `9780060846268`, `9780387004365`, `9780802713513`, `9780688123307`, `9780553070842`, `9780805056693`, `9780133266795`) for valid ISBN-10 aliases and deterministic provider query construction. Mock responses also cover Open Library edition description string/object parsing, precedence and fallbacks; malformed/empty descriptions; Google Books scanning multiple matching candidates, ignoring unrelated descriptions, and continuing query variants when a verified match is sparse; and UI reporting when a partial result has no description.
- These ISBN tests are mocked/static regression evidence only. The legacy database contains saved descriptions for the ten references, but does not identify which provider supplied them.
- Coverage added for portable-root resolution, legacy database/photo and profile-config migration, source preservation and conflict detection, canonical photos and failed replacement, Trash isolation/LIFO restore/Clear Trash, Purge backup preservation, and read-only photo verification.
- Booktopia coverage uses saved HTML fixtures for matching ISBNs, mismatches, missing descriptions, malformed/unexpected pages, and ISBN-10/13 equivalence; mocked requests cover redirect policy, HTTP 404, fallback ordering, and response-size bounds.
- Existing coverage includes catalog validation/status/sales, backup creation and restoration, metadata provider fallback/title normalization, and UI callback targeting.

## Additional checks

- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git reports configured LF-to-CRLF conversion notices on edited files.

## Remaining verification

- Manual Windows GUI acceptance remains pending. The focused intake UI run intermittently failed Tk initialization, while the latest full run had no skips.
- No packaged executable or packaging specification exists, so frozen-path behavior is unit-tested but packaging is not verified.
- Legacy migration and Clear Trash/Purge have isolated tests but still need manual acceptance testing against a copy of real user data before release.
- Live Open Library and Google Books requests for the ten legacy reference ISBNs remain unverified. DNS lookups for `openlibrary.org` and `www.googleapis.com` both returned “No such host is known” before an HTTP request could be made, so there is no live status, provider response, matching-identifier, or returned-description evidence for any ISBN. Mocked tests establish query construction and parsing behavior only; they do not show that the providers currently return these records. Booktopia remains unconfigured and was not activated or live-tested. Larger-catalog performance was not verified.

This remains an early development build. Keep independent backups of important catalog data while testing.
