## Provider defaults and candidate feasibility — November 20, 2026

Baseline: clean `main` at `5fe714fc36e6fee2c4ddc4301da1b608e98b754c`, matching the local `origin/main` reference. Hardcover is now enabled before Booktopia in fresh/default configurations. Bigbook remains disabled and available for manual activation. Explicit saved ordering and enabled states are preserved. The existing missing-token guard makes no network request and permits later-provider fallback; the regression checks its authentication diagnostic and Booktopia completion. Provider authentication, schemas and persistence were not redesigned.

- `.venv\Scripts\python.exe -m pytest tests/test_provider_settings.py tests/test_archive_org.py tests/test_booktopia.py tests/test_metadata.py tests/test_hardcover.py tests/test_provider_diagnostic.py tests/test_intake_ui.py -q -rs`: **223 passed, 17 skipped, 0 failed** in 15.25 seconds. Skips cite missing Tcl/Tk files or unavailable initialization. Coverage includes fresh defaults, configurations without provider preferences, preserved customized settings/configuration bytes, missing-token no-network behavior, chain fallback, aggregation, diagnostics and default provider status rows.
- `.venv\Scripts\python.exe -m pytest -q -rs`: **601 passed, 19 skipped, 1 failed** in 54.25 seconds. `test_form_minimum_size_keeps_scrollable_content_reachable` again failed because body and viewport heights were both 798, making `798 > 798` false. The mobile connection assertions passed in this run; their earlier intermittent failures remain unresolved. Tcl/Tk failures account for the skips. No assertion was weakened or failure suppressed, and this run does not establish that intermittent failures are fixed.
- `.venv\Scripts\python.exe -m compileall -q src tests` and `git diff --check`: **passed**. Git emitted configured LF-to-CRLF notices only.
- Official ISBNdb, Goodreads and OCLC documentation was reviewed for [candidate feasibility](docs/METADATA_PROVIDER_FEASIBILITY.md). No candidate catalog API requests, subscriptions, trial activations, purchases or new credentials were used. Public documentation and OpenAPI access do not establish live metadata coverage or latency. ISBNdb's browser-readable terms impose retention/deletion conditions; Goodreads has no established obtainable public developer route; OCLC eligibility and reuse restrictions block a general independent-user catalog integration.

Issue #2 was inspected and remains open for review and disposition of all three candidates. No issue-description change, completion comment or closure was performed. Native Windows acceptance of the defaults/diagnostic presentation was not performed; automated checks and prior live provider samples have narrower scope.

## Metadata provider compatibility — November 20, 2026

Baseline: clean `main` at `780798f3442dc3ea3008c9a93cc3ebc305006156`, matching the local `origin/main` reference. Existing description shortening is integrated. This reassessment used public bibliographic identifiers, existing local credentials loaded through `AppConfigStore`, and read-only HTTPS requests. No library database, inventory, backups, provider order, enablement, or credentials were changed. The root configuration bytes were checked before and after the bounded sample run and were unchanged; the profile fallback was absent. Credential values and raw exception bodies are excluded from this report.

### Contract findings

