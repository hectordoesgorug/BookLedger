import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/settings/clear_mobile_data.dart';

void main() {
  test('cleanup deletes only app-owned pending JPEGs', () async {
    final directory = await Directory.systemTemp.createTemp(
      'bookledger-pending-files-',
    );
    addTearDown(() => directory.delete(recursive: true));
    final pending = File('${directory.path}/bookledger_capture_test.jpg');
    final unrelated = File('${directory.path}/desktop-backup.zip');
    final otherPhoto = File('${directory.path}/user-photo.jpg');
    final nonJpegCapture = File(
      '${directory.path}/bookledger_capture_note.txt',
    );
    for (final file in [pending, unrelated, otherPhoto, nonJpegCapture]) {
      await file.writeAsBytes([1, 2, 3]);
    }

    expect(await clearPendingCapturePhotos(directory), 1);
    expect(await pending.exists(), isFalse);
    expect(await unrelated.exists(), isTrue);
    expect(await otherPhoto.exists(), isTrue);
    expect(await nonJpegCapture.exists(), isTrue);
  });

  test('cleanup propagates a directory failure for the caller to report', () async {
    final missing = Directory(
      '${Directory.systemTemp.path}/bookledger-missing-${DateTime.now().microsecondsSinceEpoch}',
    );

    await expectLater(
      clearPendingCapturePhotos(missing),
      throwsA(isA<FileSystemException>()),
    );
  });
}
