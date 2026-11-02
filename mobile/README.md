# BookLedger Mobile

Flutter companion application for capturing book ISBNs and front-cover photographs for future transfer to BookLedger desktop.

Single Entry includes camera-based ISBN scanning and front-cover capture. ISBNs must pass ISBN-10 or ISBN-13 check-digit validation. Photos remain in app-private temporary storage for the active capture session.

Bulk Entry supports a session-only queue of independently identified ISBN/photo captures, with a configurable capacity of 5 to 20 books. Photos are removed when the capture session ends. A batch can be finished early by holding Queue, and Send marks a batch ready locally. Desktop pairing and transfer are not implemented; the desktop application remains the source of truth.

## Development

From this directory:

- `flutter analyze`
- `flutter test`
- `dart format --output=none --set-exit-if-changed lib test`
- `flutter build apk --debug`
