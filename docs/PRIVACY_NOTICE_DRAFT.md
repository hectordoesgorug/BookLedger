# BookLedger Privacy Notice — Draft for Owner Review

**Draft status:** This text is based on a source review dated 2026-11-15. It is not approved for publication. The project owner must complete the decisions at the end before using it as a user-facing notice.

## Information BookLedger stores

BookLedger stores the book inventory, settings, database, and photographs on the user's Windows computer. The portable defaults place these beside the application in `config.json` and `data/`; if the application folder is not writable, configuration may use the Windows user profile instead. Android stores captured photographs in app-private temporary storage while a transfer is pending. After transfer, the desktop keeps incoming capture details and photographs in its `data/incoming/` storage and database until the user catalogs or discards each capture. A process interruption can leave a phone-side temporary capture until app or Android cleanup.

## Information sent over the network

- When a user starts an online metadata lookup, BookLedger sends the ISBN and any credential needed for that request to the selected provider over HTTPS. Current providers are Open Library, Google Books, Archive.org, Booktopia, Bigbook, and Hardcover. Provider privacy and retention practices are controlled by those providers.
- Pairing sends the phone's device name to the desktop on the local network. The phone stores its device token and paired desktop addresses using Android secure storage; the Windows desktop stores the paired name and a Windows DPAPI-protected token in its local configuration. Pairing and capture transfer use unencrypted local-network HTTP, authenticated by the token. A transfer includes the ISBN, capture identifier, order/sequence, timestamp, and JPEG photograph. Pair only on a trusted network.
- Barcode image input and scan results are processed on-device by the bundled ML Kit model. Google documents that ML Kit may contact Google for model updates, fixes, or hardware compatibility and may send usage and performance metrics. BookLedger source review found no app-owned analytics or telemetry; network traffic was not independently captured for this draft. See [ML Kit Terms](https://developers.google.com/ml-kit/terms).

This source review found no BookLedger-operated cloud service receiving the inventory. Users can initiate separate provider requests, local-network pairing/transfers, and system photo sharing.

## Backups, exports, and deletion

Backups and exports are user-controlled. A backup archive can include the database, photographs, and configuration; it is not encrypted and may contain provider settings or credentials. The user chooses where to save, copy, share, or delete backups and exported files. Android photo sharing uses the user-initiated system share sheet. Exporting the Android APK copies the bundled application file and does not upload book data.

Local inventory and photographs remain until the user removes them or deletes the relevant files. Incoming mobile captures remain until cataloged or discarded. This draft does not promise a fixed retention period for temporary files, operating-system data, provider records, or user-created backups.

## Owner decisions required before publication

1. Add the responsible publisher/data-controller name and a working privacy contact address or URL.
2. Identify the intended release jurisdictions and obtain review of which privacy rules apply.
3. Approve the provider list and add current provider privacy-policy links, including any provider-specific credential handling.
4. Confirm whether the described local retention and temporary-file behavior is sufficient, and set any retention/deletion commitments the owner intends to make.
5. Confirm the wording about backups, credentials, and possible Google ML Kit communications against the exact release build and any available network testing.

Until these decisions are made, this draft is not a final legal notice or a claim of jurisdiction-specific compliance.
