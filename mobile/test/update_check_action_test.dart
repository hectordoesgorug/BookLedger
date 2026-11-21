import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/settings/mobile_app_settings.dart';
import 'package:mobile/updates/update_check_action.dart';
import 'package:mobile/updates/update_service.dart';

import 'update_service_test.dart' show release;

void main() {
  const channel = MethodChannel('com.bookledger.mobile/app_settings');
  testWidgets(
    'explicit check shows busy state and preserves preferences and capture files',
    (tester) async {
      final methods = <String>[];
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            methods.add(call.method);
            return {
              'version': '1.1.0',
              'versionCode': 2,
              'packageName': 'com.bookledger.mobile',
              'releaseBuild': true,
              'theme': 'dark',
            };
          });
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(channel, null),
      );
      final settings = MobileAppSettings();
      addTearDown(settings.dispose);
      final folder = Directory.systemTemp.createTempSync('update-read-only-');
      addTearDown(() => folder.delete(recursive: true));
      final photo = File('${folder.path}/pending.jpg');
      photo.writeAsBytesSync([1, 2, 3]);
      final pending = Completer<Object?>();
      var calls = 0;
      final service = UpdateService(
        fetchRelease: () {
          calls++;
          return pending.future;
        },
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: UpdateCheckAction(settings: settings, service: service),
          ),
        ),
      );
      expect(calls, 0);
      await tester.tap(find.text('Check for Updates'));
      await tester.pump();
      expect(find.text('Checking…'), findsOneWidget);
      expect(
        tester
            .widget<TextButton>(find.byKey(const ValueKey('check-for-updates')))
            .onPressed,
        isNull,
      );
      pending.complete(release());
      await tester.pumpAndSettle();
      expect(find.text('Update Available'), findsOneWidget);
      expect(find.text('Installed: 1.1.0 (code 2)'), findsOneWidget);
      expect(find.text('Available: 1.2.0'), findsOneWidget);
      expect(find.text('Release notes'), findsOneWidget);
      expect(find.text('Download & Verify'), findsOneWidget);
      expect(settings.themeMode, ThemeMode.dark);
      expect(methods, ['getAppSettings']);
      expect(photo.readAsBytesSync(), [1, 2, 3]);
    },
  );

  testWidgets(
    'offline errors permit another check and disposed checks do not reopen a dialog',
    (tester) async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(
            channel,
            (call) async => {'version': '1.1.0'},
          );
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(channel, null),
      );
      final settings = MobileAppSettings();
      addTearDown(settings.dispose);
      await settings.initialize();
      final service = UpdateService(
        fetchRelease: () async => throw const SocketException('offline'),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: UpdateCheckAction(settings: settings, service: service),
          ),
        ),
      );
      await tester.tap(find.text('Check for Updates'));
      await tester.pumpAndSettle();
      expect(find.text('Unable to Check'), findsOneWidget);
      await tester.tap(find.text('Close'));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<TextButton>(find.byKey(const ValueKey('check-for-updates')))
            .onPressed,
        isNotNull,
      );
      final pending = Completer<Object?>();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: UpdateCheckAction(
              key: const ValueKey('pending'),
              settings: settings,
              service: UpdateService(fetchRelease: () => pending.future),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Check for Updates'));
      await tester.pump();
      await tester.pumpWidget(const SizedBox());
      pending.complete(release());
      await tester.pumpAndSettle();
      expect(find.byType(AlertDialog), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
}
