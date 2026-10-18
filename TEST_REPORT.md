# Test report

Date: 2026-10-18

## Latest synopsis-policy changes

- `.venv\Scripts\python.exe -m pytest tests/test_booktopia.py tests/test_metadata.py -q --basetemp=.pytest-tmp-synopsis-policy-focused-final3` — **64 passed**.
- `.venv\Scripts\python.exe -m pytest tests/test_intake_ui.py -q -rs --basetemp=.pytest-tmp-synopsis-policy-intake-final2` — **18 passed, no skips**.
- `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.pytest-tmp-synopsis-policy-full-final2` — **155 passed, no skips** in 19.27s.
- `.venv\Scripts\python.exe -m compileall -q src tests` — passed.
- `git diff --check` — passed; Git emitted only configured LF-to-CRLF notices.

## Coverage and behavior

Open Library tests confirm title, author, publisher, publication year, and page count remain available while edition descriptions, notes, excerpts, and linked-work descriptions never populate Book Details/Synopsis. The linked-work API request is no longer made solely to retrieve a synopsis. ISBN `9780716736387` has a deterministic regression for the observed bibliographic notes.

Booktopia tests use mocked responses and synthetic HTML fixtures, not captured site responses. They verify explicit tab-to-panel relationships, rejection of a tab ID without a relationship, panel text taking precedence over structured bibliographic notes, filtering author/review/recommendation sections, rejection of generic meta descriptions and purchase copy in matching Book JSON-LD, safe empty synopsis results, ISBN aliases, matching-product checks, unavailable-product status, and HTTP/network error distinctions. Reference ISBN cases are represented by synthetic fixtures: `9780140449136` for a linked synopsis panel against an Open Library note, `9781923058507` for generic purchase copy plus a linked synthetic synopsis, and `9780716736387` for Open Library notes and a matching but unavailable synthetic Booktopia page. These fixtures demonstrate parser policy, not current live markup.

The previous Booktopia parser collected unqualified body `itemprop="description"`, schema.org descriptions, and generic `description`/Open Graph metadata, without identifying a Description tab's associated panel. That allowed bibliographic notes and retail SEO text to be treated as Book Details. The revised parser only trusts a panel when the identified tab explicitly references it, or a matching schema.org Book description after filtering recognized note and retail boilerplate patterns. Unassociated `itemprop="description"` and generic meta descriptions are ignored. If no usable synopsis exists, it leaves the field empty. A matching page marked with an explicit unavailability message or structured `OutOfStock`, `Discontinued`, or `SoldOut` state reports `Product unavailable`; HTTP errors remain provider failures.

## Live investigation limits

No raw current Booktopia HTML or sanitized live capture was available in the development environment. The web-rendered indexed text snapshot for [Crime and Punishment, ISBN 9780140449136](https://www.booktopia.com.au/crime-and-punishment-fyodor-dostoyevsky/book/9780140449136.html) (crawled 1.1 years ago) and [The Strength of the Few, ISBN 9781923058507](https://www.booktopia.com.au/the-strength-of-the-few-james-islington/book/9781923058507.html) (crawled two weeks ago) shows substantial text beneath a Description label, but the transformed snapshots do not expose HTML attributes or response timing. They cannot establish whether the text is in the initial HTTP response, a hidden panel, embedded structured data, or a later browser request. The current page for [The Triumph of Evolution, ISBN 9780716736387](https://www.booktopia.com.au/the-triumph-of-evolution-niles-eldredge/book/9780716736387.html) could not be read through the available web view; the unavailable state in tests is therefore based on a clearly labeled synthetic fixture and the user's observation.

The extraction change is **not yet verified against Booktopia's actual live tab-to-panel markup**. The synthetic fixtures prove the relationship-based parser and rejection policy only. Do not treat them as captured evidence or claim that live synopsis extraction is confirmed. A sanitized current response or inspected relationship from the user's browser is still needed to verify the actual selector and availability signal. If the page structure does not expose a relation supported by the parser, Book Details will remain empty rather than use generic text.

The integration remains best-effort and subject to site changes and access policies. No schema or runtime dependency changes were made. The rest of the suite covers catalog validation, sales and status transitions, backup/restore, portable paths and migration, Trash and photo lifecycle, recovery, verification, callbacks, and intake UI behavior. Manual native-Windows GUI acceptance remains pending.
