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
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            if (call.method == 'getAppSettings') {
              return {'version': '1.0.0', 'theme': savedTheme};
            }
            if (call.method == 'setTheme') {
              savedTheme = call.arguments as String;
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

      await tester.pumpWidget(
        MaterialApp(home: ThemeSelectionScreen(settings: settings)),
      );
      await tester.tap(find.text('Dark'));
      await tester.pumpAndSettle();
      expect(settings.themeMode, ThemeMode.dark);
      expect(savedTheme, 'dark');

      final restartedSettings = MobileAppSettings();
      addTearDown(restartedSettings.dispose);
      await restartedSettings.initialize();
      expect(restartedSettings.themeMode, ThemeMode.dark);
      expect(restartedSettings.version, '1.0.0');
    },
  );

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
      MaterialApp(home: ThemeSelectionScreen(settings: settings)),
    );
    await tester.tap(find.text('Dark'));
    await tester.pumpAndSettle();

    expect(settings.themeMode, ThemeMode.light);
    expect(
      find.text('The theme preference could not be saved.'),
      findsOneWidget,
    );
  });
}
