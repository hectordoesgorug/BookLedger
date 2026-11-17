import 'dart:io';
import 'dart:async';

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
import 'package:mobile/settings/about_screen.dart';
import 'package:mobile/settings/mobile_app_settings.dart';
import 'package:mobile/settings/settings_screen.dart';

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

Future<void> _scrollSettingsTo(
  WidgetTester tester,
  Finder target, [
  double delta = 200,
]) => tester.scrollUntilVisible(
  target,
  delta,
  scrollable: find
      .descendant(
        of: find.byKey(const ValueKey('settings-list')),
        matching: find.byType(Scrollable),
      )
      .first,
);

class _MemoryPairingStore implements PairingStore {
  DesktopPairing? pairing;
  bool failClear = false;

  @override
  Future<void> clear() async {
    if (failClear) throw const FileSystemException('Pairing clear failed.');
    pairing = null;
  }

  @override
  Future<DesktopPairing?> read() async => pairing;

  @override
  Future<void> write(DesktopPairing value) async => pairing = value;
}

class _NoDesktopDiscovery implements DesktopDiscovery {
  @override
  Future<DesktopEndpoint?> discover() async => null;

  @override
  Future<void> stop() async {}
}

class _NoFileCleanupWorkflow extends SingleEntryWorkflow {
  @override
  Future<void> clear() async {
    resetAfterSuccessfulTransfer();
  }
}

class _FakeConnectionTransport implements ConnectionTransport {
  Completer<DesktopEndpoint?>? validation;
  DesktopEndpoint? validationResult;
  final validationResults = <DesktopEndpoint?>[];
  int unpairCalls = 0;
  int beginBatchCalls = 0;

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
  ) {
    if (validation != null) return validation!.future;
    return Future<DesktopEndpoint?>.value(
      validationResults.isEmpty
          ? validationResult
          : validationResults.removeAt(0),
    );
  }

  @override
  Future<bool> unpair(
    List<DesktopEndpoint> endpoints,
    String deviceToken,
  ) async {
    unpairCalls++;
    return false;
  }

  @override
  Future<bool> beginBatch(
    DesktopEndpoint endpoint,
    String token,
    String batchId,
    int expectedCount,
  ) async {
    beginBatchCalls++;
    return true;
  }

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

MobileConnectionController _testConnectionController() =>
    MobileConnectionController(
      store: _MemoryPairingStore(),
      transport: _FakeConnectionTransport(),
      deviceName: 'Test phone',
    );

MyApp _testApp() => MyApp(connectionController: _testConnectionController());

