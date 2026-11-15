import 'dart:io';

Future<int> clearPendingCapturePhotos(Directory temporaryDirectory) async {
  var deleted = 0;
  await for (final entity in temporaryDirectory.list(followLinks: false)) {
    if (entity is File &&
        entity.uri.pathSegments.last.startsWith('bookledger_capture_') &&
        entity.path.toLowerCase().endsWith('.jpg')) {
      await entity.delete();
      deleted++;
    }
  }
  return deleted;
}
