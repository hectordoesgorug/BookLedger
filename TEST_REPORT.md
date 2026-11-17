# Test report history

Record started: 2026-10-19; latest dated entry: 2026-11-17.

This is a record of specific test runs, investigations, and owner-reported physical tests, not a current comprehensive validation certificate. Results and limitations apply to the dates and environments recorded in each section. The 2026-11-15 Milestone 5 source-level run did not establish clean-machine Windows compatibility or physical Android end-to-end transfer/cataloging; the separate owner-reported final-asset session on 2026-11-16 is recorded below.

## Catalog performance investigation (2026-11-17)

Synthetic libraries were created in disposable temporary directories at 20, 100, 500, and 1,000 copies. They used varied titles, authors, genres, statuses, prices, locations, and optional metadata, plus a representative 1,200 × 1,800 JPEG cover. Database query timings are medians of five calls; sort timings are medians of seven calls through 500 rows and one call at 1,000 rows; image timings include opening, RGB conversion, thumbnail resizing, and Sold tinting. The same generated JPEG was reused per row to make the repeated image-processing cost comparable. The image benchmark used three-run medians through 500 rows and one run at 1,000 rows because of runtime. The OS file cache was warm during the repeated image runs; cold disk startup was not isolated, and the application has no thumbnail cache.

| Copies | Full query median | Filtered query median | Sort | Image baseline | Image optimized |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | 0.93 ms | 0.86 ms | 0.01 ms | 283.22 ms | 219.31 ms |
| 100 | 1.71 ms | 1.55 ms | 0.03 ms | 1,392.77 ms | 1,110.66 ms |
| 500 | 6.36 ms | 4.59 ms | 0.13 ms | 6,965.84 ms | 5,468.12 ms |
| 1,000 | 11.58 ms | Not measured | 0.42 ms | 13,376.46 ms | 11,182.95 ms |

The dominant measured separable stage was repeated image processing. The app retrieves records once per population and sorts them in memory; no N+1 query path was found. Reusing a loaded RGB image for the resize avoids an extra full-resolution RGB copy while preserving full-resolution sampling. Exact pixel comparisons against the prior processing sequence passed for synthetic RGB JPEG and RGBA PNG covers, including Sold tinting. A faster JPEG draft-resize alternative was rejected after visual inspection showed fine-detail artifacts.

No thumbnail cache, background worker, pagination, or virtualization was added: these add invalidation, memory, or interaction complexity, and the measured full-resolution resize change improves the image stage by about 16–23%. Actual widget construction, complete refresh/navigation timing, scrolling responsiveness, and process memory were not measured. The local Tcl/Tk installation lacks required ttk theme files, so full visual card validation remains unverified.

