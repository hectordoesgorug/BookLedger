import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/capture/bulk_capture_queue.dart';
import 'package:mobile/capture/captured_photo_preview.dart';
import 'package:mobile/capture/queue_action_button.dart';
import 'package:mobile/capture/single_entry_workflow.dart';
import 'package:mobile/main.dart';

Future<SingleEntryWorkflow> _pairedWorkflow(String photoPath) async {
  final workflow = SingleEntryWorkflow();
  expect(await workflow.scanIsbn('9780306406157'), isTrue);
  expect(workflow.saveIsbn(), isTrue);
  expect(await workflow.photoCaptured(photoPath), isTrue);
  expect(workflow.savePhoto(), isTrue);
  return workflow;
}

BulkCaptureQueue _testQueue(int capacity) =>
    BulkCaptureQueue(capacity: capacity, photoExists: (_) async => true);

Future<void> _addTestEntries(BulkCaptureQueue queue, int count) async {
  for (var index = 1; index <= count; index++) {
    await queue.addCapture(
      isbn: '9780306406157',
      photoPath: 'test-photo-$index.jpg',
    );
  }
}

void main() {
  testWidgets('captured photo preview contains the full camera frame', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 400,
          height: 300,
          child: CapturedPhotoPreview(file: File('missing-camera-photo.jpg')),
        ),
      ),
    );

    expect(tester.widget<Image>(find.byType(Image)).fit, BoxFit.contain);
  });

  testWidgets('home menu and single entry show the foundation UI', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const MyApp());

    expect(find.text('BookLedger'), findsWidgets);
    expect(find.text('Single Entry'), findsOneWidget);
    expect(find.text('Bulk Entry'), findsOneWidget);
    expect(find.text('Not connected'), findsOneWidget);

    await tester.tap(find.byTooltip('Menu'));
    await tester.pumpAndSettle();
    expect(find.text('About'), findsOneWidget);
    expect(find.text('Settings'), findsOneWidget);
    expect(find.text('Exit'), findsOneWidget);
    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();
    expect(
      find.text('Settings will be available in a later version.'),
      findsOneWidget,
    );
    await tester.pageBack();
    await tester.pumpAndSettle();

    await tester.tap(find.text('Single Entry'));
    await tester.pumpAndSettle();

    expect(find.bySemanticsLabel('Camera preview area'), findsOneWidget);
    expect(find.text('Scan'), findsOneWidget);
    expect(find.text('Take Photo'), findsOneWidget);
    expect(find.text('Retake'), findsOneWidget);
    expect(find.text('Save'), findsOneWidget);
    expect(find.text('Send'), findsOneWidget);
    expect(find.text('Clear'), findsOneWidget);
    expect(find.text('Not connected'), findsOneWidget);
    expect(find.text('Share Photo'), findsNothing);

    for (final label in [
      'Scan',
      'Take Photo',
      'Retake',
      'Save',
      'Send',
      'Clear',
    ]) {
      final button = tester.widget<ElevatedButton>(
        find.widgetWithText(ElevatedButton, label),
      );
      expect(button.onPressed != null, label == 'Scan');
    }
  });

  testWidgets('bulk entry preserves its 5 to 20 capacity selector', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const MyApp());

    await tester.tap(find.text('Bulk Entry'));
    await tester.pumpAndSettle();

    final slider = tester.widget<Slider>(find.byType(Slider));
    expect(slider.min, 5);
    expect(slider.max, 20);
    expect(find.byKey(const ValueKey('selected-queue-size')), findsOneWidget);

    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();

    expect(find.text('Queue'), findsWidgets);
    expect(find.text('0 / 5'), findsOneWidget);
    expect(find.text('Send'), findsNothing);
    expect(find.text('Not connected'), findsOneWidget);
    expect(find.text('Share Photo'), findsNothing);
    expect(find.text('Hold Queue to finish batch early.'), findsNothing);

    for (final label in ['Scan', 'Take Photo', 'Retake', 'Save', 'Clear']) {
      final button = tester.widget<ElevatedButton>(
        find.widgetWithText(ElevatedButton, label),
      );
      expect(button.onPressed != null, label == 'Scan');
    }
    final queueButton = tester.widget<QueueActionButton>(
      find.byType(QueueActionButton),
    );
    expect(queueButton.label, 'Queue');
    expect(queueButton.canTap, isFalse);
    expect(queueButton.canLongPress, isFalse);
  });

  testWidgets(
    'successful queue insertion resets capture and retains the photo reference',
    (WidgetTester tester) async {
      final queue = _testQueue(5);
      final workflow = await _pairedWorkflow('queued-photo.jpg');
      addTearDown(() {
        queue.dispose();
        workflow.dispose();
      });

      await tester.pumpWidget(
        MaterialApp(
          home: CaptureScreen(
            mode: CaptureMode.bulk,
            queueTarget: 5,
            bulkQueue: queue,
            workflow: workflow,
          ),
        ),
      );

      await tester.tap(find.byKey(const ValueKey('queue-action')));
      await tester.pumpAndSettle();

      expect(queue.count, 1);
      expect(find.text('1 / 5'), findsOneWidget);
      expect(workflow.stage, SingleCaptureStage.empty);
      expect(workflow.photoPath, isNull);
      expect(queue.entries.single.photoPath, 'queued-photo.jpg');
    },
  );

  testWidgets('failed queue insertion preserves the current capture', (
    WidgetTester tester,
  ) async {
    final queue = BulkCaptureQueue(
      capacity: 5,
      photoExists: (_) async => false,
    );
    final workflow = await _pairedWorkflow('missing-photo.jpg');
    addTearDown(() {
      queue.dispose();
      workflow.dispose();
    });

    await tester.pumpWidget(
      MaterialApp(
        home: CaptureScreen(
          mode: CaptureMode.bulk,
          queueTarget: 5,
          bulkQueue: queue,
          workflow: workflow,
        ),
      ),
    );

    await tester.tap(find.byKey(const ValueKey('queue-action')));
    await tester.pumpAndSettle();

    expect(queue.count, 0);
    expect(find.text('0 / 5'), findsOneWidget);
    expect(workflow.stage, SingleCaptureStage.paired);
    expect(workflow.displayedIsbn, '9780306406157');
    expect(workflow.photoPath, 'missing-photo.jpg');
    expect(
      find.text(
        'Could not add this capture. Its ISBN and photo are still available.',
      ),
      findsOneWidget,
    );
  });

  testWidgets('queue button becomes Send at selected capacity', (
    WidgetTester tester,
  ) async {
    final queue = _testQueue(5);
    await _addTestEntries(queue, 4);
    final workflow = await _pairedWorkflow('current-photo.jpg');
    addTearDown(() {
      queue.dispose();
      workflow.dispose();
    });

    await tester.pumpWidget(
      MaterialApp(
        home: CaptureScreen(
          mode: CaptureMode.bulk,
          queueTarget: 5,
          bulkQueue: queue,
          workflow: workflow,
        ),
      ),
    );

    await tester.tap(find.byKey(const ValueKey('queue-action')));
    await tester.pumpAndSettle();

    expect(queue.count, 5);
    expect(queue.isBatchReady, isTrue);
    expect(find.text('5 / 5'), findsOneWidget);
    expect(
      tester.widget<QueueActionButton>(find.byType(QueueActionButton)).label,
      'Send',
    );
    expect(find.text('Queue'), findsOneWidget);
  });

  testWidgets('long press finishes an incomplete batch without sending it', (
    WidgetTester tester,
  ) async {
    final queue = _testQueue(15);
    await _addTestEntries(queue, 1);
    addTearDown(queue.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: CaptureScreen(
          mode: CaptureMode.bulk,
          queueTarget: 15,
          bulkQueue: queue,
        ),
      ),
    );

    await tester.longPress(find.byKey(const ValueKey('queue-action')));
    await tester.pumpAndSettle();

    expect(queue.isBatchReady, isTrue);
    expect(queue.count, 1);
    expect(find.text('1 / 15'), findsOneWidget);
    expect(find.text('Send'), findsOneWidget);
    expect(
      find.text('Batch ready. Transfer is not available yet.'),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const ValueKey('queue-action')));
    await tester.pumpAndSettle();
    expect(
      find.text(
        'This batch is ready. Transfer will be available in a later version.',
      ),
      findsOneWidget,
    );
    expect(queue.count, 1);
  });

  testWidgets('cancelled long press does not finish the batch', (
    WidgetTester tester,
  ) async {
    final queue = _testQueue(15);
    await _addTestEntries(queue, 1);
    addTearDown(queue.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: CaptureScreen(
          mode: CaptureMode.bulk,
          queueTarget: 15,
          bulkQueue: queue,
        ),
      ),
    );

    final gesture = await tester.startGesture(
      tester.getCenter(find.byKey(const ValueKey('queue-action'))),
    );
    await tester.pump(const Duration(milliseconds: 100));
    await gesture.up();
    await tester.pumpAndSettle();

    expect(queue.isBatchReady, isFalse);
    expect(
      tester.widget<QueueActionButton>(find.byType(QueueActionButton)).label,
      'Queue',
    );
    expect(find.text('1 / 15'), findsOneWidget);
  });
}
