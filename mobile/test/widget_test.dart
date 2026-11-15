import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/capture/bulk_capture_queue.dart';
import 'package:mobile/capture/captured_photo_preview.dart';
import 'package:mobile/capture/queue_action_button.dart';
import 'package:mobile/capture/single_entry_workflow.dart';
import 'package:mobile/connection/desktop_discovery.dart';
import 'package:mobile/connection/mobile_connection_controller.dart';
import 'package:mobile/connection/mobile_setup_screen.dart';
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

class _MemoryPairingStore implements PairingStore {
  DesktopPairing? pairing;

  @override
  Future<void> clear() async => pairing = null;

  @override
  Future<DesktopPairing?> read() async => pairing;

  @override
  Future<void> write(DesktopPairing value) async => pairing = value;

  @override
  Future<void> verify() async {}
}

class _NoDesktopDiscovery implements DesktopDiscovery {
  @override
  Future<DesktopEndpoint?> discover() async => null;

  @override
  Future<void> stop() async {}
}

class _FakeConnectionTransport implements ConnectionTransport {
  @override
  Future<DesktopPairing> pair(
    List<DesktopEndpoint> endpoints,
    String pairingCredential,
    String deviceName,
  ) => throw UnimplementedError();

  @override
  Future<DesktopEndpoint?> validate(
    List<DesktopEndpoint> endpoints,
    String deviceToken,
  ) async => null;

  @override
  Future<bool> unpair(
    List<DesktopEndpoint> endpoints,
    String deviceToken,
  ) async => false;

  @override
  Future<bool> beginBatch(
    DesktopEndpoint endpoint,
    String token,
    String batchId,
    int expectedCount,
  ) async => true;

  @override
  Future<bool> sendCapture(
    DesktopEndpoint endpoint,
    String token,
    String batchId,
    CaptureEntry entry,
  ) async => true;

  @override
  Future<bool> completeBatch(
    DesktopEndpoint endpoint,
    String token,
    String batchId,
  ) async => true;

  @override
  void close() {}
}

MyApp _testApp() => MyApp(
  connectionController: MobileConnectionController(
    store: _MemoryPairingStore(),
    transport: _FakeConnectionTransport(),
    deviceName: 'Test phone',
  ),
);

Future<void> _addTestEntries(BulkCaptureQueue queue, int count) async {
  for (var index = 1; index <= count; index++) {
    await queue.addCapture(
      isbn: '9780306406157',
      photoPath: 'test-photo-$index.jpg',
    );
  }
}