- `.venv\Scripts\python.exe -m pytest tests\test_catalog.py tests\test_catalog_card_text.py tests\test_app_callbacks.py -q -rs --basetemp=.pytest-tmp-issue11-catalog-final` — **138 passed, 1 skipped**. The skipped Tk geometry test could not load Tcl/Tk files.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-issue11-full` — **507 passed, 18 skipped**. Tk UI tests skipped because the installed Tcl/Tk distribution is missing required files, including ttk theme assets.
- The two added thumbnail pixel-preservation cases are included in the focused and full-suite totals.

## Initial final-asset physical smoke session (owner reported, 2026-11-16)

The owner reported performing this physical session with the exact final Windows ZIP and Android APK after verifying the assets. Codex did not perform or independently observe these physical tests. The owner reported no errors. The Windows device was described as a Windows 11 laptop; device model, Windows build, Android model/OS, and whether Android installation was fresh or an upgrade were not supplied.

| # | Result | Owner-reported scenario |
| ---: | --- | --- |
| 1 | PASS | Windows ZIP size and SHA-256 matched. |
| 2 | PASS | Fresh Windows extraction and launch without Python. |
| 3 | PASS | Desktop version, navigation, Settings, About, and theme selection. |
| 4 | PASS | Disposable book add, edit, search, and photo handling. |
| 5 | PASS | Exact Android APK verified and installed/upgraded; fresh-install versus upgrade was not specified. |
| 6 | PASS | Android version and camera permissions. |
| 7 | PASS | ISBN scanning, manual ISBN entry, and No ISBN. |
| 8 | PASS | Photo capture and preview. |
| 9 | PASS | Single Entry and Bulk Entry workflows. |
| 10 | PASS | QR and manual pairing. |
| 11 | PASS | Single Entry transfer with ISBN and photo. |
| 12 | PASS | Bulk Entry transfer. |
| 13 | PASS | Desktop cataloging and duplicate handling. |
| 14 | SKIPPED | Backup and persistence after restart. The owner deliberately omitted this from the final session and reports rigorous prior testing. |
| 15 | SKIPPED | Automatic reconnection after restart. The owner deliberately omitted this from the final session and reports rigorous prior testing. |

**Session total: 13 PASS, 2 SKIPPED, 0 FAIL.** These two scenarios were deliberately omitted from this session and are retained as SKIPPED in its historical record. The owner reported that both had been rigorously tested previously. No device-specific details or install-versus-upgrade distinction have been inferred for this session.

## Follow-up of previously skipped scenarios (owner reported, 2026-11-16)

The owner subsequently reported rerunning both scenarios that were skipped in the session above:

| Scenario | Result | Owner-reported outcome |
| --- | --- | --- |
| Windows backup and persistence after restart | PASS | The previously skipped physical smoke scenario passed in the follow-up round. |
| Android/desktop automatic reconnection after restart | PASS | The previously skipped physical smoke scenario passed in the follow-up round. |

The owner reports the latest aggregate across the 15 scenarios as **15 PASS, 0 FAIL, 0 SKIPPED**. This cumulative latest status combines the original session's 13 reported passes with these two subsequently reported passes; it does not change the original session's 13 PASS / 2 SKIPPED record. Codex did not perform or independently observe either physical test round. The follow-up clarification does not specify whether these two reruns used the exact final release assets, and supplies no additional device or OS details.

## Configurable metadata provider registry

Implementation adds a central provider registry and a versioned root `config.json` for enabled states and lookup priority, with a per-user fallback when the portable root is read-only. Settings includes functional drag reordering and Restore Defaults. Lookup stops when title, author, genre, publisher, and publication year are available; edition, format, synopsis, and page count are optional enrichment. Google Books credentials remain in their existing separate file. Inventory Purge preserves provider configuration.

- `.venv\Scripts\python.exe -m pytest tests\test_provider_settings.py tests\test_metadata.py tests\test_booktopia.py tests\test_portable_lifecycle.py -q --basetemp=.pytest-tmp-provider-focused-final` — **91 passed**.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-provider-full-final` — **170 passed, 2 skipped**. Tk could not initialize because required Tcl/Tk files are missing; Settings drag/drop was not runtime-tested.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git reported configured LF-to-CRLF notices only.

## Direct ISBN fallback follow-up

- `.venv\Scripts\python.exe -m pytest tests/test_booktopia.py -q --basetemp=.pytest-tmp-direct-isbn-focused-final2` — **36 passed**.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-direct-isbn-full-final2` — **160 passed, 1 skipped**. The skipped Tk UI test could not initialize Tcl/Tk in this environment.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git emitted configured LF-to-CRLF notices only.

The `9780553290998` direct-fallback test uses synthetic HTML with the user-provided ISBN, title, and author; its synopsis text is explicitly synthetic and no live response was captured. The test simulates the search HTTP error followed by the direct ISBN request resolving to the reported canonical URL. The user's browser observations remain the only live evidence for this listing; no live request for it was made in this environment. A live recheck of both the search and canonical URLs for `9780716736387` failed at DNS resolution (`[Errno 11001] getaddrinfo failed`), so the response code, redirect path, and error-body content remain unverified.

## Booktopia unavailable HTTP-response follow-up

- `.venv\Scripts\python.exe -m pytest tests/test_booktopia.py -q --basetemp=.pytest-tmp-booktopia-http-body-focused` — **33 passed**.
- `.venv\Scripts\python.exe -m pytest` — **97 passed, 61 setup errors** because pytest could not create `tmp_path` directories under the sandbox's AppData temp path.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-unavailable-listing-full` — **157 passed, 1 skipped**. The skipped Tk UI test could not load the installed Tcl/Tk `ttk/spinbox.tcl` file.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git emitted configured LF-to-CRLF notices only.

Live requests to the ISBN `9780716736387` search and canonical product URLs failed with `URLError: [Errno 11001] getaddrinfo failed`; the available web view also could not open either URL. Therefore the live HTTP status, redirect chain, and presence of a usable error response body remain unknown. The parser tests use only synthetic fixtures. The unavailable-product fixture now uses a generic synthetic ISBN and does not claim to represent the observed listing.

## Latest synopsis-policy changes

