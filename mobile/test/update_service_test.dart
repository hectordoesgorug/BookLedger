import 'dart:io';
import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/updates/update_service.dart';

Map<String, Object?> release([String tag = 'v1.2.0']) => {
  'tag_name': tag,
  'draft': false,
  'prerelease': false,
  'html_url': '$releaseRepository/releases/tag/$tag',
  'body': 'Release notes',
  'assets': [
    for (final name in ['BookLedger-$tag-Android.apk', 'SHA256SUMS.txt'])
      {
        'name': name,
        'state': 'uploaded',
        'size': 123,
        'browser_download_url':
            '$releaseRepository/releases/download/$tag/$name',
      },
  ],
};

void main() {
  test(
    'stable release selects official APK and checksum with version and notes',
    () async {
      final result = await UpdateService(fetchRelease: () async => release())
          .check('1.1.0', supported: true);
      expect(result.state, 'Update Available');
      expect(result.available, '1.2.0');
      expect(result.notes, 'Release notes');
      expect(result.assetUrl, endsWith('BookLedger-v1.2.0-Android.apk'));
      expect(result.checksumUrl, endsWith('SHA256SUMS.txt'));
      expect(result.message, contains('session-only'));
    },
  );

  for (final version in ['1.2.0', '1.2.0+build.9', '1.10.0', '2.0.0']) {
    test('$version is not downgraded', () {
      expect(
        releaseResult(release(), version, supported: true).state,
        'Up to Date',
      );
    });
  }
  test('semantic prerelease and numeric comparison preserves ordering', () {
    final versions = [
      '1.1.0-alpha',
      '1.1.0-alpha.2',
      '1.1.0-alpha.10',
      '1.1.0-beta',
      '1.1.0-rc.1',
      '1.1.0',
      '1.2.0',
      '1.10.0',
    ];
    for (var i = 0; i < versions.length - 1; i++) {
      expect(
        ReleaseVersion(versions[i]).compareTo(ReleaseVersion(versions[i + 1])),
        lessThan(0),
      );
    }
    expect(ReleaseVersion('v1.1.0+abc').compareTo(ReleaseVersion('1.1.0')), 0);
    expect(
      ReleaseVersion('1.1.0-1').compareTo(ReleaseVersion('1.1.0--1')),
      lessThan(0),
    );
    expect(
      ReleaseVersion('1.1.0-999999999999999999999')
          .compareTo(ReleaseVersion('1.1.0-1000000000000000000000')),
      lessThan(0),
    );
    expect(
      ReleaseVersion('999999999999999999999.0.0')
          .compareTo(ReleaseVersion('1000000000000000000000.0.0')),
      lessThan(0),
    );
  });
  for (final version in [
    'latest',
    '1.2',
    'v01.2.0',
    '1.1.0-rc.01',
    'v1.2.0\n',
  ]) {
    test('reject invalid version $version', () {
      expect(() => ReleaseVersion(version), throwsFormatException);
    });
  }
  for (final field in ['draft', 'prerelease']) {
    test('$field cannot be offered as stable', () async {
      final payload = release()..[field] = true;
      final result = await UpdateService(fetchRelease: () async => payload)
          .check('1.1.0', supported: true);
      expect(result.state, 'Unable to Check');
    });
  }
  test('prerelease tag cannot be a stable release even with stable flags', () {
    expect(
      () => releaseResult(release('v1.2.0-rc.1'), '1.1.0', supported: true),
      throwsFormatException,
    );
  });
  for (final name in ['BookLedger-v1.2.0-Android.apk', 'SHA256SUMS.txt']) {
    test('missing $name is unsupported', () {
      final payload = release();
      (payload['assets'] as List).removeWhere((a) => a['name'] == name);
      expect(
        releaseResult(payload, '1.1.0', supported: true).state,
        'Unsupported Update',
      );
    });
  }
  test('untrusted and duplicate assets are not offered', () {
    final payload = release();
    (payload['assets'] as List).first['browser_download_url'] =
        'https://example.com/payload.apk';
    expect(
      releaseResult(payload, '1.1.0', supported: true).state,
      'Unsupported Update',
    );
    final duplicate = release();
    (duplicate['assets'] as List).add((duplicate['assets'] as List).first);
    expect(
      releaseResult(duplicate, '1.1.0', supported: true).state,
      'Unsupported Update',
    );
  });
  test('development build may review notes but cannot update', () {
    final result = releaseResult(release(), '1.1.0', supported: false);
    expect(result.state, 'Unsupported Update');
    expect(result.assetUrl, isNull);
    expect(result.notes, 'Release notes');
    expect(
      result.message,
      contains('newer stable version is available for manual review'),
    );
    final same = releaseResult(release('v1.1.0'), '1.1.0', supported: false);
    expect(same.state, 'Unsupported Update');
    expect(same.assetUrl, isNull);
    expect(same.message, contains('No newer stable version is available.'));
  });
  for (final payload in <Object?>[
    null,
    [],
    {},
    {'draft': false, 'prerelease': false},
  ]) {
    test('unexpected response $payload is not a no-update result', () async {
      expect(
        (await UpdateService(
          fetchRelease: () async => payload,
        ).check('1.1.0', supported: true)).state,
        'Unable to Check',
      );
    });
  }
  for (final error in [
    const SocketException('offline'),
    TimeoutException('timeout'),
    for (final status in [403, 429, 500]) HttpException('HTTP $status'),
  ]) {
    test('network failure $error is reported without changes', () async {
      final result = await UpdateService(fetchRelease: () async => throw error)
          .check('1.1.0', supported: true);
      expect(result.state, 'Unable to Check');
    });
  }
  test('unavailable installed version does not perform a request', () async {
    var calls = 0;
    final service = UpdateService(
      fetchRelease: () async {
        calls++;
        return release();
      },
    );
    expect(
      (await service.check(null, supported: true)).state,
      'Unsupported Update',
    );
    expect(calls, 0);
  });
}
