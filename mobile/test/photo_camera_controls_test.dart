import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:camera_platform_interface/camera_platform_interface.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/capture/bulk_capture_queue.dart';
import 'package:mobile/capture/framing_guides.dart';
import 'package:mobile/capture/photo_camera_view.dart';
import 'package:mobile/capture/single_entry_workflow.dart';
import 'package:mobile/main.dart';
import 'package:mobile/settings/mobile_app_settings.dart';

final _testPhotoBytes = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAFElEQVR4nGP8//8/AwMDEwMYQCkAORsDA3CXx5UAAAAASUVORK5CYII=',
);

Future<void> _pumpUntil(WidgetTester tester, bool Function() complete) async {
  await tester.runAsync(() async {
    final elapsed = Stopwatch()..start();
    while (!complete() && elapsed.elapsed < const Duration(seconds: 5)) {
      await tester.pump();
      // Let real file/image IO finish between frames on the fake clock.
      await Future<void>(() {});
    }
  });
  expect(complete(), isTrue, reason: 'Capture/image operation did not finish');
}

class _FakeCameraPlatform extends CameraPlatform {
  _FakeCameraPlatform({
    this.minimumZoom = 1,
    this.maximumZoom = 4,
    this.zoomCapabilityAvailable = true,
    this.torchSupported = true,
  });

  final double minimumZoom;
  final double maximumZoom;
  final bool zoomCapabilityAvailable;
  final bool torchSupported;
  final List<double> zoomLevels = [];
  final List<FlashMode> flashModes = [];
  int disposedCameras = 0;
  int captureCalls = 0;
  int activeZoomCalls = 0;
  int maximumConcurrentZoomCalls = 0;
  Completer<void>? zoomGate;
  String? capturePath;

  @override
  Future<List<CameraDescription>> availableCameras() async => const [
    CameraDescription(
      name: 'test-back-camera',
      lensDirection: CameraLensDirection.back,
      sensorOrientation: 90,
    ),
  ];

  @override
  Future<int> createCameraWithSettings(
    CameraDescription cameraDescription,
    MediaSettings mediaSettings,
  ) async => 1;

  @override
  Future<void> initializeCamera(
    int cameraId, {
    ImageFormatGroup imageFormatGroup = ImageFormatGroup.unknown,
  }) async {}

  @override
  Stream<CameraInitializedEvent> onCameraInitialized(int cameraId) =>
      Stream.value(
        CameraInitializedEvent(
          cameraId,
          1920,
          1080,
          ExposureMode.auto,
          true,
          FocusMode.auto,
          true,
        ),
      );

  @override
  Stream<CameraErrorEvent> onCameraError(int cameraId) =>
      Stream.value(CameraErrorEvent(cameraId, ''));

  @override
  Stream<DeviceOrientationChangedEvent> onDeviceOrientationChanged() =>
      Stream.value(
        const DeviceOrientationChangedEvent(DeviceOrientation.portraitUp),
      );

  @override
  Future<double> getMinZoomLevel(int cameraId) async {
    if (!zoomCapabilityAvailable) {
      throw CameraException('zoomUnavailable', 'Zoom limits unavailable.');
    }
    return minimumZoom;
  }

  @override
  Future<double> getMaxZoomLevel(int cameraId) async {
    if (!zoomCapabilityAvailable) {
      throw CameraException('zoomUnavailable', 'Zoom limits unavailable.');
    }
    return maximumZoom;
  }

  @override
  Future<void> setZoomLevel(int cameraId, double zoom) async {
    activeZoomCalls++;
    if (activeZoomCalls > maximumConcurrentZoomCalls) {
      maximumConcurrentZoomCalls = activeZoomCalls;
    }
    try {
      final gate = zoomGate;
      if (gate != null && !gate.isCompleted) await gate.future;
      zoomLevels.add(zoom);
    } finally {
      activeZoomCalls--;
    }
  }

  @override
  Future<void> setFlashMode(int cameraId, FlashMode mode) async {
    if (mode == FlashMode.torch && !torchSupported) {
      throw PlatformException(code: 'torchUnavailable');
    }
    flashModes.add(mode);
  }