The [official Hardcover documentation repository](https://github.com/hardcoverapp/hardcover-docs/tree/d9439f56e9eccca6d4589fb6897068b12bc3d045) was inspected at `d9439f56e9eccca6d4589fb6897068b12bc3d045`. Its [GraphQL schema](https://github.com/hardcoverapp/hardcover-docs/blob/d9439f56e9eccca6d4589fb6897068b12bc3d045/schema.graphql) and successful authenticated live introspection show that `books.author_names`, `books.genres`, and `editions.description` are absent. Older rendered schema pages still list those fields, so they were not used as the current contract.

The query now requests edition/book contributions with author names, book description, and `book.cached_tags`. Only explicit `Author` contributions populate Author, preferring edition credits and falling back to work credits. Only the `Genre` category supplies Genre; mood and general tags do not. Genre still must satisfy the catalog's approved list. Edition title takes precedence over work title. Publisher, release fields, edition information/format, and pages use supported fields; missing fields remain optional. Both ISBN forms are queried, and unrelated returned identifiers remain rejected.

The [current getting-started source](https://github.com/hardcoverapp/hardcover-docs/blob/d9439f56e9eccca6d4589fb6897068b12bc3d045/src/content/docs/api/Getting-Started.mdx) describes PAT permissions and user-selected expiration introduced after the legacy token system. Its capability map lists catalog read scopes for editions, books, contributions, authors, and publishers; no write scope is needed by this adapter. Actual least-privilege-token enforcement was not live-tested. Legacy tokens can have access equivalent to `all`; the former fixed January 1 expiry description should not be applied to every current PAT. Bearer authentication succeeded; the separate bare-token probe returned HTTP 400. Saved credentials may contain either a bare token or a Bearer prefix; requests now send exactly one prefix. HTTP and GraphQL failures retain sanitized classifications. The current free plan documents 5,000 daily requests, 60 per minute, and burst capacity 10. Each top-level alias counts toward quota; the two ISBN selections cost two units per lookup. Live rate headers agreed with those limits. The old rendered maximum-depth statement was not assumed to apply: the corrected query with nested contributions was accepted live.

[Hardcover's OAuth guidance](https://github.com/hardcoverapp/hardcover-docs/blob/d9439f56e9eccca6d4589fb6897068b12bc3d045/src/content/docs/api/OAuth.mdx) recommends OAuth for applications used by others. PAT entry remains suitable for a personal tool but is not the recommended long-term distributed-app sign-in design. A separately scoped OAuth/PKCE implementation and appropriate token storage should be assessed before promoting Hardcover as a default provider. No OAuth implementation or credential migration was performed. Only public catalog metadata was requested; no user-library or account mutations were attempted.

[BigBook's official documentation](https://bigbookapi.com/docs/) confirms `GET /search-books?isbn=...`, nested `books` groups, `GET /{id}`, and `x-api-key` authentication. Live responses agreed. The detail sample supplies title, authors, description, numeric publication year and page count. Publisher, edition, genre, and SRP are not inferred. The documented/live sample puts ISBN-10 `0439139597` in both ISBN fields; ISBN equivalence still verifies it for `9780439139595`. This is not evidence that other editions can be accepted without matching identifiers. Missing or malformed `books` arrays now produce an invalid-response failure rather than a confirmed miss. Transport errors from both adapters are sanitized, including exception messages that contain credentials.

BigBook documents daily quotas, free-plan throughput of 60 requests per minute, HTTP 402 for exhausted daily allocation, and HTTP 429 for rate limiting. Quota headers were observed on every successful sample response. The tested account began with 50 daily units and ended with 41; this is an observed account allocation, not a promise about every plan. Search and detail calls continue to share one five-second provider budget. No live retries or automatic backoff were used.

### Bounded live requests

Hardcover: ten POST requests total to `https://api.hardcover.app/v1/graphql`. No tokens were included in the URL or GraphQL variables.

| Request | Selection/input | Observed outcome | Total duration |
| --- | --- | --- | --- |
| 1 | Introspection of edition, book, and contribution field names | Bearer accepted; HTTP 200, no GraphQL errors | 0.964 s |
| 2 | Original adapter, `9780547928227` | Lookup failed, provider classification; HTTP status was not captured for this baseline call | 0.793 s |
| 3 | Corrected contract probe, `9780547928227`, one edition plus public credits/tags | HTTP 200; verified ISBN and supported fields | 0.825 s |
| 4 | Bare-token comparison, edition ID 0 with limit 1 | HTTP 400; no account records requested | 0.835 s |
| 5 | Repaired adapter, fiction `9780547928227` | HTTP 200; title, author, ISBN, genre, publisher, year, edition, pages, description | 1.105 s |
| 6 | Repaired adapter, nonfiction `9780062316097` | HTTP 200; same nine fields | 1.026 s |
| 7 | Repaired adapter, academic `9780306406157` | HTTP 200; same fields except genre | 0.873 s |
| 8 | Repaired adapter, equivalent ISBN-10 `054792822X` | HTTP 200; same nine fields as fiction ISBN-13 | 1.056 s |
| 9 | Repaired adapter, synthetic `9780000000002` | HTTP 200; unexpectedly matched a sparse record: title, author, ISBN, genre, year | 0.833 s |
| 10 | Synthetic `9799999999990`, direct edition ISBN-13 selection | HTTP 200; empty edition list, no GraphQL errors | 0.790 s |

Requests 5–9 used the adapter's `byIsbn13` and `byIsbn10` selections with the entered ISBN and its valid equivalent. Every retrieved adapter result passed identifier verification. The synthetic ISBN in request 9 is not a reliable no-result fixture: the service actually contains a record for it. Request 10 establishes an empty live result; it does not establish that every synthetic identifier will be absent.

BigBook: nine GET requests total to `https://api.bigbookapi.com`, all with `x-api-key` authentication and no key in the URL.

| Request | Path/input | Observed outcome | Total duration |
| --- | --- | --- | --- |
| 1 | `/search-books?isbn=9780547928227` | HTTP 200, empty books | 1.147 s |
| 2 | `/search-books?isbn=9780062316097` | HTTP 200, empty books | 0.593 s |
| 3 | `/search-books?isbn=9780306406157` | HTTP 200, empty books | 0.578 s |
| 4 | ISBN-10 input `054792822X`, normalized request `/search-books?isbn=9780547928227` | HTTP 200, empty books | 0.240 s |
| 5 | `/search-books?isbn=9780000000002` | HTTP 200, empty books | 0.641 s |
| 6 | `/16384516`, the official documentation example | HTTP 200, title, authors, description, year, pages, equivalent ISBN-10 | 0.680 s |
| 7 | `/search-books?isbn=9780439139595` | HTTP 200, nested group containing ID 16384516 | 0.795 s |
| 8–9 | Complete adapter lookup for `9780439139595`: same search followed by `/16384516` | Both HTTP 200; Retrieved with verified ISBN and six mapped fields | 0.900 s total; response-opening times 0.667/0.232 s |

Empty searches establish limited coverage for these exact identifiers at this time, not a confirmed endpoint defect. The successful documentation example establishes live search/detail compatibility and ISBN equivalence. Live edition mismatch was not deliberately induced; rejection of unrelated editions, credential failures, quota/rate-limit errors, and network failures were tested with deterministic fixtures. No invalid credentials were sent to either live service.

### Recommendations and automated verification

- Hardcover: retain available for manual enabling, disabled by default. The query repair passed bounded live validation. Coverage, scoped-PAT enforcement, future schema changes, and distributed-app authentication still need attention; assess OAuth separately before wider promotion.
- BigBook: retain available for manual enabling, disabled by default. Authentication and one complete ISBN lookup worked, but coverage was sparse in the representative sample and each successful search may require additional quota for details.
- `.venv\Scripts\python.exe -m pytest tests/test_hardcover.py tests/test_bigbook.py tests/test_metadata.py tests/test_provider_settings.py -q`: **80 passed** before the additional regression cases.
- `.venv\Scripts\python.exe -m pytest tests/test_hardcover.py tests/test_bigbook.py tests/test_metadata.py tests/test_provider_settings.py tests/test_provider_diagnostic.py tests/test_intake_ui.py -q -rs`: **167 passed, 17 skipped, 0 failed**. Skips cite incomplete Tcl/Tk files or unavailable display initialization. Automated checks cover both ISBN forms, verified/mismatched editions, explicit author roles, optional fields, malformed responses, HTTP 401/402/403/429/500/503, GraphQL errors over HTTP 200, credential redaction, network/timeout failures, a shrinking five-second detail budget, chain fallback/precedence, diagnostics, manual-value preservation, and default-disabled settings.
- First `.venv\Scripts\python.exe -m pytest -q -rs`: **598 passed, 19 skipped, 1 failed** in 60.96 seconds. The failure was `tests/test_mobile_connection.py::test_pairing_consumes_expiring_credential_and_authenticates_device`: HTTP 200 was received but the immediate `connected` assertion was false. That test passed on an isolated rerun (**1 passed** in 0.51 seconds). The unchanged connection handler writes the response before recording connection confirmation, which permits a timing race with that assertion. This is an explanation supported by the ordering, not a completed mobile fix. The skips cite Tcl/Tk initialization or missing files. The prior minimum-window geometry failure did not recur.
- Confirmation `.venv\Scripts\python.exe -m pytest -q -rs`: **597 passed, 19 skipped, 2 failed** in 57.86 seconds. The minimum-window geometry check recurred (`798 > 798` was false), and `tests/test_mobile_connection.py::test_connection_confirmation_expires_recovers_and_is_cleared_by_unpair` failed an immediate `connected` assertion after HTTP 200. Neither the form geometry nor mobile connection implementation/tests were changed. Provider regressions remained passing; the full suite is not green. These failures remain unresolved and were not suppressed or repaired as part of the provider changes.
- `.venv\Scripts\python.exe -m compileall -q src tests` and `git diff --check`: **passed**. Git emitted configured LF-to-CRLF notices only.

Native Windows acceptance of Settings and diagnostics was not performed. Mocked success and error fixtures do not establish live service availability beyond the requests recorded above.

## Android release-readiness audit - November 17, 2026

Baseline: clean `main` at `b50d2cfb900f593779d693dc11accd7b4d88afaa`, matching `origin/main`. The audit report is `docs/ANDROID_RELEASE_READINESS_AUDIT.md`; this entry records new runs without replacing earlier results.

- `flutter test --reporter expanded`: **126 passed, 0 failed, 0 skipped** across 12 test files. The suite covers ISBN validation and scanning callbacks, manual/no-ISBN capture, photo correction and Retake, Queue insertion and capacity, early completion, mocked transfer/reconnection/retry, camera controls, Settings, Clear Data, and layout.
- `flutter analyze`: **no issues**.
- `dart format --output=none --set-exit-if-changed lib test`: **35 files checked, 0 changed**.
- `flutter build apk --debug`: **succeeded**. Gradle reported a JDK restricted-native-access warning; dependency resolution reported 19 newer package versions incompatible with current constraints. No packages were upgraded.
- `.venv\Scripts\python.exe -m pytest -q`: **516 passed, 19 skipped, 0 failed**. The skips concern Tk/display-dependent tests in this environment; they are not Android test skips.
- `git diff --check`: **passed** on the final documentation diff; Git reported only its configured LF-to-CRLF notice for `THIRD_PARTY_NOTICES.md`.

On a Xiaomi/Poco 23122PCD1G running Android 16 (API 36), the built debug APK was installed as a fresh install after the phone accepted its install prompt; no app data was cleared. Cold first launch (6.29 seconds), warm resume (0.27 seconds), and cold launch after force-stop with Camera permission granted (5.93 seconds) reached a responsive home screen. A second background/foreground resume while the photo camera was active returned to a working preview with Torch off. Bounded logcat searches and visible observation found no BookLedger ANR; the earlier ANR cause remains unknown.

Disposable physical checks passed for initial Scan/Manual/No ISBN choices, No ISBN photo capture without Save, disabled Send while unpaired, photo-preserving Cancel Change and Manual correction, canceled Retake, successful Retake replacement (old app-private photo removed), camera Guide/Zoom persistence across force-stop, and Torch reset after backgrounding. Bulk capacity 5: Queue reached 1/5 and opened the scanner, scanner X retained the queued entry, a hold outside the scanner made Send appear without sending, and a separate five-photo batch progressed to 5/5 with no sixth scanner. Test captures were removed through normal app navigation and app-private cache inspection; the debug APK remains installed. A real barcode scan, capacity 20 physical run, authenticated reconnect, transfer and desktop acknowledgment, production-signed upgrade, and fresh release build were **not performed** in this audit.

## Android Issue #16 - November 17, 2026

Revised intake uses identifier selection, photography, then explicit Send/Queue without Save. Tests cover immediate readiness, correction/Retake preservation, stale camera-session rejection, next-scan progression, capacity/early finish, reconnect and failed-transfer retry, small-screen layout, camera controls and Settings.

Physical Android 16 checks: debug APK installed; initial 2x2 layout inspected; No ISBN opened the camera; test photograph captured; manual ISBN correction retained it; canceled Retake restored it; Bulk Queue advanced to the next scanner (1/5); scanner cancellation retained the queue; hold Queue produced Send for the partial batch. No inventory was transferred. Initial launches displayed Android input-focus ANR dialogs; after dismissal and granting Camera permission the intake screens responded. The startup warning has not been isolated. Full-capacity progression, real barcode detection, permission denial, saved-preference restart, and authenticated reconnect/transfer remain unverified on hardware. The debug APK remains installed for further testing.

Automated results: `flutter test` - 124 passed, 0 failed, 0 skipped. `flutter analyze` - no issues. `dart format --output=none --set-exit-if-changed lib test` - 35 files, 0 changed. `flutter build apk --debug` succeeded; Gradle warned about restricted `System.load` native access, and dependency resolution reported 19 newer incompatible versions (no dependency changes made). `git diff --check` passed. No desktop code changed; desktop tests were not rerun. Camera-failure recovery and readable identifier-choice controls were included in the final APK rebuild; the final APK was installed without uninstalling or clearing app data.

# Test report history

Record started: 2026-10-19; latest dated entry: 2026-11-20.

This is a record of specific test runs, investigations, and reported physical tests, not a current comprehensive validation certificate. Results and limitations apply to the dates and environments recorded in each section. The 2026-11-15 Milestone 5 source-level run did not establish clean-machine Windows compatibility or physical Android end-to-end transfer/cataloging; a separate reported final-asset session on 2026-11-16 is recorded below.

## Optional bibliographic Subtitle support (2026-11-17)

Schema v12 adds nullable `book_records.subtitle`; the sequential v11 migration does not rewrite existing titles or copy/sales rows. Add/Edit accepts and clears Subtitle independently. Catalog search includes Subtitle, Catalog displays `Title: Subtitle` only below 60 characters and otherwise displays main Title, Inventory always combines them, and Book Details separates them. ISBN providers retain their existing full-title/empty-field behavior, posters continue to use main Title, and Android code is unchanged. No-ISBN duplicate detection remains exact main Title plus Author, so legacy rows with subtitle text embedded in Title may not automatically match a newly separated pair.

Migration, persistence, title formatting/threshold, search, Inventory and Details display, provider handling, poster binding, mobile-originated intake, and backup/restore tests were added or updated. Disposable databases and backup archives were used; no actual library records were modified.

- `.venv\Scripts\python.exe -m pytest tests\test_catalog.py tests\test_catalog_card_text.py tests\test_app_callbacks.py tests\test_intake_ui.py tests\test_posters.py tests\test_uuid_backup_restore.py tests\test_mobile_incoming.py -q -rs --basetemp=.pytest-tmp-issue15-focused-recheck` — **208 passed, 2 skipped**. Skips were Tcl/Tk-dependent geometry tests.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-issue15-final-suite` — **516 passed, 18 skipped, 1 failed**. The single failure was `test_connection_confirmation_expires_recovers_and_is_cleared_by_unpair`, which observed `connected == False` after its authenticated request; the same test passed when rerun alone (**1 passed**). A second full-suite run reproduced that one timing-sensitive failure. The Issue #15 focused tests passed.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed. `git diff --check` — passed; Git emitted only configured LF-to-CRLF notices.

Tk tests that skipped could not load local Tcl/Tk files. The failed mobile-connection test does not exercise changed Issue #15 modules; it remains an unresolved full-suite warning rather than being represented as a pass.

The first combined focused run also exposed two form-window size assertions that depended on Tk applying a resize before measurement. They passed when rerun alone; the form test now processes the requested geometry update before asserting, and the final focused run passed.

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

## Initial final-asset physical smoke session (reported, 2026-11-16)

This physical session was reported using the exact final Windows ZIP and Android APK after the assets had been verified. The tests were not independently observed. No errors were reported. The Windows device was described as a Windows 11 laptop; device model, Windows build, Android model/OS, and whether Android installation was fresh or an upgrade were not supplied.

| # | Result | Reported scenario |
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
| 14 | SKIPPED | Backup and persistence after restart. This was deliberately omitted from the final session; prior testing was reported. |
| 15 | SKIPPED | Automatic reconnection after restart. This was deliberately omitted from the final session; prior testing was reported. |

**Session total: 13 PASS, 2 SKIPPED, 0 FAIL.** These two scenarios were deliberately omitted from this session and are retained as SKIPPED in its historical record. Earlier testing of both scenarios was reported. No device-specific details or install-versus-upgrade distinction have been inferred for this session.

## Follow-up of previously skipped scenarios (reported, 2026-11-16)

Both scenarios that were skipped in the session above were subsequently reported as rerun:

| Scenario | Result | Reported outcome |
| --- | --- | --- |
| Windows backup and persistence after restart | PASS | The previously skipped physical smoke scenario passed in the follow-up round. |
| Android/desktop automatic reconnection after restart | PASS | The previously skipped physical smoke scenario passed in the follow-up round. |

The latest aggregate across the 15 scenarios was reported as **15 PASS, 0 FAIL, 0 SKIPPED**. This cumulative status combines the original session's 13 reported passes with these two subsequently reported passes; it does not change the original session's 13 PASS / 2 SKIPPED record. Neither physical test round was independently observed for this report. The follow-up clarification does not specify whether these two reruns used the exact final release assets, and supplies no additional device or OS details.

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

The `9780553290998` direct-fallback test uses synthetic HTML with a supplied ISBN, title, and author; its synopsis text is explicitly synthetic and no live response was captured. The test simulates the search HTTP error followed by the direct ISBN request resolving to the reported canonical URL. Previously reported browser observations remain the only live evidence for this listing; no live request for it was made in this environment. A live recheck of both the search and canonical URLs for `9780716736387` failed at DNS resolution (`[Errno 11001] getaddrinfo failed`), so the response code, redirect path, and error-body content remain unverified.

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

The extraction change is **not yet verified against Booktopia's actual live tab-to-panel markup**. The synthetic fixtures prove the relationship-based parser and rejection policy only. Do not treat them as captured evidence or claim that live synopsis extraction is confirmed. A sanitized current response or inspected relationship from a browser is still needed to verify the actual selector and availability signal. If the page structure does not expose a relation supported by the parser, Book Details will remain empty rather than use generic text.

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
- `.venv\Scripts\python.exe -m pytest -q -rs` — **497 passed, 19 skipped, 1 failed**. The failure is `test_photo_preview_and_manual_metadata_values_are_preserved`, where the Tk photo preview did not resize after a window geometry change; the same assertion reproduced in isolation and was observed during earlier preview testing. Skips require missing Tcl/Tk files, including `init.tcl`, `ttk/utils.tcl`, and `ttk/sizegrip.tcl`.
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

## v1.1.0-rc1 candidate preparation (2026-11-17)

Exact artifacts and evidence are recorded in `docs/RELEASE_CANDIDATE_v1.1.0-rc1.md` and `dist/v1.1.0-rc1/evidence/`.

- `.venv\Scripts\python.exe -m pytest tests\test_release_version.py tests\test_portable_packaging.py -q` — **6 passed**.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-rc1-full` — **516 passed, 18 skipped, 1 failed**. `test_photo_preview_and_manual_metadata_values_are_preserved` failed because the preview height did not grow after geometry resize. An isolated rerun also failed at that assertion. No source or assertion was changed. Skips require missing Tcl/Tk display files.
- `.venv\Scripts\python.exe -m pytest tests\test_uuid_backup_restore.py tests\test_catalog.py -q -rs --basetemp=.pytest-tmp-rc1-migration-backup` — **83 passed** on disposable test data.
- `flutter test --reporter expanded` — **126 passed, 0 failed, 0 skipped**.
- `flutter analyze` — **no issues**.
- `dart format --output=none --set-exit-if-changed lib test` — **35 files, 0 changed**.
- `git diff --check` — passed; configured LF-to-CRLF notices only.
- Production-signed APK built and verified against the historical production certificate. Release notices and resolved Android license graph were inspected; see `THIRD_PARTY_NOTICES.md` and the candidate evidence inventory.
- One-file and fallback ZIPs passed integrity and composition checks. Their embedded APK hashes match the standalone APK. Both were launched from disposable extractions for 12 seconds and closed; no physical acceptance device was used.

Candidate assessment remains **BLOCKED for release approval** because of pending physical transfer and upgrade checks, and known session-only Android capture state. No candidate APK was installed.

## Photo-preview resize test diagnosis (2026-11-18)

`test_photo_preview_and_manual_metadata_values_are_preserved` had asserted that a portrait thumbnail's pixel height must grow when the form height increases at fixed width. This expectation was incorrect: `Image.thumbnail` preserves aspect ratio and fits within both preview bounds, so the unchanged preview width can remain the limiting dimension. The Tk `<Configure>` binding and `_fit_photo_preview` behavior are unchanged. The test now checks the resulting image remains within the actual preview bounds and retains its source aspect ratio, including after requested form resizes. No timer or arbitrary wait was added.

- Focused preview test, five consecutive runs: **5 passed**.
- Related `test_intake_ui.py` and `test_app_callbacks.py`: **92 passed, 1 skipped** on one run. A later run had **92 passed, 1 failed** in the separate minimum-size GUI test (`body_height == viewport_height == 769`); the preview test passed.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-57a-full`: **516 passed, 18 skipped, 1 failed** in `test_pairing_consumes_expiring_credential_and_authenticates_device`. That mobile-connection test passed in three consecutive isolated reruns.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-57a-full-rerun`: **514 passed, 19 skipped, 2 failed** in the separate minimum-size geometry assertion and the preview test's assumption that the window-manager resize request necessarily increases the mapped preview. The preview geometry request may be constrained in the integrated test display.
- Final full suite after the assertion correction: **517 passed, 17 skipped, 1 failed**. The sole failure was again the separate minimum-size geometry test, with body and viewport both measured at 769 px. The target preview test passed.

Classification: the original pixel-height assertion was a **test defect**; the additional whole-suite resize variability is **window/display geometry sensitivity**. Automated runs do not establish physical Windows visual acceptance. No production code changed; candidate artifacts were not rebuilt or altered.

## Reported physical acceptance (recorded November 18, 2026)

The November 18 physical-test report records PASS using accepted v1.1.0-rc1 for Windows portable execution; APK export; Pairing, Forget Pairing, Unpair and reconnection; multiple-instance blocking; Purge with default Clam preserved; all backup/restore features; Android camera controls; Sales, voids, reports and status transitions; updated desktop layout; poster creation; Single Entry including edge cases; and Bulk Entry including partial and full queues. These results are reported, not independently observed. Device/build details and separate fallback physical testing were not supplied.

Production upgrade PASS was reported after first installing the historical production-signed v1.0.0 APK, then installing the exact rc1 APK over it. Android presented an update confirmation and installation succeeded. Post-upgrade settings and pairing persistence were not separately reported as verified.

The remaining display-sensitive minimum-size geometry assertion was accepted as a non-blocking release exception based on reported physical layout testing. The automated suite remains 517 passed, 17 skipped, 1 failed; it is not fully passing. The original preview failure was a corrected test defect; production preview code was unchanged. The transient mobile-connection failure passed three isolated reruns. Session-only pending captures and the prior unreproduced startup ANR remain disclosed limitations.

## Publication and independent verification (November 18, 2026)

BookLedger v1.1.0 is published at https://github.com/hectordoesgorug/BookLedger/releases/tag/v1.1.0 as a stable release (not draft/prerelease). Annotated tag object `794954ae76d052bfbeae196a9396a26e60afeca3` peels to reviewed commit `01dc3990e9fa321e5cf2f815ce509d5a3736e9ac`. The reviewed source was committed and pushed before tag creation and publication.

All four public assets were downloaded independently and SHA-256 verified against final staging and the published manifest. Sizes: Portable 60,133,742 bytes; Fallback 60,982,251 bytes; APK 71,633,402 bytes; SHA256SUMS.txt 317 bytes. Candidate binaries were not rebuilt or modified. Historical v1.0.0 release metadata and its asset records exactly match the pre-publication snapshot. Evidence and downloaded bytes are retained under ignored `build/release58-verification/`.

The accepted automated exception remains 517 passed, 17 skipped, 1 failed (display-sensitive minimum-size assertion); physical acceptance remains documented as reported testing. Session-only pending captures, the prior unreproduced ANR, and unverified post-upgrade settings/pairing persistence remain disclosed. No fresh automated or physical test run is implied by publication verification.

### Historical ANR context clarified (November 18, 2026)

The earlier ANR report concerned a Poco X6 experiencing lag while rapid charging and connected to a PC through TwinDesk. No ANR was reproduced during the subsequent audit, and no root cause has been established. These circumstances are context, not a confirmed explanation or an active verified defect. Historical observations and test results above remain unchanged.

## Configurable currency and SRP investigation (2026-11-20)

- `.venv\Scripts\python.exe -m pytest tests/test_currency.py tests/test_posters.py tests/test_app_callbacks.py -q -rs` — **97 passed, 1 skipped**. The skip requires complete Tcl/Tk libraries that are missing from this Python installation.
- `.venv\Scripts\python.exe -m pytest -q -rs` — **534 passed, 18 skipped**. All skips are Tk UI/display checks unavailable with the installed incomplete Tcl/Tk runtime; no tests failed.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed.
- Read-only Frankfurter v2 smoke requests for PHP/USD and USD/PHP on November 20 returned the documented pair/rate/date shape with observation date 2026-11-20. The supported-code list was checked against `/v2/currencies`. These checks establish response compatibility at that time, not continuing service availability.

Automated rate tests use mocked responses. A single database conversion containing 100 copies, 120 sale-history rows (including voided sales), and 2 SRPs made **one** rate request. Tests cover two-decimal formatting across all 20 codes, decimal half-up rounding, zero and overflow rejection, empty-library changes, Yes/No/Cancel routing, explicit differing source/destination, rate reuse and stale rejection, offline, timeout and malformed responses, transaction rollback, config-write interruption/reconciliation, schema v12 migration without numeric changes, backup/restore of currency/cache/audit state, and purge to PHP. Existing reporting and poster tests pass in the full run.

Live Google Books ISBN checks were rate limited (HTTP 429). The three read-only Booktopia product snapshots matched paperbacks but only one displayed supplier RRP; no documented extraction permission or API was found. Open Library, Archive.org, Big Book API, and Hardcover did not document a usable publisher retail-price field. Automated SRP remains empty; manual SRP remains informational. Physical edition coverage, retailer extraction permission, native Settings rendering, and broader desktop visual behavior were not verified. Refer to the currency source review in `docs/ARCHITECTURE.md` for the source-by-source findings and primary references.
