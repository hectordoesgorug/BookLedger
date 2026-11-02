import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/capture/bulk_capture_queue.dart';

Future<Directory> _temporaryCaptureDirectory() =>
    Directory.systemTemp.createTemp('bookledger_bulk_queue_test_');

Future<File> _createPhoto(Directory directory, String name) async {
  final file = File('${directory.path}/$name.jpg');
  await file.writeAsBytes([0xFF, 0xD8, 0xFF, name.length, 0xFF, 0xD9]);
  return file;
}

void main() {
  group('BulkCaptureQueue', () {
    test('accepts the supported minimum and maximum capacities', () {
      final minimum = BulkCaptureQueue(
        capacity: BulkCaptureQueue.minimumCapacity,
      );
      final maximum = BulkCaptureQueue(
        capacity: BulkCaptureQueue.maximumCapacity,
      );
      addTearDown(minimum.dispose);
      addTearDown(maximum.dispose);

      expect(minimum.capacity, 5);
      expect(maximum.capacity, 20);
    });

    test('rejects capacities outside the supported range', () {
      expect(() => BulkCaptureQueue(capacity: 4), throwsArgumentError);
      expect(() => BulkCaptureQueue(capacity: 21), throwsArgumentError);
    });

    test('starts empty and cannot finish an empty batch', () {
      final queue = BulkCaptureQueue(capacity: 5);
      addTearDown(queue.dispose);

      expect(queue.entries, isEmpty);
      expect(queue.count, 0);
      expect(queue.isFull, isFalse);
      expect(queue.isBatchReady, isFalse);
      expect(queue.finishEarly(), isFalse);
    });

    test('accepts duplicate ISBNs as independent ordered captures', () async {
      final directory = await _temporaryCaptureDirectory();
      final queue = BulkCaptureQueue(capacity: 5);
      addTearDown(() async {
        await queue.clearSession();
        queue.dispose();
        await directory.delete(recursive: true);
      });
      final firstPhoto = await _createPhoto(directory, 'first');
      final secondPhoto = await _createPhoto(directory, 'second');
      final timestamp = DateTime.utc(2026, 11, 2);

      final first = await queue.addCapture(
        isbn: '9780306406157',
        photoPath: firstPhoto.path,
        capturedAt: timestamp,
      );
      final second = await queue.addCapture(
        isbn: '9780306406157',
        photoPath: secondPhoto.path,
        capturedAt: timestamp,
      );

      expect(first.captureId, isNot(second.captureId));
      expect(first.isbn, '9780306406157');
      expect(first.photoPath, firstPhoto.path);
      expect(first.capturedAt, timestamp);
      expect(first.sequence, 1);
      expect(second.sequence, 2);
      expect(queue.entries.map((entry) => entry.captureId), [
        first.captureId,
        second.captureId,
      ]);
    });

    test('preserves insertion order and counts repeated additions', () async {
      final directory = await _temporaryCaptureDirectory();
      final queue = BulkCaptureQueue(capacity: 5);
      addTearDown(() async {
        await queue.clearSession();
        queue.dispose();
        await directory.delete(recursive: true);
      });

      for (var index = 1; index <= 3; index++) {
        final photo = await _createPhoto(directory, 'photo_$index');
        await queue.addCapture(isbn: '9780306406157', photoPath: photo.path);
      }

      expect(queue.count, 3);
      expect(queue.entries.map((entry) => entry.sequence), [1, 2, 3]);
      expect(queue.entries.map((entry) => entry.photoPath), [
        '${directory.path}/photo_1.jpg',
        '${directory.path}/photo_2.jpg',
        '${directory.path}/photo_3.jpg',
      ]);
    });

    test('becomes ready at capacity and rejects further insertion', () async {
      final directory = await _temporaryCaptureDirectory();
      final queue = BulkCaptureQueue(capacity: 5);
      addTearDown(() async {
        await queue.clearSession();
        queue.dispose();
        await directory.delete(recursive: true);
      });

      for (var index = 1; index <= 5; index++) {
        final photo = await _createPhoto(directory, 'photo_$index');
        await queue.addCapture(isbn: '9780306406157', photoPath: photo.path);
      }
      final extraPhoto = await _createPhoto(directory, 'extra');

      expect(queue.count, 5);
      expect(queue.isFull, isTrue);
      expect(queue.isBatchReady, isTrue);
      await expectLater(
        queue.addCapture(isbn: '9780306406157', photoPath: extraPhoto.path),
        throwsStateError,
      );
      expect(queue.count, 5);
      expect(await extraPhoto.exists(), isTrue);
    });

    test('early completion preserves an incomplete batch', () async {
      final directory = await _temporaryCaptureDirectory();
      final queue = BulkCaptureQueue(capacity: 15);
      addTearDown(() async {
        await queue.clearSession();
        queue.dispose();
        await directory.delete(recursive: true);
      });
      final photos = <File>[];
      for (var index = 1; index <= 10; index++) {
        final photo = await _createPhoto(directory, 'photo_$index');
        photos.add(photo);
        await queue.addCapture(isbn: '9780306406157', photoPath: photo.path);
      }

      expect(queue.finishEarly(), isTrue);
      expect(queue.isBatchReady, isTrue);
      expect(queue.count, 10);
      expect(queue.entries.map((entry) => entry.sequence), [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
      ]);
      expect(
        await Future.wait(photos.map((photo) => photo.exists())),
        everyElement(true),
      );
      expect(queue.finishEarly(), isFalse);
    });

    test(
      'failed insertion leaves queue empty and keeps an existing entry',
      () async {
        final directory = await _temporaryCaptureDirectory();
        final queue = BulkCaptureQueue(capacity: 5);
        addTearDown(() async {
          await queue.clearSession();
          queue.dispose();
          await directory.delete(recursive: true);
        });
        final validPhoto = await _createPhoto(directory, 'valid');
        await queue.addCapture(
          isbn: '9780306406157',
          photoPath: validPhoto.path,
        );

        await expectLater(
          queue.addCapture(
            isbn: '9780306406157',
            photoPath: '${directory.path}/missing.jpg',
          ),
          throwsA(isA<FileSystemException>()),
        );

        expect(queue.count, 1);
        expect(queue.entries.single.photoPath, validPhoto.path);
        expect(await validPhoto.exists(), isTrue);
      },
    );

    test(
      'rejects invalid ISBN without taking ownership of its photo',
      () async {
        final directory = await _temporaryCaptureDirectory();
        final queue = BulkCaptureQueue(capacity: 5);
        addTearDown(() async {
          await queue.clearSession();
          queue.dispose();
          await directory.delete(recursive: true);
        });
        final photo = await _createPhoto(directory, 'photo');

        await expectLater(
          queue.addCapture(isbn: '9780306406158', photoPath: photo.path),
          throwsArgumentError,
        );

        expect(queue.entries, isEmpty);
        expect(await photo.exists(), isTrue);
      },
    );

    test(
      'session cleanup deletes queued photos and clears in-memory entries',
      () async {
        final directory = await _temporaryCaptureDirectory();
        final queue = BulkCaptureQueue(capacity: 5);
        final queuedPhoto = await _createPhoto(directory, 'queued');
        final unrelatedPhoto = await _createPhoto(directory, 'unrelated');
        await queue.addCapture(
          isbn: '9780306406157',
          photoPath: queuedPhoto.path,
        );
        expect(queue.finishEarly(), isTrue);

        await queue.clearSession();

        expect(queue.entries, isEmpty);
        expect(queue.count, 0);
        expect(queue.isBatchReady, isFalse);
        expect(await queuedPhoto.exists(), isFalse);
        expect(await unrelatedPhoto.exists(), isTrue);
        queue.dispose();
        await directory.delete(recursive: true);
      },
    );
  });
}
