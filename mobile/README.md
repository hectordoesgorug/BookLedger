# BookLedger Mobile

Flutter companion application for capturing book ISBNs and front-cover photographs for future transfer to BookLedger desktop.

Single Entry now includes camera-based ISBN scanning and front-cover capture. ISBNs must pass ISBN-10 or ISBN-13 check-digit validation. Photos remain in app-private temporary storage for the active capture session. Desktop pairing and transfer are not implemented; the desktop application remains the source of truth.

Bulk Entry currently provides only the Milestone 1 queue-size selection and presentation interface.

## Development

From this directory:

- `flutter analyze`
- `flutter test`
- `dart format --output=none --set-exit-if-changed lib test`
- `flutter build apk --debug`
