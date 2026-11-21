# Changelog

## 1.2.0 — Release preparation

**Status:** Unpublished. Candidate acceptance is recorded; publication is pending.

### Desktop

- Add configurable currency display and explicit, backed-up conversion for asking prices, retained sales history and SRP values.
- Add deterministic book-description shortening with an original-versus-shortened review step; keep the original description.
- Repair existing metadata providers and enable Hardcover ahead of Booktopia by default. BigBook remains available but disabled by default.
- Refine desktop layout and navigation, and add explicit update checks with verified downloads and package-specific manual Windows update instructions.

### Android

- Add explicit update checks and verified APK downloads. Android's system installer handles any user-approved installation.
- Increase the Android version to `1.2.0+3` while preserving application ID `com.bookledger.mobile`.

### Compatibility and limitations

- Desktop database schema is 14. Back up before upgrading; v1.1.0 cannot open a migrated schema-14 library, so rollback requires restoring a pre-upgrade backup.
- The published v1.1.0 binaries do not include the update flow. Install an updater-capable release manually before using it.
- Windows installation remains manual after download verification. Android installation requires explicit confirmation and the system installer.
- Pending mobile captures remain session-only. Automated publisher SRP sourcing and additional metadata providers are not included.

## 1.1.0 — 2026-11-18

The accepted **v1.1.0-rc1** candidate was published as the stable v1.1.0 GitHub Release. Final assets are byte-identical copies, and all four public downloads were independently verified.

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
- Android remains `com.bookledger.mobile`, now `1.1.0+2`, with the existing production signing identity. A reported test installed the exact rc1 APK over the historical production-signed v1.0.0 installation. Settings/pairing persistence after upgrade was not separately verified.
- Pending mobile captures remain session-only: process termination can lose the queue even when temporary photos remain. Keep the app open through acknowledgment; durable mobile recovery is deferred by decision.
- Local transfer remains token-authenticated, unencrypted HTTP on a trusted network. No transport change was made.
- The earlier ANR report concerned a Poco X6 experiencing lag while rapid charging and connected to a PC through TwinDesk. No ANR was reproduced during the subsequent audit, and no root cause has been established. These circumstances are context, not a confirmed explanation or an active verified defect. Single/Bulk acceptance and reconnection were reported as passing physical tests.
- Automated Tk/display skips and physical-device limits remain explicit in the candidate report. Mocked transfer tests do not establish hardware integration.
- Other backlog work, including library merging, background removal, bulk desktop metadata download, and general desktop resizing, is not included.

See [draft release notes](docs/RELEASE_NOTES_v1.1.0.md) and [candidate checklist](docs/RELEASE_CHECKLIST_v1.1.0.md).

## 1.0.0 — 2026-11-16

Initial public Windows portable and Android companion release: bibliographic/copy inventory, ISBN lookup, photos, sales, backups/restoration, and local authenticated mobile capture transfer. Historical tag `v1.0.0` points to `1224f3ec25b8a3715f3b6b4234ed2bf9f180bc5c`.

See the unchanged [historical release notes](docs/RELEASE_NOTES_v1.0.0.md) and [release checklist](docs/RELEASE_CHECKLIST_v1.0.0.md).
