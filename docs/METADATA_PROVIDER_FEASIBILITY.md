# Metadata provider feasibility

Verified November 20, 2026 for BookLedger's independent portable desktop catalog. [Issue #2](https://github.com/hectordoesgorug/BookLedger/issues/2) remains open pending review and agreed dispositions for ISBNdb, Goodreads and WorldCat. No candidate adapters, GUI controls, subscriptions, credentials or production records were created or changed.

## Baseline and recommendations

Fresh settings use Open Library → Google Books → Archive.org → Hardcover → Booktopia → Bigbook. Only Bigbook is disabled by default. Explicit saved ordering and enabled states take precedence. Missing Hardcover credentials return an immediate authentication result without a network request; subsequent providers remain available through the existing metadata chain. Settings → API Management remains the credential interface.

Hardcover and Bigbook compatibility repairs are integrated in `5fe714fc36e6fee2c4ddc4301da1b608e98b754c`. The [dated test report](../TEST_REPORT.md#metadata-provider-compatibility--november-20-2026) records bounded live results and distinguishes them from automated fixtures. OAuth for wider Hardcover distribution remains separate from those completed repairs.

| Candidate | Technical feasibility | Access/retention fit | Potential value | Recommendation |
| --- | --- | --- | --- | --- |
| ISBNdb | Documented REST ISBN lookup and broad bibliographic fields | Paid subscription; API-derived catalog and backup data must be removed after expiry | Potential older/local-edition coverage; list price is advertised but not verified publisher SRP | **Defer** until written terms resolve durable retention, exports/backups and price semantics; then consider a separately authorized sample |
| Goodreads | No obtainable supported public developer route established | No new public keys since 2020; website terms do not grant metadata harvesting rights | No authorized incremental ISBN or SRP coverage demonstrated | **Reject** implementation under current access conditions |
| WorldCat/OCLC | Search v2 provides bibliographic resources; Entities is a different service | Institutional subscriptions or negotiated partnership; discovery rights do not establish cataloging/storage rights | Potential academic/older-edition value, unmeasured; no verified SRP source | **Reject** a general independent-user integration; revisit only with an appropriate OCLC agreement |

Existing public/credentialed providers already cover the basic fields and optional descriptions. A candidate must demonstrate additional edition coverage while preserving ISBN verification, fill-missing-only behavior, approved genres, the five-second provider budget, durable local records and portable backups. Catalog size and marketing claims do not establish incremental coverage.

## ISBNdb

### Price, access and credentials

The official [pricing page](https://isbndb.com/isbn-database), read in a normal browser, lists these monthly USD prices before applicable taxes:

| Plan | Monthly price | Daily searches | Advertised throughput | Other limits |
| --- | --- | --- | --- | --- |
| Basic | $14.99 | 5,000 | 1 call/second | 100 bulk results/call; seven-day trial advertised |
| Premium | $35.99 | 15,000 | 3 calls/second | 1,000 bulk results/call |
| Pro | $99.99 | 50,000 | 5 calls/second | 1,000 bulk results/call; real-time merchant pricing |
| Academic/nonprofit | $7.50 | 2,000 | Not separately confirmed | Basic features with 10 bulk results/call; eligibility and noncommercial educational/research restrictions |
| Enterprise | Individually quoted | Negotiated | Negotiated | Requires contact |

Annual billing advertises two months free. Daily limits reset at midnight UTC; no separate monthly allocation was established, and unused calls do not roll forward. A free website account offers single-book browser lookups, **not API access**. The trial converts to a paid subscription unless canceled. No account, trial or subscription was activated.

The [API documentation](https://isbndb.com/isbndb-api-documentation-v2), version 2.9.1 dated November 19, 2026, documents `GET https://api2.isbndb.com/book/{isbn}`, bulk ISBN retrieval, searches and account/quota information. The API key belongs in the `Authorization` header; query-string authentication is unsupported. HTTP 401 covers missing/invalid keys or inactive subscriptions, 404 an absent ISBN, 429 minute/daily quotas and 503 temporary unavailability. Rate-limit headers expose limits and remaining allocation. Missing values can be omitted rather than null.

### Metadata, edition coverage and latency

The [FAQ](https://isbndb.com/faq#what-info-does-your-db-include) and pricing page advertise ISBN-10/13, title, author, publisher, publication date, binding, pages, edition, format, synopsis, language, subjects, list price, covers and physical measurements. Current API release notes add genres and Thema classifications. The FAQ guarantees only title, author, ISBN and ISBN-13; other fields vary by record. The embedded endpoint schema did not render fully during review, so property-level price/currency mapping remains unverified.

ISBNdb advertises more than 123 million records, including local, rare, non-English and out-of-print editions. That is a provider claim, not a measured BookLedger match rate. Potential older/academic value remains unverified. A future authorized test must compare the same public ISBN sample against existing providers, check both returned ISBNs and valid equivalents, distinguish translations/bindings and reject unrelated editions.

No candidate API requests were made because API access requires subscription activation. A single exact-ISBN request could fit the five-second budget in principle, but no response-time guarantee or measured latency was established. Throughput limits do not establish latency. Retries and detail requests would need to share that existing budget.

### Storage and distribution blocker

The [terms dated September 7, 2026](https://isbndb.com/terms-and-conditions) permit subscribers to build their own applications, display individual records and cache data while subscribed. They restrict bulk redistribution, database resale/proxying, systematic extraction and key sharing. Within 30 days after subscription expiry or termination, API-derived data must be removed from products/databases; backup copies must also be removed within that period and cannot be restored. Independently created data and bare ISBN identifiers are treated separately. Content-removal notices introduce another deletion obligation.

These conditions conflict with BookLedger's durable accepted metadata and portable backups. Its merged fields also lack the provenance needed to reliably separate every API-derived value from independently obtained or manually edited values after cancellation. This is an integration blocker under the reviewed terms; no automatic record deletion should be introduced to accommodate it. Obtain written permission covering persistent personal records, edits, backup/restore, exports/posters and distributed installations before integrating. Do not ship a shared key or assume one subscriber's key may be distributed to all users.

### SRP overlap

The [pricing FAQ](https://isbndb.com/faq#does-the-data-include-real-time-book-prices) distinguishes list-price data on all plans from real-time merchant pricing on Pro/Enterprise. This is a potential lead for [Issue #20](https://github.com/hectordoesgorug/BookLedger/issues/20), but neither label establishes current publisher SRP for a physical edition in a verified currency/market. Price date, publisher provenance, edition/binding, currency and coverage need clarification and licensed samples. No automatic SRP mapping is justified.

Recommendation: defer implementation pending written retention/reuse permission and a separately authorized comparison sample. A technically simple API does not resolve the retention conflict.

## Goodreads

The [official developer group](https://www.goodreads.com/group/show/8095-goodreads-developers) states that new public API keys stopped on December 8, 2020 and retirement was planned. The legacy [API URL](https://www.goodreads.com/api) redirected to the homepage and a JavaScript verification notice here; the official [API help page](https://help.goodreads.com/s/article/Does-Goodreads-support-the-use-of-APIs) returned a loading/CSS-error shell. These observations do not prove that every legacy key or private partnership is inoperable. No currently supported, obtainable ISBN metadata integration for BookLedger was established.

Old API-key/OAuth tutorials and legacy XML field lists are historical evidence, not a current integration contract. No legacy key was available or tested, and no authorized private partnership was identified. Current supported fields, price, quotas, latency and incremental ISBN coverage remain unverified rather than assumed free or unlimited.

The [site terms](https://www.goodreads.com/about/terms) grant limited personal/noncommercial use and exclude collection/use of book listings, descriptions and reviews, along with data mining and similar extraction. They do not authorize a persistent BookLedger metadata harvest. No scraping, unofficial proxy, website-internal endpoint or authentication workaround was implemented or tested.

Recommendation: reject an adapter under current access conditions. Existing providers supply the core bibliographic fields without depending on an unavailable public developer enrollment route. No authorized incremental coverage or SRP advantage was demonstrated. Revisit only if Goodreads offers a supported agreement covering ISBN retrieval, local retention and distribution.

## WorldCat / OCLC

### Search API v2 access and bibliographic data

The [Search API eligibility page](https://www.oclc.org/developer/api/oclc-apis/worldcat-search-api.en.html) requires both a full OCLC Cataloging and Metadata subscription and a FirstSearch/WorldCat Discovery subscription. Commercial partnerships are a separate route. Production status and sandbox availability do not make access public. No independent-user price/free API plan was established; institutional/partnership pricing must be confirmed with OCLC.

The [v2 reference](https://developer.api.oclc.org/wcv2) and [public OpenAPI contract](https://developer.api.oclc.org/docs/wcapi/v2/openapi-external-prod.yaml) document OAuth-secured brief/full bibliographic endpoints, ISBNs, titles/creators, dates, edition statements, publication details, subjects, formats and physical descriptions. Access uses provisioned WSKey/application credentials and OAuth tokens. Never embed a shared WSKey secret in a distributed portable binary or borrow institutional credentials for unrelated users.

ISBN searches may return multiple records or related editions. Exact identifier, binding and language checks remain necessary. Brief records should not be assumed to contain a synopsis or numeric page count. A library catalog could improve academic/older-edition coverage, but no authenticated match-rate comparison or latency was measured. Token acquisition and follow-up retrieval would share the five-second lookup budget. No guaranteed response time or current v2 per-key quota was established; the old v1 50,000-request FAQ example must not be applied to v2.

The current [terms hub](https://www.oclc.org/developer/support/terms-and-conditions.en.html) links [Search API terms](https://www.oclc.org/content/dam/developer-network/PDFs/wcapi-terms-and-conditions-20121204.pdf) dated 2012. They limit use to discovery, exclude cataloging, restrict commercial use without another agreement and tie a WSKey to the institution's needs. Their age means the applicable v2/institutional contract needs direct confirmation; the publicly linked terms do not grant independent catalog population, permanent local storage or portable-backup/export redistribution rights.

### Distinct OCLC products

| Service | Purpose and access | Implication |
| --- | --- | --- |
| [WorldCat Search v2](https://www.oclc.org/developer/api/oclc-apis/worldcat-search-api.en.html) | Library discovery, bibliographic retrieval and holdings; qualifying subscriptions/partnership | Relevant data, but eligibility and cataloging/retention rights remain blockers |
| [WorldCat Metadata API](https://www.oclc.org/developer/api/oclc-apis/worldcat-metadata-api.en.html) | Bibliographic and holdings cataloging/management; full Cataloging and Metadata subscription | Relevant cataloging product, not a free unauthenticated substitute |
| [WorldCat Discovery API](https://developer.api.oclc.org/worldcat-discovery) | Discovery/central-index resources for library interfaces | Separate entitlement, fields and data rights; not interchangeable with Search or Metadata |
| [WorldCat Entities Data API](https://www.oclc.org/developer/api/oclc-apis/worldcat-entities-data.en.html) | Linked-data properties by entity URI; limited public tier, additional free-WSKey tier, full Meridian tier | Public entity access is not demonstrated ISBN-to-edition lookup |
| [WorldCat.org website](https://www.oclc.org/content/dam/ext-ref/worldcat-org/terms.html) | Human discovery under website terms | Does not authorize automated catalog creation or permanent metadata harvesting |

The [Entities access matrix](https://help.oclc.org/Metadata_Services/WorldCat_Entities/WorldCat_Entities_data_API/WorldCat_Entities_data) lists some title/author/description and edition properties in the public tier, but puts `isbn` in the Meridian-subscriber tier. A generic entity description is not necessarily a book synopsis, and extent is not guaranteed numeric pages. Limited URI retrieval does not establish BookLedger's required ISBN verification. [Entities terms](https://policies.oclc.org/en/terms/worldcat-entities.html) also impose attribution, noncommercial and storage conditions; local-workflow allowances are not unrestricted redistribution rights.

[WorldCat.org website terms](https://www.oclc.org/content/dam/ext-ref/worldcat-org/terms.html) restrict automated extraction, cataloging/metadata creation and long-term storage. These differ from API licensing, but rule out treating public pages as a shortcut around eligibility. Search v1 support ended December 31, 2024; no v1 integration was evaluated. No reliable publisher SRP field/currency was established across the examined services; bibliographic/acquisition notes must not become automatic current retail-price evidence.

Recommendation: reject a general WorldCat provider under current independent-user conditions. Revisit an institutional/partner variant only with written eligibility, cataloging/retention/export rights, credential architecture, quotas and pricing. No examined public, institution-free service meets the edition-verification and durable-catalog requirements.

## Verification and next decisions

Only official vendor documentation supports these findings. ISBNdb's public overview, pricing, API overview/changelog, FAQ and terms were readable in a browser after web fetches hit robots restrictions/HTTP 403; its embedded endpoint schema did not fully render. OCLC's public OpenAPI file was inspected. Goodreads access limitations are recorded above. Public documentation access is not successful provider API verification.

No ISBNdb, Goodreads or OCLC catalog API calls used credentials or incurred charges. No trial, subscription, paid plan or OAuth application was activated. Candidate API latency, authenticated failures, incremental coverage and physical-edition price quality therefore remain unverified. Existing automated tests establish defaults and fallback behavior, not candidate API compatibility.

Review these three recommendations before assigning final dispositions or closing Issue #2. Any future integration requires separate approval and must reuse existing API Management, keep credentials out of URLs, verify ISBN editions, map supported fields only, respect approved genres and the five-second budget, and keep automatic SRP separately scoped.