void main() {
  testWidgets('Scan starts the scanner in both capture modes', (
    WidgetTester tester,
  ) async {
    const permissionChannel = MethodChannel(
      'flutter.baseflow.com/permissions/methods',
    );
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(permissionChannel, (_) async => 1);
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(permissionChannel, null),
    );

    for (final mode in CaptureMode.values) {
      final workflow = SingleEntryWorkflow();
      final queue = mode == CaptureMode.bulk ? _testQueue(5) : null;
      await tester.pumpWidget(
        MaterialApp(
          home: CaptureScreen(
            mode: mode,
            queueTarget: mode == CaptureMode.bulk ? 5 : null,
            bulkQueue: queue,
            workflow: workflow,
          ),
        ),
      );

      final scanButton = tester.widget<ElevatedButton>(
        find.widgetWithText(ElevatedButton, 'Scan'),
      );
      expect(scanButton.onPressed, isNotNull);
      expect(find.text('Scan Number'), findsNothing);
      await tester.tap(find.widgetWithText(ElevatedButton, 'Scan'));
      await tester.pumpAndSettle();
      expect(workflow.scannerActive, isTrue);

      await tester.pumpWidget(const SizedBox.shrink());
      queue?.dispose();
      workflow.dispose();
    }
  });

  testWidgets('No ISBN choice starts photo capture in both modes', (
    WidgetTester tester,
  ) async {
    for (final mode in CaptureMode.values) {
      final workflow = SingleEntryWorkflow();
      final queue = mode == CaptureMode.bulk ? _testQueue(5) : null;
      await tester.pumpWidget(
        MaterialApp(
          home: CaptureScreen(
            mode: mode,
            queueTarget: mode == CaptureMode.bulk ? 5 : null,
            bulkQueue: queue,
            workflow: workflow,
          ),
        ),
      );

      await tester.tap(find.widgetWithText(TextButton, 'No ISBN'));
      await tester.pump();
      expect(workflow.captureIsbn, isNull);
      expect(workflow.isNoIsbn, isTrue);
      expect(workflow.photoCameraActive, isTrue);

      await tester.pumpWidget(const SizedBox.shrink());
      queue?.dispose();
      workflow.dispose();
    }
  });

  testWidgets('manual ISBN keypad Done continues into capture state', (
    WidgetTester tester,
  ) async {
    final workflow = SingleEntryWorkflow();
    await tester.pumpWidget(
      MaterialApp(
        home: CaptureScreen(mode: CaptureMode.single, workflow: workflow),
      ),
    );

    await tester.tap(find.text('Enter Manually'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '0-306-40615-2');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 350));

    expect(workflow.captureIsbn, '0306406152');
    expect(workflow.displayedIsbn, '0306406152');
    expect(workflow.photoCameraActive, isTrue);

    await tester.pumpWidget(const SizedBox.shrink());
    workflow.dispose();
  });

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
    await tester.pumpWidget(_testApp());

    expect(find.byKey(const ValueKey('home-banner')), findsOneWidget);
    expect(find.text('Single Entry'), findsOneWidget);
    expect(find.text('Scan and capture one book.'), findsOneWidget);
    expect(find.text('Bulk Entry'), findsOneWidget);
    expect(find.text('Capture multiple books in a queue.'), findsOneWidget);
    expect(find.text('Not paired'), findsOneWidget);

    await tester.tap(find.byTooltip('Menu'));
    await tester.pumpAndSettle();
    expect(find.text('About'), findsOneWidget);
    expect(find.text('Settings'), findsOneWidget);
    expect(find.text('Exit'), findsOneWidget);
    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();
    expect(find.text('Mobile App Setup'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();

    await tester.tap(find.text('Single Entry'));
    await tester.pumpAndSettle();

    expect(find.text('Scan Number'), findsNothing);
    expect(find.text('Enter Manually'), findsOneWidget);
    expect(find.text('No ISBN'), findsOneWidget);
    expect(find.text('Scan'), findsOneWidget);
    final scanButton = tester.widget<ElevatedButton>(
      find.widgetWithText(ElevatedButton, 'Scan'),
    );
    expect(scanButton.onPressed, isNotNull);
    expect(find.text('Take Photo'), findsOneWidget);
    expect(find.text('Retake'), findsOneWidget);
    expect(find.text('Save'), findsOneWidget);
    expect(find.text('Send'), findsOneWidget);
    expect(find.text('Clear'), findsOneWidget);
    expect(find.text('Not paired'), findsOneWidget);
    expect(find.text('Share Photo'), findsNothing);

    for (final label in ['Take Photo', 'Retake', 'Save', 'Send', 'Clear']) {
      final button = tester.widget<ElevatedButton>(
        find.widgetWithText(ElevatedButton, label),
      );
      expect(button.onPressed, isNull);
    }
  });

  testWidgets('home banner asset loads and keeps its source aspect ratio', (
    WidgetTester tester,
  ) async {
    final bytes = await rootBundle.load('assets/banner.png');
    final dimensions = ByteData.sublistView(bytes, 16, 24);
    final sourceRatio = dimensions.getUint32(0) / dimensions.getUint32(4);

    await tester.pumpWidget(_testApp());
    await tester.pumpAndSettle();

    final banner = tester.widget<Image>(
      find.byKey(const ValueKey('home-banner')),
    );
    final size = tester.getSize(find.byKey(const ValueKey('home-banner')));
    expect(banner.fit, BoxFit.contain);
    expect(size.width / size.height, closeTo(sourceRatio, 0.01));
  });

  testWidgets(
    'Visit GitHub opens the repository externally and handles failure',
    (WidgetTester tester) async {
      const channel = MethodChannel('com.bookledger.mobile/external_url');
      MethodCall? receivedCall;
      var shouldOpen = true;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            receivedCall = call;
            return shouldOpen;
          });
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(channel, null),
      );

      await tester.pumpWidget(_testApp());
      await tester.ensureVisible(find.text('Visit GitHub'));
      await tester.tap(find.text('Visit GitHub'));
      await tester.pumpAndSettle();
      expect(receivedCall?.method, 'openGithub');
      expect(
        receivedCall?.arguments,
        'https://github.com/hectordoesgorug/BookLedger',
      );
      expect(
        find.text('Could not open GitHub. Please try again.'),
        findsNothing,
      );

      shouldOpen = false;
      await tester.ensureVisible(find.text('Visit GitHub'));
      await tester.tap(find.text('Visit GitHub'));
      await tester.pumpAndSettle();
      expect(
        find.text('Could not open GitHub. Please try again.'),
        findsOneWidget,
      );
    },
  );

  testWidgets('Exit requests normal Flutter activity shutdown', (
    WidgetTester tester,
  ) async {
    MethodCall? receivedCall;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (call) async {
          receivedCall = call;
          return null;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null),
    );

    await tester.pumpWidget(_testApp());
    await tester.tap(find.byTooltip('Menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Exit'));
    await tester.pump();

    expect(receivedCall?.method, 'SystemNavigator.pop');
  });

  testWidgets('home scrolls on small screens with larger text', (
    WidgetTester tester,
  ) async {
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);

    for (final size in [const Size(320, 480), const Size(412, 915)]) {
      tester.view.physicalSize = size;
      await tester.pumpWidget(
        MaterialApp(
          home: MediaQuery(
            data: const MediaQueryData(textScaler: TextScaler.linear(2)),
            child: const HomeScreen(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('Single Entry'), findsOneWidget);
      expect(find.text('Visit GitHub'), findsOneWidget);
      expect(find.text('Not paired'), findsOneWidget);
    }
  });

  testWidgets('bulk entry preserves its 5 to 20 capacity selector', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(_testApp());

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
    expect(find.text('Not paired'), findsOneWidget);
    expect(find.text('Share Photo'), findsNothing);
    expect(find.text('Hold Queue to finish batch early.'), findsNothing);

    final scanButton = tester.widget<ElevatedButton>(
      find.widgetWithText(ElevatedButton, 'Scan'),
    );
    expect(scanButton.onPressed, isNotNull);
    for (final label in ['Take Photo', 'Retake', 'Save', 'Clear']) {
      final button = tester.widget<ElevatedButton>(
        find.widgetWithText(ElevatedButton, label),
      );
      expect(button.onPressed, isNull);
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
        'Could not queue this capture. Its ISBN and photo remain available.',
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
    expect(find.text('Batch ready to send.'), findsOneWidget);
    expect(
      tester.widget<QueueActionButton>(find.byType(QueueActionButton)).canTap,
      isFalse,
    );
    expect(queue.count, 1);
  });

  testWidgets('forget pairing confirmation can be cancelled or completed', (
    WidgetTester tester,
  ) async {
    final store = _MemoryPairingStore()
      ..pairing = DesktopPairing(
        endpoints: [DesktopEndpoint(address: '192.168.1.20', port: 43821)],
        deviceToken: 'device-token-${List.filled(48, 'x').join()}',
        deviceName: 'Desktop',
      );
    final queue = _testQueue(5);
    await queue.addCapture(isbn: '9780306406157', photoPath: 'queued.jpg');
    final controller = MobileConnectionController(
      store: store,
      transport: _FakeConnectionTransport(),
      discovery: _NoDesktopDiscovery(),
    );
    addTearDown(controller.dispose);
    addTearDown(queue.dispose);
    await controller.initialize();

    await tester.pumpWidget(
      MaterialApp(home: MobileSetupScreen(controller: controller)),
    );
    await tester.pump();
    await tester.tap(find.text('Forget Pairing'));
    await tester.pumpAndSettle();
    expect(find.text('Forget this desktop on this phone?'), findsOneWidget);
    expect(
      find.text('It does not revoke the pairing stored on the desktop.'),
      findsNothing,
    );
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(controller.isPaired, isTrue);
    expect(store.pairing, isNotNull);

    await tester.tap(find.text('Forget Pairing'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Forget'));
    await tester.pumpAndSettle();
    expect(controller.isPaired, isFalse);
    expect(controller.status, MobileConnectionStatus.notPaired);
    expect(store.pairing, isNull);
    expect(queue.count, 1);
    expect(queue.entries.single.photoPath, 'queued.jpg');
    expect(find.text('Pair with desktop QR code'), findsOneWidget);
    expect(find.text('Pair manually'), findsWidgets);
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
