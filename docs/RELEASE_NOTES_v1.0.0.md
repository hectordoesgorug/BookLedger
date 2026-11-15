# BookLedger v1.0.0 — Initial Public Release

BookLedger is a portable Windows book-inventory application with an Android companion for scanning and photo capture.

## Features

- Catalog books and separate physical copies with stable copy records.
- Look up bibliographic metadata online using an ISBN.
- Store book and copy photographs, condition, location, status, and price.
- Track listings and completed sales for individual copies.
- Keep the desktop database and photos in portable local storage and create user-controlled backups.
- Scan ISBN barcodes and capture book photographs in the Android companion.
- Pair the Android companion with BookLedger Desktop and transfer captures for desktop cataloging.

## Downloads

- Windows 11 x64 portable package: `BookLedger-v1.0.0-Windows-x64-Portable.zip`
- Android companion APK: `BookLedger-v1.0.0-Android.apk`

## Installation

For Windows, download and extract the entire ZIP, then run `BookLedger/BookLedger.exe`. Keep the package's `licenses/`, `mobile/`, `zeroconf/`, and `docs/` folders alongside the executable. The first launch creates the configuration and writable data folders.

For Android, install the APK through Android's standard sideloading flow. The companion supports Single Entry and Bulk Entry for scanning ISBNs and capturing photos; it relies on BookLedger Desktop to catalog and manage inventory. Pair over a trusted local network. Pairing and transfers use unencrypted local HTTP.

BookLedger stores its desktop database and photos locally. Backups are user-controlled and are not encrypted by BookLedger. Online ISBN lookup sends the ISBN and any required provider credentials to the selected provider over HTTPS. See the [Privacy Notice](PRIVACY_NOTICE.md) and [Third-Party Notices](../THIRD_PARTY_NOTICES.md) for details.

The Android companion's behavior may depend on the device and Android environment; this release does not claim universal Android compatibility.
