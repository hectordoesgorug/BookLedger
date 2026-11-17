# BookLedger Privacy Notice

**Developer:** `hectordoesgorug` ([GitHub profile](https://github.com/hectordoesgorug))

**Project:** [BookLedger on GitHub](https://github.com/hectordoesgorug/BookLedger)

BookLedger stores your book inventory, settings, database, and photos on your Windows computer. In the portable version these files are kept beside the application; configuration may use your Windows profile if that folder is not writable. The Android app keeps captured photos in temporary app storage while a transfer is pending. Pending capture and queue metadata are session-only: process termination can lose the queue even if temporary photographs remain. Keep the app open until the desktop acknowledges receipt. The desktop stages received captures in its local data folder and database until you catalog or discard them. Temporary-file cleanup can depend on app and operating-system behavior.

BookLedger does not send your inventory to a BookLedger-operated cloud service. Some user-triggered actions do use networks:

- An online ISBN lookup sends the ISBN and any required provider credentials to the selected metadata provider over HTTPS. Each provider controls its own handling and retention.
- Pairing sends the phone's device name to the desktop. Pairing and photo transfer use token-authenticated, unencrypted HTTP on your local network. A transfer includes the ISBN, capture ID, sequence, timestamp, and photo. Use a trusted network. Pairing tokens are stored locally using Android secure storage and Windows DPAPI protection.
- Barcode scanning runs on-device using Google ML Kit. Its SDK may contact Google for model updates, fixes, or device compatibility and may send usage or performance metrics. This is based on source and vendor documentation; BookLedger has not independently captured all SDK network traffic.

Backups are user-controlled and are not encrypted by BookLedger; they can contain your database, photos, settings, or provider credentials. You choose where to save, share, or delete them. Android photo sharing uses the system share sheet. Exporting the companion APK copies the bundled installer and does not upload your book data.

Local records remain until you delete them. Incoming mobile captures remain until cataloged or discarded. This notice does not set retention periods for operating-system temporary files, external metadata providers, or backups you create.

## Contact and scope

For questions, use the [BookLedger GitHub Issues page](https://github.com/hectordoesgorug/BookLedger/issues). GitHub Issues are public: do not post private information, credentials, photos, or sensitive book data there. The developer's legal name and location have not been provided. Privacy laws and required contact details vary by jurisdiction; where a named controller or confidential contact channel is required, this public GitHub route may not be sufficient. No jurisdiction-specific legal assessment is made by this notice.