  @override
  Widget buildPreview(int cameraId) => const ColoredBox(color: Colors.black);

  @override
  Future<XFile> takePicture(int cameraId) async {
    captureCalls++;
    return XFile(capturePath!);
  }

  @override
  Future<void> dispose(int cameraId) async {
    disposedCameras++;
  }
}

Future<_FakeCameraPlatform> _installFakeCamera(
  WidgetTester tester, {
  double minimumZoom = 1,
  double maximumZoom = 4,
  bool zoomCapabilityAvailable = true,
  bool torchSupported = true,
}) async {
  final oldCameraPlatform = CameraPlatform.instance;
  final camera = _FakeCameraPlatform(
    minimumZoom: minimumZoom,
    maximumZoom: maximumZoom,
    zoomCapabilityAvailable: zoomCapabilityAvailable,
    torchSupported: torchSupported,
  );
  CameraPlatform.instance = camera;
  addTearDown(() => CameraPlatform.instance = oldCameraPlatform);

  final directory = (await tester.runAsync(
    () => Directory.systemTemp.createTemp('bookledger-camera-controls-'),
  ))!;
  addTearDown(() async {
    await tester.runAsync(() => directory.delete(recursive: true));
  });
  final sourcePhoto = File('${directory.path}/camera-source.jpg');
  await tester.runAsync(() => sourcePhoto.writeAsBytes(_testPhotoBytes));
  camera.capturePath = sourcePhoto.path;

  const pathProvider = MethodChannel('plugins.flutter.io/path_provider');
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(pathProvider, (call) async {
        if (call.method == 'getTemporaryDirectory') return directory.path;
        return null;
      });
  addTearDown(
    () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(pathProvider, null),
  );
  return camera;
}

