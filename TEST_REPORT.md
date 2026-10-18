# Test report

Date: 2026-10-18

## Full test suite

- `.venv\Scripts\python.exe -m pytest` — **86 passed, 61 errors**. The errors occurred before test bodies ran because pytest could not create numbered temporary directories under the sandbox-managed `%LOCALAPPDATA%\Temp\pytest-of-marlo` path.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-booktopia-full-report-final-20261018` — **148 passed, no skips in 18.75s**.
- `.venv\Scripts\python.exe -m pytest tests/test_booktopia.py tests/test_metadata.py -q --basetemp=.pytest-tmp-booktopia-focus-final-20261018` — **57 passed**.
- `.venv\Scripts\python.exe -m pytest tests/test_intake_ui.py -q -rs --basetemp=.pytest-tmp-booktopia-intake-regression-20261018` — **18 passed**.

The Booktopia tests use mocked HTTP responses and explicitly marked synthetic HTML fixtures; none were captured from Booktopia. They cover search-result selection, exact ISBN and ISBN-10/13 alias matching, rejection of mismatched or unverified pages, supported schema.org field extraction, missing descriptions, redirects, response limits, 404 versus HTTP errors, timeout reporting, provider ordering, skipped lookups, and non-overwriting field merges. The synthetic reference fixture uses ISBN `9780140449136` / `0140449132` to check the parser against the user-provided field shape; it does not establish that Booktopia currently serves those values in that markup. Tests also verify that Booktopia's 720-page value does not replace an earlier provider's 671-page value.

Existing metadata coverage includes the ten legacy reference ISBNs (`9780060515195`, `9780345351739`, `9780330352888`, `9780060846268`, `9780387004365`, `9780802713513`, `9780688123307`, `9780553070842`, `9780805056693`, `9780133266795`) for valid ISBN aliases and deterministic query construction; Open Library description precedence/fallbacks; Google Books matching-volume and query-variant behavior; safe error outcomes; and preservation of manual values. These tests are mocked/static evidence only. The legacy database does not identify which provider supplied its saved descriptions.

The remaining suite covers catalog validation, status transitions and sales history, backup/restore, portable paths and migration, Trash and photo lifecycle, recovery operations, verification, callback targeting, and Add Book UI behavior.

## Additional checks

- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed. Git emitted configured LF-to-CRLF conversion notices for edited files; no whitespace errors were reported.

## Live verification and limitations

- One live HTTPS request to `https://www.booktopia.com.au/book/9780140449136.html/` failed before HTTP with `No such host is known`. No Booktopia page, redirect, status code, or live metadata was observed. Open Library and Google Books live requests were likewise not verified because DNS resolution is unavailable in this environment.
- The [Booktopia Terms of Business](https://www.booktopia.com.au/termsOfBusiness) page reviewed here states that bibliographic data is copyrighted by Nielsen Book Services, publishers, or their licensors. It does not establish permission for automated metadata retrieval or describe a metadata API. `robots.txt` and the live product page could not be fetched from this environment, so access rules and current HTML remain unverified.
- Manual GUI acceptance remains pending. This environment intermittently failed to load Tcl/Tk during an earlier run, but the final full suite passed without skips and the focused intake UI run passed all 18 tests.
- No schema changes or runtime dependencies were added. Booktopia page structure, field coverage, and access policy may change; the integration remains best-effort. The page-count difference between the user's prior Open Library value (671) and observed Booktopia page (720) remains unresolved; the merge policy preserves the earlier value.

This remains an early development build. Keep independent backups of important catalog data while testing.
