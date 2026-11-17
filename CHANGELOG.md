# Changelog

## 1.1.0 — Unreleased

Internal candidate: **v1.1.0-rc1**, prepared from `8b4b904d83627c4b11ae749dd83d32bc8b46d8bc` plus the uncommitted Handover #57 preparation changes. This is not a published release.

### Desktop

- Prevent concurrent desktop access to the same portable library; separate library folders remain independent.
- Add ascending/descending catalog sorting and normalize card heights to reduce clipped text.
- Add optional bibliographic subtitles, subtitle search, and consistent Inventory/Details display. Catalog combines title and subtitle below its existing length threshold; posters retain the main title.
- Improve mobile connection-status reporting.
- Reduce catalog image-processing work while preserving image sampling and Sold styling; no thumbnail cache or background loading was added.

### Android

- Remove the obsolete secure-storage diagnostic control (#6).
- Consolidate Settings, including pairing and theme controls, and refine the home footer (#5).
- Add camera torch, supported zoom steps, framing guides, and persisted zoom/guide preferences (#8).
- Add reconnection regression coverage for capture and transfer workflows (#19).
- Streamline Single/Bulk Entry: Scan/Manual/No ISBN choices, immediate photo readiness, photo-preserving Change/Retake, automatic next-book scanning, and partial-batch completion (#16).

### Compatibility and limitations

- Desktop schema advances from v11 to v12 by adding nullable `book_records.subtitle`. Existing titles and copy/sales identities remain unchanged. Existing v1.0.0 backups are supported by the restore/migration path. Back up before upgrade; preserve `data/`, `config.json`, and `backups/`. Downgrading a migrated library is not supported; use a pre-upgrade backup with the old application.
- Android remains `com.bookledger.mobile`, now `1.1.0+2`, with the existing production signing identity. In-place upgrade and settings/pairing preservation require owner verification on this exact candidate.
- Pending mobile captures remain session-only: process termination can lose the queue even when temporary photos remain. Keep the app open through acknowledgment; durable mobile recovery is deferred by decision.
- Local transfer remains token-authenticated, unencrypted HTTP on a trusted network. No transport change was made.
- An earlier Android startup ANR remains unexplained; it was not reproduced in the November 17 debug audit. Signed-candidate startup and live transfer acceptance remain pending.
- Automated Tk/display skips and physical-device limits remain explicit in the candidate report. Mocked transfer tests do not establish hardware integration.
- Other backlog work, including library merging, background removal, bulk desktop metadata download, and general desktop resizing, is not included.

See [draft release notes](docs/RELEASE_NOTES_v1.1.0.md) and [candidate checklist](docs/RELEASE_CHECKLIST_v1.1.0.md).

## 1.0.0 — 2026-11-16

Initial public Windows portable and Android companion release: bibliographic/copy inventory, ISBN lookup, photos, sales, backups/restoration, and local authenticated mobile capture transfer. Historical tag `v1.0.0` points to `1224f3ec25b8a3715f3b6b4234ed2bf9f180bc5c`.

See the unchanged [historical release notes](docs/RELEASE_NOTES_v1.0.0.md) and [release checklist](docs/RELEASE_CHECKLIST_v1.0.0.md).