- `.venv\Scripts\python.exe -m pytest tests/test_booktopia.py tests/test_metadata.py -q --basetemp=.pytest-tmp-synopsis-policy-focused-final3` — **64 passed**.
- `.venv\Scripts\python.exe -m pytest tests/test_intake_ui.py -q -rs --basetemp=.pytest-tmp-synopsis-policy-intake-final2` — **18 passed, no skips**.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-synopsis-policy-full-final2` — **155 passed, no skips** in 19.27s.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git emitted only configured LF-to-CRLF notices.

## Coverage and behavior

Open Library tests confirm title, author, publisher, publication year, and page count remain available while edition descriptions, notes, excerpts, and linked-work descriptions never populate Book Details/Synopsis. The linked-work API request is no longer made solely to retrieve a synopsis. ISBN `9780716736387` has a deterministic regression for the observed bibliographic notes.

Booktopia tests use mocked responses and synthetic HTML fixtures, not captured site responses. They verify explicit tab-to-panel relationships, rejection of a tab ID without a relationship, panel text taking precedence over structured bibliographic notes, filtering author/review/recommendation sections, rejection of generic meta descriptions and purchase copy in matching Book JSON-LD, safe empty synopsis results, ISBN aliases, matching-product checks, unavailable-product status, and HTTP/network error distinctions. The existing `9780140449136` and `9781923058507` cases use synthetic fixtures to test matching synopsis extraction; their earlier manual GUI checks are separate observations and do not make the fixtures captured responses. The unavailable-product behavior uses a generic synthetic ISBN fixture, not `9780716736387`. No captured Booktopia response for the unavailable `9780716736387` page is available.

The previous Booktopia parser collected unqualified body `itemprop="description"`, schema.org descriptions, and generic `description`/Open Graph metadata, without identifying a Description tab's associated panel. That allowed bibliographic notes and retail SEO text to be treated as Book Details. The revised parser only trusts a panel when the identified tab explicitly references it, or a matching schema.org Book description after filtering recognized note and retail boilerplate patterns. Unassociated `itemprop="description"` and generic meta descriptions are ignored. If no usable synopsis exists, it leaves the field empty. A matching page marked with an explicit unavailability message or structured `OutOfStock`, `Discontinued`, or `SoldOut` state reports `Product unavailable`. For HTTP error responses, the bounded HTML body is parsed only when the final URL is the requested ISBN's canonical product URL; metadata is accepted only with matching page ISBN evidence and supported values. Error pages that do not meet those checks retain their provider-error status.

## Live investigation limits

No raw current Booktopia HTML or sanitized live capture was available in the development environment. The web-rendered indexed text snapshot for [Crime and Punishment, ISBN 9780140449136](https://www.booktopia.com.au/crime-and-punishment-fyodor-dostoyevsky/book/9780140449136.html) (crawled 1.1 years ago) and [The Strength of the Few, ISBN 9781923058507](https://www.booktopia.com.au/the-strength-of-the-few-james-islington/book/9781923058507.html) (crawled two weeks ago) shows substantial text beneath a Description label, but the transformed snapshots do not expose HTML attributes or response timing. They cannot establish whether the text is in the initial HTTP response, a hidden panel, embedded structured data, or a later browser request. The current page for [The Triumph of Evolution, ISBN 9780716736387](https://www.booktopia.com.au/the-triumph-of-evolution-niles-eldredge/book/9780716736387.html) could not be read through the available web view, and direct requests failed DNS resolution. Thus the live response status, redirect chain, and presence or absence of usable error-body HTML remain unverified; the prior synthetic test is no longer presented as evidence about that listing.

The extraction change is **not yet verified against Booktopia's actual live tab-to-panel markup**. The synthetic fixtures prove the relationship-based parser and rejection policy only. Do not treat them as captured evidence or claim that live synopsis extraction is confirmed. A sanitized current response or inspected relationship from the user's browser is still needed to verify the actual selector and availability signal. If the page structure does not expose a relation supported by the parser, Book Details will remain empty rather than use generic text.

The integration remains best-effort and subject to site changes and access policies. No schema or runtime dependency changes were made. The rest of the suite covers catalog validation, sales and status transitions, backup/restore, portable paths and migration, Trash and photo lifecycle, recovery, verification, callbacks, and intake UI behavior. Manual native-Windows GUI acceptance remains pending.

## Archive.org metadata provider integration

- `.venv\Scripts\python.exe -m pytest -q tests\test_archive_org.py tests\test_provider_settings.py tests\test_provider_diagnostic.py tests\test_metadata.py tests\test_booktopia.py --basetemp=.pytest-tmp-archive --tb=short` — **136 passed, 13 skipped**.
- `.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-archive --tb=short` — **364 passed, 14 skipped, 4 failed**. The failures are existing missing-bundled-logo failures in `test_app_callbacks.py` and `test_resources.py`; `assets/generalists_bookshop_logo.png` is absent from this checkout.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git reports configured LF-to-CRLF notices only.

The Archive.org provider is registered after Google Books and before Booktopia. Fresh settings use that order; a legacy saved order is retained and Archive.org is appended as enabled when absent. The existing registry-driven Metadata Sources priority list and ISBN Lookup Test expose Archive.org. Search requests only identifier, title, creator, publisher, year, edition, and description for up to ten results. Distinct records are kept separate, and ambiguous candidates are checked by item metadata for the requested ISBN (or valid ISBN-10/13 equivalent), up to three records.

The normal `run_bookledger.bat` launcher opened the application. Manual inspection showed Archive.org in the enabled provider list and independent diagnostic selector; an Archive.org diagnostic run reported a provider lookup error and 0.04 seconds because DNS resolution is unavailable. Direct live requests for all four requested ISBNs likewise failed DNS resolution before receiving an Archive.org response. Consequently, no live candidate quality, description, or server timing is confirmed. Mocked tests cover candidate selection, exact ISBN verification, mapping, errors, timeouts, configuration migration, registry order, and diagnostic fields.

## Poster creation implementation

- `.venv\Scripts\python.exe -m pytest --basetemp=.pytest-tmp-poster tests\test_posters.py tests\test_app_callbacks.py tests\test_uuid_backup_restore.py tests\test_portable_lifecycle.py -q -rs --tb=short` — **69 passed, 1 skipped**.
- `.venv\Scripts\python.exe -m pytest --basetemp=.pytest-tmp-poster -q -rs --tb=short` — **319 passed, 13 skipped**. Skips require the complete Tcl/Tk library or a display; this Python environment is missing Tk files such as `ttk/sizegrip.tcl` and `ttk/scrollbar.tcl`.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git emitted configured LF-to-CRLF notices only.

Automated tests cover schema v8 migration, preset persistence and sequencing, shared background cleanup, relative background resolution and fallback storage, title and price formatting, normalized element geometry, PNG export, backup/restore of templates and poster files, read-only application-assets restore fallback, and purge preservation of unrelated files. Visual inspection and a real launcher/UI smoke test were not possible because Tcl/Tk is incomplete in this environment.

## Mobile connectivity completion (2026-11-02)

- `.venv\\Scripts\\python.exe -m pytest tests\\test_mobile_network.py tests\\test_credential_protection.py tests\\test_mobile_connection.py -q` — **32 passed**.
- `.venv\\Scripts\\python.exe -m pytest -q -rs` — **443 passed, 18 skipped**. All skips require the complete Tcl/Tk library; this environment lacks `ttk/sizegrip.tcl`. The four missing bundled-logo failures are resolved by the intended blank-logo behavior.
- `flutter analyze` — passed with no issues.
- `flutter test` — **54 passed**.
- `dart format --output=none --set-exit-if-changed lib test` — **24 files checked, 0 changed**.
- Android `assembleDebug` — **BUILD SUCCESSFUL** with Android Studio JBR, one Gradle worker, Kotlin in-process, and Kotlin incremental compilation disabled.
- `git diff --check` — passed; Git emitted configured LF-to-CRLF notices.

On the Poco X6, the Android secure-storage write/read probe passed. The client initially rejected its own API paths because its allowlist contained escaped prefix text. After that correction, the desktop returned HTTP 400: Dart had sent a chunked JSON body while the Python handler required `Content-Length`. Setting the byte length fixed the request. QR pairing and manual pairing then both completed; the desktop showed the paired device, authenticated reconnect succeeded, the token survived a full app force-stop/relaunch, and connection recovered after desktop restart and Wi-Fi interruption/recovery. Logs report status/phase only and do not include pairing credentials or device tokens.

The desktop DNS-SD service advertised on the tested Wi-Fi network. Changed-IP recovery has automated ordering coverage, but an IP change was not reproduced on the Poco, so Android NSD discovery after an actual DHCP change remains unverified. Windows Mobile Hotspot pairing and multicast discovery were not physically tested. No Windows Firewall rules were modified. The configured shop logo remained visible; the logo file itself was left untouched.

## Milestone 5 mobile transfer and desktop cataloging (2026-11-15)

- Targeted staging/catalog regression run: `.venv\\Scripts\\python.exe -m pytest tests/test_mobile_incoming.py tests/test_catalog.py tests/test_posters.py -q` — **88 passed**.
- Full Python suite: `.venv\\Scripts\\python.exe -m pytest -q` — **449 passed, 18 skipped**. Skips are Tk/UI tests requiring unavailable Tcl/Tk components.
- `flutter analyze` — **no issues**.
- `flutter test` — **59 passed**.
- `dart format --output=none --set-exit-if-changed lib test` — **24 files checked, 0 changed**.
- Android debug APK: Flutter's `build apk` wrapper hit the known Kotlin incremental-cache cross-drive issue; direct Android Studio JBR Gradle `assembleDebug` succeeded with Kotlin in-process, incremental compilation disabled, and one worker.
- `git diff --check` — passed.

Automated tests cover validated and idempotent staging, duplicate/nullable ISBNs, batch ordering and readiness, transfer callbacks, recovery after restart, and preserving the incoming UUID through durable catalog save. Physical Poco X6 end-to-end transfer/cataloging and native Tk UI interaction were not performed in this turn. No transfer retry behavior was tested against a live desktop/device pair.

## Catalog sorting direction toggle (2026-11-17)

- `.venv\Scripts\python.exe -m pytest -q tests/test_app_callbacks.py -k catalog_sort` — **3 passed**.
- `.venv\Scripts\python.exe -m pytest -q tests/test_app_callbacks.py tests/test_catalog.py` — **130 passed, 1 skipped**.
- `.venv\Scripts\python.exe -m pytest -q -rs` — **497 passed, 19 skipped, 1 failed**. The failure is `test_photo_preview_and_manual_metadata_values_are_preserved`, where the Tk photo preview did not resize after a window geometry change; the same assertion reproduced in isolation and was observed during Handover #46 validation. Skips require missing Tcl/Tk files, including `init.tcl`, `ttk/utils.tcl`, and `ttk/sizegrip.tcl`.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git reports configured LF-to-CRLF notices only.

Catalog sorting tests cover Title, Copy ID, and Price in both directions, case-insensitive title comparison, numeric keys, explicit Copy ID tie-breaking, empty and single-row inputs, active filter forwarding, re-sorting refreshed records, direction toggling, and sort preference retention across navigation. The incomplete Tcl/Tk runtime prevented visual verification of the arrow control and its tooltip in the running desktop UI.

## Catalog card second-line clipping (Issue #12 follow-up, 2026-11-17)

- `.venv\Scripts\python.exe -m pytest -q -rs tests/test_catalog_card_text.py tests/test_app_callbacks.py tests/test_catalog.py` — **136 passed, 1 skipped**; the skipped pre-existing display test could not load Tcl/Tk `init.tcl`.
- `.venv\Scripts\python.exe -m pytest -q -rs` — **504 passed, 19 skipped**. Two Tk UI tests could not load Tcl/Tk files; 17 provider diagnostic UI tests require `ttk/sizegrip.tcl`.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git reports configured LF-to-CRLF notices only.

The new widget geometry test passed in the focused run. It checks the measured two-line `ttk.Label` request—including descenders—fits the text area and that short and truncated values keep equal text-area and card heights. Full-suite execution later skipped that Tk test because `tk.tcl` was unavailable. In the available Tk runtime, a 17 px line spacing yielded a 34 px two-line frame while the actual two-line label requested 38 px; the card area now uses the active font/theme label's measured request instead of line spacing alone. Full desktop visual inspection remains pending.

## Catalog card text layout (Issue #12, 2026-11-17)

- `.venv\Scripts\python.exe -m pytest -q -rs tests/test_catalog_card_text.py tests/test_app_callbacks.py tests/test_catalog.py` — **136 passed, 1 skipped**. The skipped display test could not load Tcl/Tk `ttk/sizegrip.tcl`.
- `.venv\Scripts\python.exe -m pytest -q -rs` — **505 passed, 18 skipped**. One UI test could not load `init.tcl`; 17 provider diagnostic UI tests require the missing `ttk/sizegrip.tcl`.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git reports configured LF-to-CRLF notices only.

Pure text tests cover one-line, two-line, overflowing, long unbroken, and empty values. A Tk geometry test passed for mixed short and long text, confirming two-line areas and equal overall card heights; database tests confirm complete title and author values remain in Catalog and More Details. A full app visual review was not performed.