Future<void> _pumpPhotoCamera(
  WidgetTester tester, {
  double preferredZoom = 1.0,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: PhotoCameraView(
          captureRequestId: 0,
          guideMode: FramingGuideMode.lFrame,
          onGuideModeChanged: (_) {},
          preferredZoom: preferredZoom,
          onZoomChanged: (_) {},
          onCaptured: (_) async {},
          onCancel: () {},
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('failed Retake restores the retained photo and readiness', (
    tester,
  ) async {
    final camera = await _installFakeCamera(tester);
    final workflow = SingleEntryWorkflow()..chooseNoIsbn();
    await workflow.photoCaptured('retained.jpg');
    final id = workflow.captureId;
    workflow.beginPhotoCapture();
    camera.capturePath = null;
    await tester.pumpWidget(
      MaterialApp(
        home: CaptureScreen(mode: CaptureMode.single, workflow: workflow),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ElevatedButton, 'Take Photo'));
    await tester.pumpAndSettle();
    expect(workflow.isCaptureReady, isTrue);
    expect(workflow.photoCameraActive, isFalse);
    expect(workflow.photoPath, 'retained.jpg');
    expect(workflow.captureId, id);
    expect(find.byType(PhotoCameraView), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
    workflow.dispose();
  });

  testWidgets('torch starts off, toggles, and turns off at disposal', (
    WidgetTester tester,
  ) async {
    final camera = await _installFakeCamera(tester);
    await _pumpPhotoCamera(tester);

    expect(camera.flashModes.first, FlashMode.off);
    expect(find.byTooltip('Torch: off'), findsOneWidget);
    await tester.tap(find.byTooltip('Torch: off'));
    await tester.pumpAndSettle();
    expect(camera.flashModes.last, FlashMode.torch);
    expect(find.byTooltip('Torch: on'), findsOneWidget);

    await tester.tap(find.byTooltip('Torch: on'));
    await tester.pumpAndSettle();
    expect(camera.flashModes.last, FlashMode.off);
    expect(find.byTooltip('Torch: off'), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    expect(camera.flashModes.last, FlashMode.off);
    expect(camera.disposedCameras, 1);
  });

  testWidgets('torch and guide icons are smaller but keep full touch targets', (
    WidgetTester tester,
  ) async {
    await _installFakeCamera(tester);
    await _pumpPhotoCamera(tester);

    for (final tooltip in ['Torch: off', 'Guide: L-frame']) {
      final buttonFinder = find.ancestor(
        of: find.byTooltip(tooltip),
        matching: find.byType(IconButton),
      );
      final button = tester.widget<IconButton>(buttonFinder);
      expect(button.iconSize, 18);
      expect(button.color!.a, closeTo(0.8, 0.001));
      expect(tester.getSize(buttonFinder), const Size(48, 48));
    }
  });

  testWidgets('unsupported torch becomes a disabled control without failing', (
    WidgetTester tester,
  ) async {
    await _installFakeCamera(tester, torchSupported: false);
    await _pumpPhotoCamera(tester);

    await tester.tap(find.byTooltip('Torch: off'));
    await tester.pumpAndSettle();

    final button = tester.widget<IconButton>(
      find.ancestor(
        of: find.byTooltip('Torch unavailable'),
        matching: find.byType(IconButton),
      ),
    );
    expect(button.onPressed, isNull);
    expect(tester.takeException(), isNull);
  });

  testWidgets('zoom uses discrete half-step camera-supported values', (
    WidgetTester tester,
  ) async {
    final camera = await _installFakeCamera(
      tester,
      minimumZoom: 0.5,
      maximumZoom: 8,
    );
    await _pumpPhotoCamera(tester);

    final slider = tester.widget<Slider>(
      find.byKey(const ValueKey('camera-zoom-slider')),
    );
    expect(slider.min, 0.5);
    expect(slider.max, 3.0);
    expect(slider.divisions, 5);
    expect(slider.value, 1.0);
    expect(find.text('1.0×'), findsOneWidget);

    slider.onChanged!(1.5);
    await tester.pumpAndSettle();
    expect(camera.zoomLevels.last, 1.5);
    expect(find.text('1.5×'), findsOneWidget);
  });

  testWidgets('zoom omits unsupported wide and high stops', (
    WidgetTester tester,
  ) async {
    await _installFakeCamera(tester, minimumZoom: 1, maximumZoom: 2.2);
    await _pumpPhotoCamera(tester);

    final slider = tester.widget<Slider>(
      find.byKey(const ValueKey('camera-zoom-slider')),
    );
    expect(slider.min, 1.0);
    expect(slider.max, 2.0);
    expect(slider.divisions, 2);
    expect(find.text('1.0×'), findsOneWidget);
  });

  testWidgets('saved zoom falls back without overwriting unsupported choice', (
    WidgetTester tester,
  ) async {
    final camera = await _installFakeCamera(
      tester,
      minimumZoom: 1,
      maximumZoom: 2,
    );
    await _pumpPhotoCamera(tester, preferredZoom: 2.5);

    expect(camera.zoomLevels, [2.0]);
    expect(find.text('2.0×'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('fixed zoom range shows its value without an invalid slider', (
    WidgetTester tester,
  ) async {
    await _installFakeCamera(tester, minimumZoom: 1, maximumZoom: 1);
    await _pumpPhotoCamera(tester);

    expect(find.byKey(const ValueKey('camera-zoom-slider')), findsNothing);
    expect(find.text('1.0×'), findsOneWidget);
    expect(find.text('Fixed'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('rapid zoom updates are coalesced to one in-flight command', (
    WidgetTester tester,
  ) async {
    final camera = await _installFakeCamera(tester);
    await _pumpPhotoCamera(tester);
    camera.zoomLevels.clear();
    camera.zoomGate = Completer<void>();
    final slider = tester.widget<Slider>(
      find.byKey(const ValueKey('camera-zoom-slider')),
    );

    slider.onChanged!(2);
    await tester.pump();
    slider.onChanged!(2.9);
    await tester.pump();
    expect(camera.maximumConcurrentZoomCalls, 1);
    expect(camera.zoomLevels, isEmpty);

    camera.zoomGate!.complete();
    await tester.pumpAndSettle();
    expect(camera.zoomLevels, [2, 3]);
    expect(camera.maximumConcurrentZoomCalls, 1);
  });

  testWidgets('unavailable discrete zoom range never sends a camera command', (
    WidgetTester tester,
  ) async {
    final camera = await _installFakeCamera(
      tester,
      minimumZoom: 1.1,
      maximumZoom: 1.4,
    );
    await _pumpPhotoCamera(tester);

    expect(find.byKey(const ValueKey('camera-zoom-slider')), findsNothing);
    expect(find.text('Unavailable'), findsOneWidget);
    expect(camera.zoomLevels, isEmpty);
    expect(tester.takeException(), isNull);
  });

  testWidgets('zoom capability lookup failure disables the control safely', (
    WidgetTester tester,
  ) async {
    final camera = await _installFakeCamera(
      tester,
      zoomCapabilityAvailable: false,
    );
    await _pumpPhotoCamera(tester);

    expect(find.byKey(const ValueKey('camera-zoom-slider')), findsNothing);
    expect(find.text('Unavailable'), findsOneWidget);
    expect(camera.zoomLevels, isEmpty);
    expect(tester.takeException(), isNull);
  });

  testWidgets('pause disposes the camera and resume starts with torch off', (
    WidgetTester tester,
  ) async {
    final camera = await _installFakeCamera(tester);
    await _pumpPhotoCamera(tester);
    await tester.tap(find.byTooltip('Torch: off'));
    await tester.pumpAndSettle();
    expect(camera.flashModes.last, FlashMode.torch);

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pumpAndSettle();
    expect(camera.flashModes.last, FlashMode.off);
    expect(camera.disposedCameras, 1);

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();
    expect(find.byTooltip('Torch: off'), findsOneWidget);
    expect(camera.flashModes.last, FlashMode.off);
    expect(tester.takeException(), isNull);
  });

  testWidgets('retake restores guide mode and captured bytes unchanged', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(406, 904);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final camera = await _installFakeCamera(tester);
    final workflow = SingleEntryWorkflow()..chooseNoIsbn();
    var savedGuideMode = 'lFrame';
    var savedZoom = 1.0;
    const appSettingsChannel = MethodChannel(
      'com.bookledger.mobile/app_settings',
    );
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(appSettingsChannel, (call) async {
          if (call.method == 'getAppSettings') {
            return {
              'version': '1.0.0',
              'theme': 'default',
              'cameraGuideMode': savedGuideMode,
              'cameraZoom': savedZoom,
            };
          }
          if (call.method == 'setCameraPreferences') {
            final values = Map<Object?, Object?>.from(call.arguments as Map);
            savedGuideMode = values['guideMode']! as String;
            savedZoom = values['zoom']! as double;
            return true;
          }
          return null;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(appSettingsChannel, null),
    );
    final settings = MobileAppSettings();
    addTearDown(settings.dispose);
    await settings.initialize();
    const permissionChannel = MethodChannel(
      'flutter.baseflow.com/permissions/methods',
    );
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(permissionChannel, (_) async => 1);
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(permissionChannel, null),
    );
    addTearDown(workflow.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: CaptureScreen(
          mode: CaptureMode.single,
          workflow: workflow,
          appSettings: settings,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Guide: L-frame'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Guide: 3×3 grid'));
    await tester.pumpAndSettle();
    expect(find.byTooltip('Guide: 4×4 grid'), findsOneWidget);
    final slider = tester.widget<Slider>(
      find.byKey(const ValueKey('camera-zoom-slider')),
    );
    slider.onChanged!(2.5);
    await tester.pumpAndSettle();
    expect(find.text('2.5×'), findsOneWidget);
    expect(savedGuideMode, 'grid4x4');
    expect(savedZoom, 2.5);
    await tester.tap(find.byTooltip('Torch: off'));
    await tester.pumpAndSettle();
    expect(camera.flashModes.last, FlashMode.torch);

    await tester.tap(find.widgetWithText(ElevatedButton, 'Take Photo'));
    await _pumpUntil(tester, () => workflow.isCaptureReady);
    await tester.pump();
    await tester.pumpAndSettle();
    expect(camera.captureCalls, 1);
    expect(
      find.text('The photo could not be captured. Please try again.'),
      findsNothing,
    );
    final photoPath = workflow.photoPath!;
    await _pumpUntil(
      tester,
      () => tester
          .widgetList<RawImage>(find.byType(RawImage))
          .any((image) => image.image != null),
    );
    expect(
      await tester.runAsync(() => File(photoPath).readAsBytes()),
      _testPhotoBytes,
    );
    expect(find.byType(PhotoCameraView), findsNothing);
    expect(find.byTooltip('Guide: 4×4 grid'), findsNothing);

    await tester.tap(find.widgetWithText(ElevatedButton, 'Retake'));
    await tester.pumpAndSettle();
    expect(find.byType(PhotoCameraView), findsOneWidget);
    expect(find.byTooltip('Guide: 4×4 grid'), findsOneWidget);
    expect(find.byTooltip('Torch: off'), findsOneWidget);
    expect(find.text('2.5×'), findsOneWidget);
    expect(savedGuideMode, 'grid4x4');
    expect(savedZoom, 2.5);
    expect(camera.flashModes.last, FlashMode.off);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await FileImage(File(photoPath)).evict();
    expect(camera.disposedCameras, 2);
  });

  testWidgets('Bulk Entry uses the same live camera controls', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(406, 904);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await _installFakeCamera(tester);
    final workflow = SingleEntryWorkflow()..chooseNoIsbn();
    final queue = BulkCaptureQueue(capacity: 5);
    addTearDown(() {
      workflow.dispose();
      queue.dispose();
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
    await tester.pumpAndSettle();

    expect(find.byType(PhotoCameraView), findsOneWidget);
    expect(find.byTooltip('Torch: off'), findsOneWidget);
    expect(find.byTooltip('Guide: L-frame'), findsOneWidget);
    expect(find.byKey(const ValueKey('camera-zoom-slider')), findsOneWidget);
  });

  testWidgets('saved guide preference follows Single and Bulk sessions', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(406, 904);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await _installFakeCamera(tester);

    var savedGuideMode = 'lFrame';
    var savedZoom = 1.0;
    const channel = MethodChannel('com.bookledger.mobile/app_settings');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          if (call.method == 'getAppSettings') {
            return {
              'version': '1.0.0',
              'theme': 'default',
              'cameraGuideMode': savedGuideMode,
              'cameraZoom': savedZoom,
            };
          }
          if (call.method == 'setCameraPreferences') {
            final values = Map<Object?, Object?>.from(call.arguments as Map);
            savedGuideMode = values['guideMode']! as String;
            savedZoom = values['zoom']! as double;
            return true;
          }
          return null;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, null),
    );
    final settings = MobileAppSettings();
    addTearDown(settings.dispose);
    await settings.initialize();

    final singleWorkflow = SingleEntryWorkflow()..chooseNoIsbn();
    addTearDown(singleWorkflow.dispose);
    await tester.pumpWidget(
      MaterialApp(
        home: CaptureScreen(
          mode: CaptureMode.single,
          workflow: singleWorkflow,
          appSettings: settings,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Guide: L-frame'));
    await tester.pumpAndSettle();
    expect(savedGuideMode, 'grid3x3');
    await singleWorkflow.clear();
    expect(savedGuideMode, 'grid3x3');
    expect(settings.cameraGuideMode, 'grid3x3');

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    final bulkWorkflow = SingleEntryWorkflow()..chooseNoIsbn();
    final queue = BulkCaptureQueue(capacity: 5);
    addTearDown(() {
      bulkWorkflow.dispose();
      queue.dispose();
    });
    await tester.pumpWidget(
      MaterialApp(
        home: CaptureScreen(
          mode: CaptureMode.bulk,
          queueTarget: 5,
          bulkQueue: queue,
          workflow: bulkWorkflow,
          appSettings: settings,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byTooltip('Guide: 3×3 grid'), findsOneWidget);
  });
}
