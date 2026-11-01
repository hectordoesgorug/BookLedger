import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/capture/single_entry_workflow.dart';

Future<Directory> _temporaryCaptureDirectory() =>
    Directory.systemTemp.createTemp('bookledger_capture_test_');

Future<File> _createPhoto(Directory directory, String name) async {
  final file = File('${directory.path}/$name.jpg');
  await file.writeAsBytes([0xFF, 0xD8, 0xFF]);
  return file;
}

Future<SingleEntryWorkflow> _savedIsbnWorkflow() async {
  final workflow = SingleEntryWorkflow();
  expect(await workflow.scanIsbn('9780306406157'), isTrue);
  expect(workflow.stage, SingleCaptureStage.isbnScanned);
  expect(workflow.saveIsbn(), isTrue);
  expect(workflow.stage, SingleCaptureStage.isbnSaved);
  return workflow;
}

void main() {
  group('Single entry workflow', () {
    test('starts empty', () {
      final workflow = SingleEntryWorkflow();
      addTearDown(workflow.dispose);

      expect(workflow.stage, SingleCaptureStage.empty);
      expect(workflow.displayedIsbn, isNull);
      expect(workflow.photoPath, isNull);
      expect(workflow.pairedIsbn, isNull);
      expect(workflow.photoCameraActive, isFalse);
      expect(workflow.hasCaptureData, isFalse);
    });

    test('accepts valid ISBN-10 and ISBN-13 values', () async {
      final workflow = SingleEntryWorkflow();
      addTearDown(workflow.dispose);

      expect(await workflow.scanIsbn('0-306-40615-2'), isTrue);
      expect(workflow.displayedIsbn, '0306406152');
      expect(await workflow.scanIsbn('ISBN-13: 978-0-306-40615-7'), isTrue);
      expect(workflow.displayedIsbn, '9780306406157');
      expect(workflow.stage, SingleCaptureStage.isbnScanned);
    });

    test(
      'rejects invalid ISBNs without replacing a valid scanned value',
      () async {
        final workflow = SingleEntryWorkflow();
        addTearDown(workflow.dispose);

        expect(await workflow.scanIsbn('9780306406157'), isTrue);
        expect(await workflow.scanIsbn('9780306406158'), isFalse);
        expect(await workflow.scanIsbn('not a barcode ISBN'), isFalse);
        expect(workflow.displayedIsbn, '9780306406157');
        expect(workflow.stage, SingleCaptureStage.isbnScanned);
      },
    );

    test('saving ISBN enables a separate photo-camera state', () async {
      final workflow = await _savedIsbnWorkflow();
      addTearDown(workflow.dispose);

      expect(workflow.beginPhotoCapture(), isTrue);
      expect(workflow.stage, SingleCaptureStage.photoCamera);
      expect(workflow.displayedIsbn, '9780306406157');
      workflow.cancelPhotoCapture();
      expect(workflow.stage, SingleCaptureStage.isbnSaved);
    });

    test('captured photo remains unpaired until explicitly saved', () async {
      final directory = await _temporaryCaptureDirectory();
      final photo = await _createPhoto(directory, 'front');
      final workflow = await _savedIsbnWorkflow();
      addTearDown(() async {
        await workflow.clear();
        workflow.dispose();
        await directory.delete(recursive: true);
      });

      expect(workflow.beginPhotoCapture(), isTrue);
      expect(await workflow.photoCaptured(photo.path), isTrue);
      expect(workflow.stage, SingleCaptureStage.photoCaptured);
      expect(workflow.pairedIsbn, isNull);
      expect(workflow.savePhoto(), isTrue);
      expect(workflow.stage, SingleCaptureStage.paired);
      expect(workflow.pairedIsbn, '9780306406157');
    });

    test(
      'retake preserves ISBN and replaces the old photo after capture',
      () async {
        final directory = await _temporaryCaptureDirectory();
        final firstPhoto = await _createPhoto(directory, 'first');
        final replacementPhoto = await _createPhoto(directory, 'replacement');
        final workflow = await _savedIsbnWorkflow();
        addTearDown(() async {
          await workflow.clear();
          workflow.dispose();
          await directory.delete(recursive: true);
        });

        workflow.beginPhotoCapture();
        await workflow.photoCaptured(firstPhoto.path);
        workflow.savePhoto();

        expect(workflow.beginPhotoCapture(), isTrue);
        expect(workflow.stage, SingleCaptureStage.photoCamera);
        expect(workflow.displayedIsbn, '9780306406157');
        expect(await workflow.photoCaptured(replacementPhoto.path), isTrue);
        expect(await File(firstPhoto.path).exists(), isFalse);
        expect(workflow.photoPath, replacementPhoto.path);
        expect(workflow.pairedIsbn, isNull);
        expect(workflow.stage, SingleCaptureStage.photoCaptured);
      },
    );

    test(
      'rescanning invalidates the paired photo and removes its file',
      () async {
        final directory = await _temporaryCaptureDirectory();
        final photo = await _createPhoto(directory, 'paired');
        final workflow = await _savedIsbnWorkflow();
        addTearDown(() async {
          await workflow.clear();
          workflow.dispose();
          await directory.delete(recursive: true);
        });

        workflow.beginPhotoCapture();
        await workflow.photoCaptured(photo.path);
        workflow.savePhoto();

        expect(await workflow.scanIsbn('0306406152'), isTrue);
        expect(workflow.stage, SingleCaptureStage.isbnScanned);
        expect(workflow.displayedIsbn, '0306406152');
        expect(workflow.photoPath, isNull);
        expect(workflow.pairedIsbn, isNull);
        expect(await File(photo.path).exists(), isFalse);
      },
    );

    test(
      'clear resets the whole capture and removes the temporary photo',
      () async {
        final directory = await _temporaryCaptureDirectory();
        final photo = await _createPhoto(directory, 'clear');
        final workflow = await _savedIsbnWorkflow();
        addTearDown(() async {
          await workflow.clear();
          workflow.dispose();
          await directory.delete(recursive: true);
        });

        workflow.beginPhotoCapture();
        await workflow.photoCaptured(photo.path);
        workflow.savePhoto();
        await workflow.clear();

        expect(workflow.stage, SingleCaptureStage.empty);
        expect(workflow.displayedIsbn, isNull);
        expect(workflow.photoPath, isNull);
        expect(workflow.pairedIsbn, isNull);
        expect(workflow.hasCaptureData, isFalse);
        expect(await File(photo.path).exists(), isFalse);
      },
    );

    test('clear cancels a live photo mode without losing cleanup', () async {
      final workflow = await _savedIsbnWorkflow();
      addTearDown(workflow.dispose);

      expect(workflow.beginPhotoCapture(), isTrue);
      await workflow.clear();
      expect(workflow.stage, SingleCaptureStage.empty);
      expect(workflow.photoCameraActive, isFalse);
    });

    test('does not pair a photo unless an ISBN was saved first', () async {
      final workflow = SingleEntryWorkflow();
      addTearDown(workflow.dispose);

      expect(workflow.beginPhotoCapture(), isFalse);
      expect(workflow.savePhoto(), isFalse);
      expect(workflow.stage, SingleCaptureStage.empty);
    });

    test('rescan before save replaces only the pending ISBN', () async {
      final workflow = SingleEntryWorkflow();
      addTearDown(workflow.dispose);

      await workflow.scanIsbn('9780306406157');
      await workflow.scanIsbn('0306406152');
      expect(workflow.displayedIsbn, '0306406152');
      expect(workflow.stage, SingleCaptureStage.isbnScanned);
      expect(workflow.beginPhotoCapture(), isFalse);
    });
  });
}
