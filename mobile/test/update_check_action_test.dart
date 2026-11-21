import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/settings/mobile_app_settings.dart';
import 'package:mobile/updates/update_check_action.dart';
import 'package:mobile/updates/update_installer.dart';
import 'package:mobile/updates/update_service.dart';

import 'update_service_test.dart' show release;

const _settingsChannel = MethodChannel('com.bookledger.mobile/app_settings');

void main() {
  testWidgets(
    'explicit check shows busy state and preserves preferences and capture files',
    (tester) async {
      final methods = <String>[];
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(_settingsChannel, (call) async {
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
            .setMockMethodCallHandler(_settingsChannel, null),
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

  for (final candidate in [
    const UpdateApkEligibility(packageName: 'com.other.app', versionCode: 3),
    const UpdateApkEligibility(
      packageName: 'com.bookledger.mobile',
      versionCode: 2,
    ),
  ]) {
    testWidgets(
      'install action rejects ${candidate.packageName} code ${candidate.versionCode}',
      (tester) async {
        final settings = await _releaseSettings();
        addTearDown(settings.dispose);
        final download = _fixtureDownload();
        addTearDown(() => download.file.parent.delete(recursive: true));
        final installer = _FakeInstaller(eligibility: candidate);
        await _openUpdateDialog(tester, settings, installer, download);
        expect(find.byKey(const ValueKey('install-update')), findsNothing);
        expect(
          find.textContaining('Android rejected the APK for installation.'),
          findsOneWidget,
        );
        expect(installer.installCalls, 0);
      },
    );
  }

  testWidgets('verification failure never exposes Install Update', (
    tester,
  ) async {
    final settings = await _releaseSettings();
    addTearDown(settings.dispose);
    final download = _fixtureDownload();
    addTearDown(() => download.file.parent.delete(recursive: true));
    final installer = _FakeInstaller(
      inspectionError: const FormatException('corrupt APK'),
    );
    await _openUpdateDialog(tester, settings, installer, download);
    expect(find.byKey(const ValueKey('install-update')), findsNothing);
    expect(find.textContaining('corrupt APK'), findsOneWidget);
    expect(installer.installCalls, 0);
  });

  testWidgets(
    'install confirmation warns about captures and cancellation preserves them',
    (tester) async {
      final settings = await _releaseSettings();
      addTearDown(settings.dispose);
      final download = _fixtureDownload();
      addTearDown(() => download.file.parent.delete(recursive: true));
      final pending = File('${download.file.parent.path}/pending.jpg')
        ..writeAsBytesSync([1, 2, 3]);
      final installer = _FakeInstaller(
        eligibility: const UpdateApkEligibility(
          packageName: 'com.bookledger.mobile',
          versionCode: 3,
        ),
        status: 'canceled',
      );
      await _openUpdateDialog(tester, settings, installer, download);
      expect(find.byKey(const ValueKey('install-update')), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('install-update')));
      await tester.pumpAndSettle();
      expect(
        find.textContaining(
          'Any unsent captures may be lost if the update closes BookLedger.',
        ),
        findsOneWidget,
      );
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(installer.installCalls, 0);
      expect(pending.readAsBytesSync(), [1, 2, 3]);

      await tester.tap(find.byKey(const ValueKey('install-update')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('confirm-install-update')));
      await tester.pumpAndSettle();
      expect(installer.installCalls, 1);
      expect(find.textContaining('Installation was canceled.'), findsOneWidget);
      expect(pending.readAsBytesSync(), [1, 2, 3]);
    },
  );

  testWidgets(
    'installer unavailable is reported without claiming installation',
    (tester) async {
      final settings = await _releaseSettings();
      addTearDown(settings.dispose);
      final download = _fixtureDownload();
      addTearDown(() => download.file.parent.delete(recursive: true));
      final installer = _FakeInstaller(status: 'unavailable');
      await _openUpdateDialog(tester, settings, installer, download);
      await tester.tap(find.byKey(const ValueKey('install-update')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('confirm-install-update')));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Android could not open the package installer.'),
        findsOneWidget,
      );
      expect(find.textContaining('confirmed'), findsNothing);
    },
  );

  testWidgets(
    'leaving while installer handoff is pending does not update disposed UI',
    (tester) async {
      final settings = await _releaseSettings();
      addTearDown(settings.dispose);
      final download = _fixtureDownload();
      addTearDown(() => download.file.parent.delete(recursive: true));
      final pendingInstall = Completer<String>();
      final installer = _FakeInstaller(installCompleter: pendingInstall);
      await _openUpdateDialog(tester, settings, installer, download);
      await tester.tap(find.byKey(const ValueKey('install-update')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('confirm-install-update')));
      await tester.pumpAndSettle();
      expect(installer.installCalls, 1);
      await tester.pumpWidget(const SizedBox());
      pendingInstall.complete('installed');
      await tester.pump();
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'permission and installer outcomes are shown without claiming success',
    (tester) async {
      final settings = await _releaseSettings();
      addTearDown(settings.dispose);
      final download = _fixtureDownload();
      addTearDown(() => download.file.parent.delete(recursive: true));
      final installer = _FakeInstaller(
        eligibility: const UpdateApkEligibility(
          packageName: 'com.bookledger.mobile',
          versionCode: 3,
        ),
        status: 'permissionRequired',
      );
      await _openUpdateDialog(tester, settings, installer, download);
      await tester.tap(find.byKey(const ValueKey('install-update')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('confirm-install-update')));
      await tester.pumpAndSettle();
      expect(
        find.textContaining(
          'Allow BookLedger to install updates in Android settings',
        ),
        findsOneWidget,
      );
      expect(find.textContaining('installed.'), findsNothing);
    },
  );

  testWidgets(
    'offline errors permit another check and disposed checks do not reopen a dialog',
    (tester) async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(
            _settingsChannel,
            (call) async => {'version': '1.1.0'},
          );
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(_settingsChannel, null),
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

Future<MobileAppSettings> _releaseSettings() async {
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(
        _settingsChannel,
        (call) async => {
          'version': '1.1.0',
          'versionCode': 2,
          'packageName': 'com.bookledger.mobile',
          'releaseBuild': true,
        },
      );
  addTearDown(
    () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(_settingsChannel, null),
  );
  final settings = MobileAppSettings();
  await settings.initialize();
  return settings;
}

VerifiedUpdateDownload _fixtureDownload() {
  final folder = Directory.systemTemp.createTempSync('update-install-test-');
  final file = File('${folder.path}/BookLedger-v1.2.0-Android.apk')
    ..writeAsBytesSync([0x50, 0x4b, 1, 2]);
  return VerifiedUpdateDownload(file, 'a' * 64);
}

Future<void> _openUpdateDialog(
  WidgetTester tester,
  MobileAppSettings settings,
  _FakeInstaller installer,
  VerifiedUpdateDownload download,
) async {
  final service = _FixtureUpdateService(download);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: UpdateCheckAction(
          settings: settings,
          service: service,
          installer: installer,
        ),
      ),
    ),
  );
  await tester.tap(find.text('Check for Updates'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Download & Verify'));
  await tester.pumpAndSettle();
}

class _FixtureUpdateService extends UpdateService {
  _FixtureUpdateService(this.fixture)
    : super(fetchRelease: () async => release());

  final VerifiedUpdateDownload fixture;

  @override
  Future<VerifiedUpdateDownload> download(
    UpdateResult result, {
    required bool supported,
    required UpdateDownloadCancellation cancellation,
    void Function(String state, int bytes, int? total)? onProgress,
  }) async => fixture;
}

class _FakeInstaller implements UpdateInstaller {
  _FakeInstaller({
    this.eligibility = const UpdateApkEligibility(
      packageName: 'com.bookledger.mobile',
      versionCode: 3,
    ),
    this.inspectionError,
    this.status = 'notConfirmed',
    this.installCompleter,
  });

  final UpdateApkEligibility eligibility;
  final Object? inspectionError;
  final String status;
  final Completer<String>? installCompleter;
  var installCalls = 0;

  @override
  Future<UpdateApkEligibility> inspect(
    VerifiedUpdateDownload download,
    int installedVersionCode,
  ) async {
    if (inspectionError != null) throw inspectionError!;
    return eligibility;
  }

  @override
  Future<String> install(VerifiedUpdateDownload download, int versionCode) {
    installCalls++;
    return installCompleter?.future ?? Future<String>.value(status);
  }
}
