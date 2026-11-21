import 'dart:io';
import 'dart:async';
import 'dart:convert';

import 'package:crypto/crypto.dart';
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

  test('download streams APK, reports progress, verifies checksum and isolates storage', () async {
    final apk = [0x50, 0x4b, 0x03, 0x04, ...utf8.encode('fixture apk')];
    final name = 'BookLedger-v1.2.0-Android.apk';
    final manifest = '${sha256.convert(apk)}  $name\n';
    final payload = release()
      ..['assets'] = [
        for (final item in [
          (name, apk.length),
          ('SHA256SUMS.txt', utf8.encode(manifest).length),
        ])
          {
            'name': item.$1,
            'state': 'uploaded',
            'size': item.$2,
            'browser_download_url':
                '$releaseRepository/releases/download/v1.2.0/${item.$1}',
          },
      ];
    final result = releaseResult(payload, '1.1.0', supported: true);
    final base = await Directory.systemTemp.createTemp('update-stage-');
    addTearDown(() => base.delete(recursive: true));
    final capture = File('${base.path}/pending.jpg')
      ..writeAsBytesSync([9, 8, 7]);
    final transport = _FixtureTransport({
      result.checksumUrl!: UpdateDownloadResponse(
        200,
        {},
        Stream.value(utf8.encode(manifest)),
      ),
      result.assetUrl!: UpdateDownloadResponse(200, {
        'content-length': '${apk.length}',
      }, Stream.value(apk)),
    });
    final service = UpdateService(
      fetchRelease: () async => payload,
      downloadTransport: () => transport,
      stagingDirectory: () async => base,
      freeBytes: () async => 10 * 1024 * 1024,
    );
    final progress = <String>[];
    final verified = await service.download(
      result,
      supported: true,
      cancellation: UpdateDownloadCancellation(),
      onProgress: (state, _, _) => progress.add(state),
    );
    expect(verified.file.readAsBytesSync(), apk);
    expect(verified.sha256, sha256.convert(apk).toString());
    expect(
      verified.file.path,
      contains('${Platform.pathSeparator}updates${Platform.pathSeparator}'),
    );
    expect(progress, contains('Downloading'));
    expect(progress, contains('Verified'));
    expect(capture.readAsBytesSync(), [9, 8, 7]);
    expect(transport.closed, isTrue);
  });

  test(
    'malformed, duplicate and mismatched manifests leave no partial APK',
    () async {
      final apk = [0x50, 0x4b, 0x03, 0x04, 1, 2, 3];
      final name = 'BookLedger-v1.2.0-Android.apk';
      final digest = sha256.convert(apk).toString();
      for (final manifest in [
        'bad line\n',
        '$digest  $name\n$digest  $name\n',
        '$digest  $name\n$digest  ${name.toUpperCase()}\n',
        '${'0' * 64}  $name\n',
      ]) {
        final payload = release()
          ..['assets'] = [
            for (final entry in [
              (name, apk.length),
              ('SHA256SUMS.txt', utf8.encode(manifest).length),
            ])
              {
                'name': entry.$1,
                'state': 'uploaded',
                'size': entry.$2,
                'browser_download_url':
                    '$releaseRepository/releases/download/v1.2.0/${entry.$1}',
              },
          ];
        final result = releaseResult(payload, '1.1.0', supported: true);
        final base = await Directory.systemTemp.createTemp('update-bad-');
        final service = UpdateService(
          downloadTransport: () => _FixtureTransport({
            result.checksumUrl!: UpdateDownloadResponse(
              200,
              {},
              Stream.value(utf8.encode(manifest)),
            ),
            result.assetUrl!: UpdateDownloadResponse(
              200,
              {},
              Stream.value(apk),
            ),
          }),
          stagingDirectory: () async => base,
          freeBytes: () async => 100000,
        );
        await expectLater(
          service.download(
            result,
            supported: true,
            cancellation: UpdateDownloadCancellation(),
          ),
          throwsFormatException,
        );
        expect(Directory('${base.path}/updates').listSync(), isEmpty);
        await base.delete(recursive: true);
      }
    },
  );

  test('download rejects unsafe redirects, HTTP errors, truncation, and low storage', () async {
    final apk = [0x50, 0x4b, 0x03, 0x04, 1, 2, 3];
    final name = 'BookLedger-v1.2.0-Android.apk';
    final manifest = '${sha256.convert(apk)}  $name\n';
    final payload = release()
      ..['assets'] = [
        for (final entry in [
          (name, apk.length),
          ('SHA256SUMS.txt', utf8.encode(manifest).length),
        ])
          {
            'name': entry.$1,
            'state': 'uploaded',
            'size': entry.$2,
            'browser_download_url':
                '$releaseRepository/releases/download/v1.2.0/${entry.$1}',
          },
      ];
    final result = releaseResult(payload, '1.1.0', supported: true);
    final base = await Directory.systemTemp.createTemp('update-errors-');
    addTearDown(() => base.delete(recursive: true));
    Future<UpdateService> service(
      Map<String, UpdateDownloadResponse> responses, {
      int free = 100000,
    }) async => UpdateService(
      downloadTransport: () => _FixtureTransport(responses),
      stagingDirectory: () async => base,
      freeBytes: () async => free,
    );
    final redirectService = await service({
      result.checksumUrl!: UpdateDownloadResponse(
        200,
        {},
        Stream.value(utf8.encode(manifest)),
      ),
      result.assetUrl!: UpdateDownloadResponse(302, {
        'location': 'https://example.com/apk',
      }, const Stream.empty()),
    });
    await expectLater(
      redirectService.download(
        result,
        supported: true,
        cancellation: UpdateDownloadCancellation(),
      ),
      throwsFormatException,
    );
    final httpService = await service({
      result.checksumUrl!: UpdateDownloadResponse(
        429,
        {},
        const Stream.empty(),
      ),
    });
    await expectLater(
      httpService.download(
        result,
        supported: true,
        cancellation: UpdateDownloadCancellation(),
      ),
      throwsA(isA<HttpException>()),
    );
    final shortService = await service({
      result.checksumUrl!: UpdateDownloadResponse(
        200,
        {},
        Stream.value(utf8.encode(manifest)),
      ),
      result.assetUrl!: UpdateDownloadResponse(
        200,
        {},
        Stream.value(apk.take(4).toList()),
      ),
    });
    await expectLater(
      shortService.download(
        result,
        supported: true,
        cancellation: UpdateDownloadCancellation(),
      ),
      throwsFormatException,
    );
    final lowStorage = await service({}, free: 1);
    await expectLater(
      lowStorage.download(
        result,
        supported: true,
        cancellation: UpdateDownloadCancellation(),
      ),
      throwsA(isA<FileSystemException>()),
    );
    expect(Directory('${base.path}/updates').listSync(), isEmpty);
  });

  test('pre-canceled update creates no staged or partial file', () async {
    final cancellation = UpdateDownloadCancellation()..cancel();
    final apk = [0x50, 0x4b, 0x03, 0x04, 1];
    final name = 'BookLedger-v1.2.0-Android.apk';
    final manifest = '${sha256.convert(apk)}  $name\n';
    final payload = release()
      ..['assets'] = [
        for (final entry in [
          (name, apk.length),
          ('SHA256SUMS.txt', utf8.encode(manifest).length),
        ])
          {
            'name': entry.$1,
            'state': 'uploaded',
            'size': entry.$2,
            'browser_download_url':
                '$releaseRepository/releases/download/v1.2.0/${entry.$1}',
          },
      ];
    final result = releaseResult(payload, '1.1.0', supported: true);
    final base = await Directory.systemTemp.createTemp('update-cancel-');
    addTearDown(() => base.delete(recursive: true));
    final service = UpdateService(
      downloadTransport: () => _FixtureTransport({}),
      stagingDirectory: () async => base,
      freeBytes: () async => 100000,
    );
    await expectLater(
      service.download(result, supported: true, cancellation: cancellation),
      throwsA(isA<UpdateDownloadCanceled>()),
    );
    expect(Directory('${base.path}/updates').listSync(), isEmpty);
  });

  test(
    'debug or non-newer update result cannot enter the download flow',
    () async {
      final base = await Directory.systemTemp.createTemp('update-ineligible-');
      addTearDown(() => base.delete(recursive: true));
      final service = UpdateService(
        downloadTransport: () => throw StateError('Network must not start.'),
        stagingDirectory: () async => base,
        freeBytes: () async => 100000,
      );
      final eligible = releaseResult(release(), '1.1.0', supported: true);
      await expectLater(
        service.download(
          eligible,
          supported: false,
          cancellation: UpdateDownloadCancellation(),
        ),
        throwsFormatException,
      );
      final current = releaseResult(
        release('v1.1.0'),
        '1.1.0',
        supported: true,
      );
      await expectLater(
        service.download(
          current,
          supported: true,
          cancellation: UpdateDownloadCancellation(),
        ),
        throwsFormatException,
      );
      expect(Directory('${base.path}/updates').existsSync(), isFalse);
    },
  );

  test('download rejects release identity and filename mismatches before network access', () async {
    final valid = releaseResult(release(), '1.1.0', supported: true);
    final service = UpdateService(
      downloadTransport: () => throw StateError('Network must not start.'),
    );
    for (final forged in [
      UpdateResult(
        valid.state,
        valid.installed,
        available: valid.available,
        releaseUrl: 'https://example.com/releases/tag/v1.2.0',
        assetUrl: valid.assetUrl,
        checksumUrl: valid.checksumUrl,
        assetName: valid.assetName,
        assetSize: valid.assetSize,
        checksumSize: valid.checksumSize,
      ),
      UpdateResult(
        valid.state,
        valid.installed,
        available: valid.available,
        releaseUrl: valid.releaseUrl,
        assetUrl: valid.assetUrl,
        checksumUrl: valid.checksumUrl,
        assetName: 'BookLedger-v9.9.9-Android.apk',
        assetSize: valid.assetSize,
        checksumSize: valid.checksumSize,
      ),
    ]) {
      await expectLater(
        service.download(
          forged,
          supported: true,
          cancellation: UpdateDownloadCancellation(),
        ),
        throwsFormatException,
      );
    }
  });
}

class _FixtureTransport implements UpdateDownloadTransport {
  _FixtureTransport(this.responses);
  final Map<String, UpdateDownloadResponse> responses;
  bool closed = false;

  @override
  Future<UpdateDownloadResponse> get(Uri uri) async =>
      responses[uri.toString()]!;

  @override
  void close() => closed = true;
}