DesktopPairing _savedPairing() => DesktopPairing(
  endpoints: [DesktopEndpoint(address: '192.168.1.20', port: 43821)],
  deviceToken: 'device-token-${List.filled(48, 'x').join()}',
  deviceName: 'Desktop',
  lastEndpoint: DesktopEndpoint(address: '192.168.1.20', port: 43821),
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
    expect(find.text('Pairing'), findsOneWidget);
    expect(find.text('Pair with desktop QR code'), findsOneWidget);
    expect(find.text('Desktop IPv4 address'), findsOneWidget);
    expect(find.text('Test secure storage'), findsNothing);
    expect(find.byType(ListView), findsOneWidget);
    await _scrollSettingsTo(
      tester,
      find.byKey(const ValueKey('dark-mode-switch')),
    );
    expect(tester.widget<Switch>(find.byType(Switch)).value, isFalse);
    await _scrollSettingsTo(
      tester,
      find.byKey(const ValueKey('clear-data-action')),
    );
    expect(find.text('Clear Data'), findsWidgets);
    expect(
      find.byKey(const ValueKey('settings-clear-data-heading')),
      findsOneWidget,
    );
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.text('Single Entry'), findsOneWidget);

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

  testWidgets('connected footer names BookLedger Desktop', (
    WidgetTester tester,
  ) async {
    final store = _MemoryPairingStore()..pairing = _savedPairing();
    final controller = MobileConnectionController(
      store: store,
      transport: _FakeConnectionTransport()
        ..validationResult = _savedPairing().endpoints.first,
      discovery: _NoDesktopDiscovery(),
    );
    addTearDown(() {
      controller.didChangeAppLifecycleState(AppLifecycleState.paused);
      controller.dispose();
    });
    await controller.initialize();
    await tester.pump();
    await tester.pump();
    expect(controller.status, MobileConnectionStatus.connected);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: ConnectionStatus(controller: controller)),
      ),
    );
    await tester.pump();

    expect(
      find.text('Connected · Connected to BookLedger Desktop.'),
      findsOneWidget,
    );
    final icon = tester.widget<Icon>(find.byIcon(Icons.check_circle));
    expect(
      icon.color,
      Theme.of(tester.element(find.byType(ConnectionStatus)))
          .colorScheme
          .tertiary,
    );
    await controller.clearLocalPairing();
  });

  testWidgets('successful single transfer shows the success notice', (
    WidgetTester tester,
  ) async {
    final controller = MobileConnectionController(
      store: _MemoryPairingStore()..pairing = _savedPairing(),
      transport: _FakeConnectionTransport()
        ..validationResult = _savedPairing().endpoints.first,
      discovery: _NoDesktopDiscovery(),
    );
    addTearDown(() {
      controller.didChangeAppLifecycleState(AppLifecycleState.paused);
      controller.dispose();
    });
    await controller.initialize();
    await tester.pump();
    await tester.pump();
    expect(controller.isConnected, isTrue);
    final workflow = _NoFileCleanupWorkflow();
    expect(await workflow.scanIsbn('9780306406157'), isTrue);
    expect(workflow.saveIsbn(), isTrue);
    expect(
      await workflow.photoCaptured('successful-transfer-photo.jpg'),
      isTrue,
    );
    expect(workflow.savePhoto(), isTrue);
    addTearDown(workflow.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: CaptureScreen(
          mode: CaptureMode.single,
          workflow: workflow,
          connectionController: controller,
        ),
      ),
    );
    final sendButton = tester.widget<ElevatedButton>(
      find.widgetWithText(ElevatedButton, 'Send'),
    );
    expect(sendButton.onPressed, isNotNull);
    await tester.tap(find.widgetWithText(ElevatedButton, 'Send'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(
      find.text(
        'Desktop received the capture. Cataloging will follow on desktop.',
      ),
      findsOneWidget,
    );
    final theme = Theme.of(tester.element(find.byType(SnackBar)));
    expect(
      tester.widget<SnackBar>(find.byType(SnackBar)).backgroundColor,
      theme.colorScheme.tertiaryContainer,
    );
    await controller.clearLocalPairing();
    ScaffoldMessenger.of(tester.element(find.byType(SnackBar)))
        .hideCurrentSnackBar();
    await tester.pump(const Duration(milliseconds: 300));
  });

  testWidgets('Single Entry Send follows authenticated reconnection', (
    WidgetTester tester,
  ) async {
    final transport = _FakeConnectionTransport()
      ..validationResults.addAll([
        _savedPairing().endpoints.first,
        null,
        _savedPairing().endpoints.first,
      ]);
    final controller = MobileConnectionController(
      store: _MemoryPairingStore()..pairing = _savedPairing(),
      transport: transport,
      discovery: _NoDesktopDiscovery(),
    );
    var controllerDisposed = false;
    void disposeController() {
      if (controllerDisposed) return;
      controllerDisposed = true;
      controller.didChangeAppLifecycleState(AppLifecycleState.paused);
      controller.dispose();
    }

    addTearDown(disposeController);
    await controller.initialize();
    await tester.pump();
    await tester.pump();
    expect(controller.isConnected, isTrue);

    final workflow = await _pairedWorkflow('reconnect-single.jpg');
    addTearDown(workflow.dispose);
    final captureId = workflow.captureId;
    await tester.pumpWidget(
      MaterialApp(
        home: CaptureScreen(
          mode: CaptureMode.single,
          workflow: workflow,
          connectionController: controller,
        ),
      ),
    );

    ElevatedButton sendButton() => tester.widget<ElevatedButton>(
      find.widgetWithText(ElevatedButton, 'Send'),
    );

    expect(sendButton().onPressed, isNotNull);
    expect(await controller.manualReconnect(), isFalse);
    await tester.pump();
    expect(controller.status, MobileConnectionStatus.disconnected);
    expect(sendButton().onPressed, isNull);
    expect(workflow.isCaptureReady, isTrue);

    expect(await controller.manualReconnect(), isTrue);
    await tester.pump();
    expect(sendButton().onPressed, isNotNull);
    expect(workflow.captureId, captureId);
    expect(workflow.displayedIsbn, '9780306406157');
    expect(workflow.photoPath, 'reconnect-single.jpg');
    expect(transport.beginBatchCalls, 0);
    await tester.pumpWidget(const SizedBox.shrink());
    disposeController();
  });

  testWidgets(
    'Bulk Entry Send follows reconnection without changing its batch',
    (WidgetTester tester) async {
      final endpoint = _savedPairing().endpoints.first;
      final transport = _FakeConnectionTransport()
        ..validationResults.addAll([endpoint, null, endpoint]);
      final controller = MobileConnectionController(
        store: _MemoryPairingStore()..pairing = _savedPairing(),
        transport: transport,
        discovery: _NoDesktopDiscovery(),
      );
      var controllerDisposed = false;
      void disposeController() {
        if (controllerDisposed) return;
        controllerDisposed = true;
        controller.didChangeAppLifecycleState(AppLifecycleState.paused);
        controller.dispose();
      }

      addTearDown(disposeController);
      await controller.initialize();
      await tester.pump();
      await tester.pump();
      expect(controller.isConnected, isTrue);

      final queue = _testQueue(5);
      await _addTestEntries(queue, 5);
      addTearDown(queue.dispose);
      final batchId = queue.batchId;
      final captureIds = queue.entries.map((entry) => entry.captureId).toList();
      await tester.pumpWidget(
        MaterialApp(
          home: CaptureScreen(
            mode: CaptureMode.bulk,
            queueTarget: 5,
            bulkQueue: queue,
            connectionController: controller,
          ),
        ),
      );

      QueueActionButton sendButton() =>
          tester.widget<QueueActionButton>(find.byType(QueueActionButton));

      expect(sendButton().label, 'Send');
      expect(sendButton().canTap, isTrue);
      expect(await controller.manualReconnect(), isFalse);
      await tester.pump();
      expect(sendButton().canTap, isFalse);
      expect(queue.isBatchReady, isTrue);

      expect(await controller.manualReconnect(), isTrue);
      await tester.pump();
      expect(sendButton().canTap, isTrue);
      expect(queue.batchId, batchId);
      expect(queue.entries.map((entry) => entry.captureId), captureIds);
      expect(queue.count, 5);
      expect(transport.beginBatchCalls, 0);
      await tester.pumpWidget(const SizedBox.shrink());
      disposeController();
    },
  );

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
      final links = tester.getRect(
        find.byKey(const ValueKey('home-footer-links')),
      );
      final status = tester.getRect(find.byType(ConnectionStatus));
      expect(links.bottom, lessThanOrEqualTo(status.top));
      expect(status.bottom, lessThanOrEqualTo(size.height));
    }
  });

  testWidgets('Home footer keeps GitHub and version above connection status', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(406, 904);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    const channel = MethodChannel('com.bookledger.mobile/app_settings');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          if (call.method == 'getAppSettings') {
            return {'version': '1.2.3', 'theme': 'default'};
          }
          return true;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, null),
    );
    final settings = MobileAppSettings();
    addTearDown(settings.dispose);
    await settings.initialize();

    await tester.pumpWidget(
      MaterialApp(home: HomeScreen(appSettings: settings)),
    );
    await tester.pumpAndSettle();

    final connectionTop = tester.getTopLeft(find.byType(ConnectionStatus)).dy;
    final github = tester.getRect(
      find.widgetWithText(TextButton, 'Visit GitHub'),
    );
    final version = tester.getRect(find.byKey(const ValueKey('home-version')));
    final pairConnect = tester.getRect(
      find.widgetWithText(OutlinedButton, 'Pair / Connect'),
    );

    expect(find.text('BookLedger Mobile • v1.2.3'), findsOneWidget);
    expect(pairConnect.bottom, lessThan(github.top));
    expect(github.bottom, lessThan(version.top));
    expect(version.bottom, lessThan(connectionTop));
    expect(
      tester.getBottomRight(find.byType(ConnectionStatus)).dy,
      lessThanOrEqualTo(904),
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'About guide includes workflow, version and external project link',
    (WidgetTester tester) async {
      const appSettingsChannel = MethodChannel(
        'com.bookledger.mobile/app_settings',
      );
      const externalUrlChannel = MethodChannel(
        'com.bookledger.mobile/external_url',
      );
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        ..setMockMethodCallHandler(appSettingsChannel, (call) async {
          return {'version': '1.2.3', 'theme': 'default'};
        })
        ..setMockMethodCallHandler(externalUrlChannel, (_) async => true);
      addTearDown(() {
        final messenger =
            TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
        messenger
          ..setMockMethodCallHandler(appSettingsChannel, null)
          ..setMockMethodCallHandler(externalUrlChannel, null);
      });

      await tester.pumpWidget(_testApp());
      await tester.pumpAndSettle();
      expect(find.text('BookLedger Mobile • v1.2.3'), findsOneWidget);
      await tester.tap(find.byTooltip('Menu'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('About'));
      await tester.pumpAndSettle();

      for (final heading in [
        'About BookLedger Mobile',
        'Getting Started',
        'Single Entry',
        'Bulk Entry',
        'Camera Controls',
        'Pairing and Connectivity',
        'Troubleshooting',
        'Version and Project Information',
      ]) {
        for (
          var scroll = 0;
          scroll < 10 && find.text(heading).evaluate().isEmpty;
          scroll++
        ) {
          await tester.drag(find.byType(ListView).last, const Offset(0, -400));
          await tester.pumpAndSettle();
        }
        expect(find.text(heading), findsOneWidget);
      }
      expect(find.text('BookLedger Mobile • v1.2.3'), findsOneWidget);
      for (
        var scroll = 0;
        scroll < 10 && find.text('Camera Controls').evaluate().isEmpty;
        scroll++
      ) {
        await tester.drag(find.byType(ListView).last, const Offset(0, 350));
        await tester.pumpAndSettle();
      }
      expect(find.text('Camera Controls'), findsOneWidget);
      expect(
        find.textContaining('continuous camera lighting on or off'),
        findsOneWidget,
      );
      expect(
        find.textContaining('0.5× steps from 0.5× up to 3.0×'),
        findsOneWidget,
      );
      expect(find.textContaining('do not offer 0.5×'), findsOneWidget);
      expect(
        find.textContaining('Your selected zoom is remembered.'),
        findsOneWidget,
      );
      expect(
        find.textContaining('cycle through L-shaped corner guides'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Your selection is remembered.'),
        findsOneWidget,
      );
      expect(find.textContaining('overlays do not crop'), findsOneWidget);
      expect(find.byType(Scrollable), findsWidgets);
      for (
        var scroll = 0;
        scroll < 10 && find.text('BookLedger on GitHub').evaluate().isEmpty;
        scroll++
      ) {
        await tester.drag(find.byType(ListView).last, const Offset(0, -350));
        await tester.pumpAndSettle();
      }
      expect(find.text('BookLedger on GitHub'), findsOneWidget);
      await tester.drag(find.byType(ListView).last, const Offset(0, -160));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('BookLedger on GitHub'));
      await tester.tap(find.text('BookLedger on GitHub'));
      await tester.pumpAndSettle();
    },
  );

  testWidgets('selected theme updates the whole application immediately', (
    WidgetTester tester,
  ) async {
    const channel = MethodChannel('com.bookledger.mobile/app_settings');
    var theme = 'default';
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          if (call.method == 'getAppSettings') {
            return {'version': '1.0.0', 'theme': theme};
          }
          if (call.method == 'setTheme') {
            theme = call.arguments as String;
            return true;
          }
          return null;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, null),
    );
    final appSettings = MobileAppSettings();
    addTearDown(appSettings.dispose);
    final controller = _testConnectionController();

    await tester.pumpWidget(
      MyApp(connectionController: controller, appSettings: appSettings),
    );
    await tester.pumpAndSettle();
    expect(
      tester.widget<MaterialApp>(find.byType(MaterialApp)).themeMode,
      ThemeMode.light,
    );
    await tester.tap(find.byTooltip('Menu'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();
    await _scrollSettingsTo(
      tester,
      find.byKey(const ValueKey('dark-mode-switch')),
    );
    await tester.tap(find.byKey(const ValueKey('dark-mode-switch')));
    await tester.pumpAndSettle();
    expect(theme, 'dark');
    expect(
      tester.widget<MaterialApp>(find.byType(MaterialApp)).themeMode,
      ThemeMode.dark,
    );
  });

  testWidgets('Settings scrolls on small screens with enlarged text', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(320, 480);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final controller = _testConnectionController();
    addTearDown(controller.dispose);
    final settings = MobileAppSettings();
    addTearDown(settings.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(1.6)),
          child: SettingsScreen(controller: controller, settings: settings),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(ListView), findsOneWidget);
    expect(find.text('Pairing'), findsOneWidget);
    expect(find.text('Pair with desktop QR code'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await _scrollSettingsTo(
      tester,
      find.byKey(const ValueKey('dark-mode-switch')),
      160,
    );
    await tester.pumpAndSettle();
    expect(find.text('Dark Mode'), findsOneWidget);
    expect(find.byType(Switch), findsOneWidget);
    expect(tester.takeException(), isNull);

    await _scrollSettingsTo(
      tester,
      find.byKey(const ValueKey('clear-data-action')),
      160,
    );
    await tester.pumpAndSettle();
    expect(find.text('Clear Data'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Settings sections fit a typical portrait screen in order', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(406, 904);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final controller = _testConnectionController();
    addTearDown(controller.dispose);
    final settings = MobileAppSettings();
    addTearDown(settings.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: SettingsScreen(controller: controller, settings: settings),
      ),
    );
    await tester.pumpAndSettle();

    final pairingY = tester
        .getTopLeft(find.byKey(const ValueKey('settings-pairing-heading')))
        .dy;
    final themeY = tester
        .getTopLeft(find.byKey(const ValueKey('dark-mode-switch')))
        .dy;
    final clearDataY = tester
        .getTopLeft(find.byKey(const ValueKey('settings-clear-data-heading')))
        .dy;
    final clearButtonBottom = tester
        .getBottomRight(find.byKey(const ValueKey('clear-data-action')))
        .dy;

    expect(pairingY, lessThan(themeY));
    expect(themeY, lessThan(clearDataY));
    expect(clearDataY, lessThan(clearButtonBottom));
    expect(clearButtonBottom, lessThanOrEqualTo(904));
    expect(tester.takeException(), isNull);
  });

  testWidgets('About guide scrolls with large text on a small viewport', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(320, 480);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final settings = MobileAppSettings();
    addTearDown(settings.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(1.8)),
          child: AboutScreen(settings: settings, onVisitGitHub: () async {}),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.byType(ListView), findsOneWidget);
    expect(find.text('About BookLedger Mobile'), findsOneWidget);
  });

  testWidgets('Clear Data cancel preserves all data', (
    WidgetTester tester,
  ) async {
    final store = _MemoryPairingStore()..pairing = _savedPairing();
    final controller = MobileConnectionController(
      store: store,
      transport: _FakeConnectionTransport(),
      discovery: _NoDesktopDiscovery(),
    );
    addTearDown(controller.dispose);
    final settings = MobileAppSettings();
    addTearDown(settings.dispose);
    var clearCalled = false;

    await tester.pumpWidget(
      MaterialApp(
        home: SettingsScreen(
          controller: controller,
          settings: settings,
          clearPendingPhotos: () async {
            clearCalled = true;
          },
        ),
      ),
    );
    await _scrollSettingsTo(
      tester,
      find.byKey(const ValueKey('clear-data-action')),
    );
    await tester.tap(find.byKey(const ValueKey('clear-data-action')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Clear Mobile Data?'), findsOneWidget);
    await tester.tap(find.text('Cancel'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(store.pairing, isNotNull);
    expect(clearCalled, isFalse);
  });

  testWidgets('Clear Data deletes only pending photos and forgets locally', (
    WidgetTester tester,
  ) async {
    final store = _MemoryPairingStore()..pairing = _savedPairing();
    final transport = _FakeConnectionTransport();
    final controller = MobileConnectionController(
      store: store,
      transport: transport,
      discovery: _NoDesktopDiscovery(),
    );
    addTearDown(controller.dispose);
    await controller.initialize();
    await tester.pump();
    await tester.pump();
    controller.didChangeAppLifecycleState(AppLifecycleState.paused);
    var photosCleared = false;
    final settings = MobileAppSettings();
    addTearDown(settings.dispose);
    const appSettingsChannel = MethodChannel(
      'com.bookledger.mobile/app_settings',
    );
    var savedTheme = 'dark';
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(appSettingsChannel, (call) async {
          if (call.method == 'getAppSettings') {
            return {'version': '1.2.3', 'theme': savedTheme};
          }
          if (call.method == 'setTheme') {
            savedTheme = call.arguments as String;
            return true;
          }
          return null;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(appSettingsChannel, null),
    );
    await settings.initialize();

    await tester.pumpWidget(
      MaterialApp(
        home: SettingsScreen(
          controller: controller,
          settings: settings,
          clearPendingPhotos: () async {
            photosCleared = true;
          },
        ),
      ),
    );
    await _scrollSettingsTo(
      tester,
      find.byKey(const ValueKey('clear-data-action')),
    );
    await tester.tap(find.byKey(const ValueKey('clear-data-action')));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('desktop BookLedger library will not be deleted.'),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const ValueKey('clear-data-confirm')));
    await tester.pumpAndSettle();

    expect(photosCleared, isTrue);
    expect(store.pairing, isNull);
    expect(controller.isPaired, isFalse);
    expect(controller.status, MobileConnectionStatus.notPaired);
    expect(settings.themeMode, ThemeMode.dark);
    expect(transport.unpairCalls, 0);
    expect(
      find.text(
        'Pending captures deleted and pairing forgotten on this phone.',
      ),
      findsOneWidget,
    );
    expect(find.byType(SnackBar), findsOneWidget);
    final restartedController = MobileConnectionController(
      store: store,
      transport: _FakeConnectionTransport(),
      discovery: _NoDesktopDiscovery(),
    );
    await restartedController.initialize();
    expect(restartedController.status, MobileConnectionStatus.notPaired);
    restartedController.dispose();
  });

  testWidgets('Clear Data reports photo deletion failure without success', (
    WidgetTester tester,
  ) async {
    final controller = MobileConnectionController(
      store: _MemoryPairingStore(),
      transport: _FakeConnectionTransport(),
      discovery: _NoDesktopDiscovery(),
    );
    addTearDown(controller.dispose);
    final settings = MobileAppSettings();
    addTearDown(settings.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: SettingsScreen(
          controller: controller,
          settings: settings,
          clearPendingPhotos: () async {
            throw const FileSystemException('Temporary storage unavailable.');
          },
        ),
      ),
    );
    await _scrollSettingsTo(
      tester,
      find.byKey(const ValueKey('clear-data-action')),
    );
    await tester.tap(find.byKey(const ValueKey('clear-data-action')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('clear-data-confirm')));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'Pairing was forgotten, but pending photos could not all be deleted. Retry Clear Data.',
      ),
      findsOneWidget,
    );
    expect(
      find.text(
        'Pending captures deleted and pairing forgotten on this phone.',
      ),
      findsNothing,
    );
    expect(controller.isPaired, isFalse);
  });

  testWidgets('Clear Data preserves photos when secure pairing clear fails', (
    WidgetTester tester,
  ) async {
    final store = _MemoryPairingStore()
      ..pairing = _savedPairing()
      ..failClear = true;
    final controller = MobileConnectionController(
      store: store,
      transport: _FakeConnectionTransport(),
      discovery: _NoDesktopDiscovery(),
    );
    addTearDown(controller.dispose);
    await controller.initialize();
    await tester.pump();
    await tester.pump();
    controller.didChangeAppLifecycleState(AppLifecycleState.paused);
    var photosCleared = false;
    final settings = MobileAppSettings();
    addTearDown(settings.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: SettingsScreen(
          controller: controller,
          settings: settings,
          clearPendingPhotos: () async {
            photosCleared = true;
          },
        ),
      ),
    );
    await _scrollSettingsTo(
      tester,
      find.byKey(const ValueKey('clear-data-action')),
    );
    await tester.tap(find.byKey(const ValueKey('clear-data-action')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('clear-data-confirm')));
    await tester.pumpAndSettle();

    expect(photosCleared, isFalse);
    expect(store.pairing, isNotNull);
    expect(
      find.text('Saved pairing could not be removed from secure storage.'),
      findsWidgets,
    );
  });

  testWidgets('Clear Data waits while a connection operation is active', (
    WidgetTester tester,
  ) async {
    final store = _MemoryPairingStore()..pairing = _savedPairing();
    final transport = _FakeConnectionTransport()
      ..validation = Completer<DesktopEndpoint?>();
    final controller = MobileConnectionController(
      store: store,
      transport: transport,
      discovery: _NoDesktopDiscovery(),
    );
    addTearDown(() {
      if (!transport.validation!.isCompleted) {
        transport.validation!.complete(null);
      }
      controller.dispose();
    });
    await controller.initialize();
    expect(controller.isBusy, isTrue);
    final settings = MobileAppSettings();
    addTearDown(settings.dispose);
    var photosCleared = false;

    await tester.pumpWidget(
      MaterialApp(
        home: SettingsScreen(
          controller: controller,
          settings: settings,
          clearPendingPhotos: () async {
            photosCleared = true;
          },
        ),
      ),
    );
    await _scrollSettingsTo(
      tester,
      find.byKey(const ValueKey('clear-data-action')),
    );
    await tester.tap(find.byKey(const ValueKey('clear-data-action')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('clear-data-confirm')));
    await tester.pumpAndSettle();

    expect(photosCleared, isFalse);
    expect(store.pairing, isNotNull);
    expect(
      find.text(
        'Wait for the current connection operation to finish, then retry.',
      ),
      findsOneWidget,
    );
  });

  testWidgets('active camera capture cannot be left before it is settled', (
    WidgetTester tester,
  ) async {
    final workflow = SingleEntryWorkflow()..chooseNoIsbn();
    addTearDown(workflow.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => CaptureScreen(
                    mode: CaptureMode.single,
                    workflow: workflow,
                  ),
                ),
              ),
              child: const Text('Home'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Home'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Single Entry'), findsOneWidget);

    await tester.pageBack();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('Single Entry'), findsOneWidget);
    expect(tester.takeException(), isNull);
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
