import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/settings/mobile_app_settings.dart';
import 'package:mobile/settings/settings_screen.dart';

void main() {
  const channel = MethodChannel('com.bookledger.mobile/app_settings');

  testWidgets(
    'Default is initial and Dark persists after a new settings load',
    (WidgetTester tester) async {
      var savedTheme = 'default';
      var savedGuideMode = 'lFrame';
      var savedZoom = 1.0;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            if (call.method == 'getAppSettings') {
              return {
                'version': '1.0.0',
                'theme': savedTheme,
                'cameraGuideMode': savedGuideMode,
                'cameraZoom': savedZoom,
              };
            }
            if (call.method == 'setTheme') {
              savedTheme = call.arguments as String;
              return true;
            }
            if (call.method == 'setCameraPreferences') {
              final values = call.arguments as Map<Object?, Object?>;
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
      expect(settings.themeMode, ThemeMode.light);
      expect(settings.version, '1.0.0');
      expect(settings.cameraGuideMode, 'lFrame');
      expect(settings.cameraZoom, 1.0);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: DarkModeSwitch(settings: settings)),
        ),
      );
      expect(tester.widget<Switch>(find.byType(Switch)).value, isFalse);
      await tester.tap(find.byType(Switch));
      await tester.pumpAndSettle();
      expect(settings.themeMode, ThemeMode.dark);
      expect(savedTheme, 'dark');

      final restartedSettings = MobileAppSettings();
      addTearDown(restartedSettings.dispose);
      await restartedSettings.initialize();
      expect(restartedSettings.themeMode, ThemeMode.dark);
      expect(restartedSettings.version, '1.0.0');
      expect(restartedSettings.cameraGuideMode, 'lFrame');
      expect(restartedSettings.cameraZoom, 1.0);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: DarkModeSwitch(settings: restartedSettings)),
        ),
      );
      expect(tester.widget<Switch>(find.byType(Switch)).value, isTrue);
    },
  );

  test(
    'camera preferences persist and reload with existing app settings',
    () async {
      var savedGuideMode = 'lFrame';
      var savedZoom = 1.0;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            if (call.method == 'getAppSettings') {
              return {
                'version': '1.0.0',
                'theme': 'dark',
                'cameraGuideMode': savedGuideMode,
                'cameraZoom': savedZoom,
              };
            }
            if (call.method == 'setCameraPreferences') {
              final values = call.arguments as Map<Object?, Object?>;
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
      for (final mode in ['lFrame', 'grid3x3', 'grid4x4', 'off']) {
        expect(await settings.setCameraGuideMode(mode), isTrue);
        expect(savedGuideMode, mode);
      }
      expect(await settings.setCameraZoom(2.5), isTrue);

      final relaunchedSettings = MobileAppSettings();
      addTearDown(relaunchedSettings.dispose);
      await relaunchedSettings.initialize();
      expect(relaunchedSettings.cameraGuideMode, 'off');
      expect(relaunchedSettings.cameraZoom, 2.5);
      expect(relaunchedSettings.themeMode, ThemeMode.dark);
      expect(relaunchedSettings.version, '1.0.0');
    },
  );

  test(
    'invalid stored and requested camera preferences use safe defaults',
    () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            if (call.method == 'getAppSettings') {
              return {
                'version': '1.0.0',
                'theme': 'default',
                'cameraGuideMode': 'broken',
                'cameraZoom': 0.7,
              };
            }
            return false;
          });
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(channel, null),
      );

      final settings = MobileAppSettings();
      addTearDown(settings.dispose);
      await settings.initialize();
      expect(settings.cameraGuideMode, 'lFrame');
      expect(settings.cameraZoom, 1.0);
      expect(await settings.setCameraGuideMode('invalid'), isFalse);
      expect(await settings.setCameraZoom(0.7), isFalse);
    },
  );

  test(
    'camera preference writes serialize and retain the latest combination',
    () async {
      final firstWrite = Completer<void>();
      final writes = <Map<Object?, Object?>>[];
      var savedGuideMode = 'lFrame';
      var savedZoom = 1.0;
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
              writes.add(values);
              if (writes.length == 1) await firstWrite.future;
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
      final guideWrite = settings.setCameraGuideMode('grid3x3');
      final zoomWrite = settings.setCameraZoom(2.0);
      await Future<void>.delayed(Duration.zero);
      expect(writes, hasLength(1));
      firstWrite.complete();
      expect(await guideWrite, isTrue);
      expect(await zoomWrite, isTrue);
      expect(writes, hasLength(2));
      expect(savedGuideMode, 'grid3x3');
      expect(savedZoom, 2.0);
    },
  );

  test('camera preference save failure is returned to the caller', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          if (call.method == 'getAppSettings') {
            return {'version': '1.0.0', 'theme': 'default'};
          }
          if (call.method == 'setCameraPreferences') return false;
          return null;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, null),
    );

    final settings = MobileAppSettings();
    addTearDown(settings.dispose);
    await settings.initialize();

    expect(await settings.setCameraGuideMode('off'), isFalse);
    expect(settings.cameraGuideMode, 'off');
  });

  testWidgets('theme save failure leaves current theme unchanged', (
    WidgetTester tester,
  ) async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          if (call.method == 'getAppSettings') {
            return {'version': '1.0.0', 'theme': 'default'};
          }
          if (call.method == 'setTheme') return false;
          return null;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, null),
    );

    final settings = MobileAppSettings();
    addTearDown(settings.dispose);
    await settings.initialize();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: DarkModeSwitch(settings: settings)),
      ),
    );
    await tester.tap(find.byType(Switch));
    await tester.pumpAndSettle();

    expect(settings.themeMode, ThemeMode.light);
    expect(
      find.text('The theme preference could not be saved.'),
      findsOneWidget,
    );
  });
}
