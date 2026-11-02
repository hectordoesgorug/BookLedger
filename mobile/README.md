 # BookLedger Mobile

Flutter companion application for session-only book capture and local pairing with BookLedger desktop.

Single Entry scans ISBNs and captures front-cover photographs. Bulk Entry queues independently identified ISBN/photo captures in app-private temporary storage, with capacity from 5 to 20. A batch can be finished early by holding Queue. Send marks it ready locally; book/photo transfer is not implemented.

Mobile App Setup pairs to the desktop over the local network using QR or manual IPv4 entry. The device token is stored in Android secure storage. HTTP traffic is unencrypted, so pair only on a trusted network. Reconnection tries the last endpoint, then DNS-SD/mDNS discovery, then saved addresses. QR and manual entry remain available when multicast discovery is unavailable. Windows hotspot discovery has not been physically verified.

## Development

From this directory:

- `flutter analyze`
- `flutter test`
- `dart format --output=none --set-exit-if-changed lib test`
- `flutter build apk --debug`
