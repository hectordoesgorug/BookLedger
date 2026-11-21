import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

const releaseRepository = 'https://github.com/hectordoesgorug/BookLedger';
const latestReleaseEndpoint =
    'https://api.github.com/repos/hectordoesgorug/BookLedger/releases/latest';

class ReleaseVersion implements Comparable<ReleaseVersion> {
  ReleaseVersion(String text) {
    final match = RegExp(
      r'^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$',
    ).firstMatch(text);
    if (match == null || match.group(0) != text) {
      throw const FormatException('Invalid version');
    }
    numbers = [for (var i = 1; i <= 3; i++) BigInt.parse(match.group(i)!)];
    pre = match.group(4)?.split('.') ?? [];
    if (pre.any((p) => RegExp(r'^0[0-9]+$').hasMatch(p))) {
      throw const FormatException('Invalid prerelease');
    }
  }

  late final List<BigInt> numbers;
  late final List<String> pre;

  @override
  int compareTo(ReleaseVersion other) {
    for (var i = 0; i < 3; i++) {
      final order = numbers[i].compareTo(other.numbers[i]);
      if (order != 0) return order;
    }
    if (pre.isEmpty || other.pre.isEmpty) {
      return pre.isEmpty == other.pre.isEmpty ? 0 : (pre.isEmpty ? 1 : -1);
    }
    for (var i = 0; i < pre.length && i < other.pre.length; i++) {
      final a = _numericIdentifier(pre[i]);
      final b = _numericIdentifier(other.pre[i]);
      final order = a != null && b != null
          ? a.compareTo(b)
          : a != null
          ? -1
          : b != null
          ? 1
          : pre[i].compareTo(other.pre[i]);
      if (order != 0) return order;
    }
    return pre.length.compareTo(other.pre.length);
  }

  static BigInt? _numericIdentifier(String value) =>
      RegExp(r'^[0-9]+$').hasMatch(value) ? BigInt.parse(value) : null;
}

class UpdateResult {
  const UpdateResult(
    this.state,
    this.installed, {
    this.available,
    this.notes = '',
    this.message = '',
    this.releaseUrl,
    this.assetUrl,
    this.checksumUrl,
    this.assetName,
    this.assetSize,
    this.checksumSize,
  });

  final String state, installed, notes, message;
  final String? available, releaseUrl, assetUrl, checksumUrl;
  final String? assetName;
  final int? assetSize, checksumSize;
}

class UpdateDownloadCancellation {
  bool _cancelled = false;
  final _listeners = <void Function()>{};

  bool get isCancelled => _cancelled;
  void cancel() {
    if (_cancelled) return;
    _cancelled = true;
    for (final listener in List<void Function()>.of(_listeners)) {
      listener();
    }
  }

  void _listen(void Function() listener) {
    if (_cancelled) {
      listener();
    } else {
      _listeners.add(listener);
    }
  }

  void _remove(void Function() listener) => _listeners.remove(listener);
}

class UpdateDownloadResponse {
  const UpdateDownloadResponse(this.statusCode, this.headers, this.body);
  final int statusCode;
  final Map<String, String> headers;
  final Stream<List<int>> body;
}

abstract interface class UpdateDownloadTransport {
  Future<UpdateDownloadResponse> get(Uri uri);
  void close();
}

class _IoUpdateDownloadTransport implements UpdateDownloadTransport {
  _IoUpdateDownloadTransport(this._client);
  final HttpClient _client;

  @override
  Future<UpdateDownloadResponse> get(Uri uri) async {
    final request = await _client
        .getUrl(uri)
        .timeout(const Duration(seconds: 15));
    request.followRedirects = false;
    request.headers.set(
      HttpHeaders.userAgentHeader,
      'BookLedger Mobile update downloader',
    );
    request.headers.set(HttpHeaders.acceptHeader, 'application/octet-stream');
    final response = await request.close().timeout(const Duration(seconds: 15));
    final headers = <String, String>{};
    response.headers.forEach((name, values) {
      headers[name.toLowerCase()] = values.join(',');
    });
    return UpdateDownloadResponse(response.statusCode, headers, response);
  }

  @override
  void close() => _client.close(force: true);
}

class VerifiedUpdateDownload {
  const VerifiedUpdateDownload(this.file, this.sha256);
  final File file;
  final String sha256;
}

class UpdateDownloadCanceled implements Exception {}

class _DigestSink implements Sink<Digest> {
  Digest? value;

  @override
  void add(Digest data) => value = data;

  @override
  void close() {}
}

const _maxApkBytes = 256 * 1024 * 1024;
const _maxManifestBytes = 1024 * 1024;
const _downloadHosts = {'github.com', 'release-assets.githubusercontent.com'};

UpdateResult releaseResult(
  Object? payload,
  String installed, {
  required bool supported,
}) {
  final current = ReleaseVersion(installed);
  if (payload is! Map ||
      payload['draft'] != false ||
      payload['prerelease'] != false) {
    throw const FormatException('No stable release');
  }
  final tag = payload['tag_name'];
  if (tag is! String) throw const FormatException('Missing version');
  final available = ReleaseVersion(tag);
  if (available.pre.isNotEmpty) throw const FormatException('Not stable');
  final url = '$releaseRepository/releases/tag/$tag';
  final notes = payload['body'];
  final assets = payload['assets'];
  if (payload['html_url'] != url || notes is! String || assets is! List) {
    throw const FormatException('Incomplete release');
  }
  final version = tag.startsWith('v') ? tag.substring(1) : tag;
  UpdateResult result(
    String state,
    String message, {
    String? asset,
    String? checksum,
    String? assetName,
    int? assetSize,
    int? checksumSize,
  }) => UpdateResult(
    state,
    installed,
    available: version,
    notes: notes,
    message: message,
    releaseUrl: url,
    assetUrl: asset,
    checksumUrl: checksum,
    assetName: assetName,
    assetSize: assetSize,
    checksumSize: checksumSize,
  );
  if (!supported) {
    return result(
      'Unsupported Update',
      '${available.compareTo(current) <= 0 ? 'No newer stable version is available.' : 'A newer stable version is available for manual review.'} '
          'This debug/development build or platform cannot use production updates. Review releases manually.',
    );
  }
  if (available.compareTo(current) <= 0) {
    return result('Up to Date', 'No newer stable version is available.');
  }
  (String, int)? asset(String name) {
    final matches = assets
        .whereType<Map>()
        .where((a) => a['name'] == name)
        .toList();
    if (matches.length != 1) return null;
    final a = matches.single;
    final expected = '$releaseRepository/releases/download/$tag/$name';
    return a['browser_download_url'] == expected &&
            a['state'] == 'uploaded' &&
            a['size'] is int &&
            (a['size'] as int) > 0
        ? (expected, a['size'] as int)
        : null;
  }

  final apk = asset('BookLedger-$tag-Android.apk');
  final checksum = asset('SHA256SUMS.txt');
  if (apk == null || checksum == null) {
    return result(
      'Unsupported Update',
      'The release is missing a complete Android APK or checksum manifest.',
    );
  }
  return result(
    'Update Available',
    'Download and verify the official APK for later use. Installation is not available yet. '
        'A future installation workflow must verify package, signing certificate and higher version code. Do not uninstall or clear data. '
        'Pending captures are session-only and can be lost if installation closes the app; transfer them before any later upgrade.',
    asset: apk.$1,
    checksum: checksum.$1,
    assetName: 'BookLedger-$tag-Android.apk',
    assetSize: apk.$2,
    checksumSize: checksum.$2,
  );
}

class UpdateService {
  UpdateService({
    Future<Object?> Function()? fetchRelease,
    this._downloadTransport,
    Future<Directory> Function()? stagingDirectory,
    Future<int?> Function()? freeBytes,
  }) : _fetchRelease = fetchRelease ?? _readLatest,
       _stagingDirectory = stagingDirectory ?? getApplicationSupportDirectory,
       _freeBytes = freeBytes ?? _readFreeBytes;
  final Future<Object?> Function() _fetchRelease;
  final UpdateDownloadTransport Function()? _downloadTransport;
  final Future<Directory> Function() _stagingDirectory;
  final Future<int?> Function() _freeBytes;

  Future<UpdateResult> check(
    String? installed, {
    required bool supported,
  }) async {
    try {
      ReleaseVersion(installed ?? '');
    } on FormatException {
      return UpdateResult(
        'Unsupported Update',
        installed ?? 'unknown',
        message: 'The installed version is unavailable or malformed.',
      );
    }
    try {
      final payload = await _fetchRelease().timeout(const Duration(seconds: 5));
      return releaseResult(payload, installed!, supported: supported);
    } on TimeoutException {
      return UpdateResult(
        'Unable to Check',
        installed!,
        message: 'GitHub did not respond in time. Try again later.',
      );
    } on Object {
      return UpdateResult(
        'Unable to Check',
        installed!,
        message: 'Could not check GitHub. Check your connection and try again; the service may be unavailable or rate-limited.',
      );
    }
  }

  Future<VerifiedUpdateDownload> download(
    UpdateResult result, {
    required bool supported,
    required UpdateDownloadCancellation cancellation,
    void Function(String state, int bytes, int? total)? onProgress,
  }) async {
    final name = result.assetName;
    final size = result.assetSize;
    final available = result.available;
    final tag = result.releaseUrl?.split('/').last;
    if (!supported ||
        result.state != 'Update Available' ||
        name == null ||
        size == null ||
        available == null ||
        tag == null ||
        result.releaseUrl != '$releaseRepository/releases/tag/$tag' ||
        (tag != available && tag != 'v$available')) {
      throw const FormatException(
        'An eligible stable Android update is required.',
      );
    }
    if (ReleaseVersion(result.installed).compareTo(ReleaseVersion(available)) >=
        0) {
      throw const FormatException(
        'Only a newer stable release can be downloaded.',
      );
    }
    if (name != 'BookLedger-$tag-Android.apk' ||
        !RegExp(r'^BookLedger-v?[0-9]+\.[0-9]+\.[0-9]+-Android\.apk$')
            .hasMatch(name) ||
        size <= 0 ||
        size > _maxApkBytes ||
        result.checksumSize == null ||
        result.checksumSize! <= 0 ||
        result.checksumSize! > _maxManifestBytes) {
      throw const FormatException(
        'The release APK size or name is unsupported.',
      );
    }
    final assetUrl = '$releaseRepository/releases/download/$tag/$name';
    final checksumUrl =
        '$releaseRepository/releases/download/$tag/SHA256SUMS.txt';
    if (result.assetUrl != assetUrl || result.checksumUrl != checksumUrl) {
      throw const FormatException(
        'The release asset does not match the official release.',
      );
    }
    final base = await _stagingDirectory();
    final updateRoot = Directory(
      '${base.path}${Platform.pathSeparator}updates',
    );
    await updateRoot.create(recursive: true);
    final free = await _freeBytes();
    if (free != null && free < size + result.checksumSize!) {
      throw const FileSystemException(
        'There is not enough free app storage for this update.',
      );
    }
    final folder = await updateRoot.createTemp('v$available-Android-');
    final partial = File(
      '${folder.path}${Platform.pathSeparator}$name.partial',
    );
    final finalFile = File('${folder.path}${Platform.pathSeparator}$name');
    final transport =
        _downloadTransport?.call() ??
        _IoUpdateDownloadTransport(
          HttpClient()..connectionTimeout = const Duration(seconds: 15),
        );
    void abort() => transport.close();
    cancellation._listen(abort);
    try {
      cancellation._throwIfCancelled();
      final manifest = await _readBounded(
        transport,
        Uri.parse(checksumUrl),
        expectedSize: result.checksumSize,
        maxSize: _maxManifestBytes,
        cancellation: cancellation,
      );
      final expected = _manifestDigest(manifest, name);
      cancellation._throwIfCancelled();
      final digest = _DigestSink();
      final input = sha256.startChunkedConversion(digest);
      var received = 0;
      final output = await partial.open(mode: FileMode.writeOnly);
      try {
        await for (final chunk in _downloadStream(
          transport,
          Uri.parse(assetUrl),
          expectedSize: size,
          maxSize: _maxApkBytes,
          cancellation: cancellation,
        )) {
          cancellation._throwIfCancelled();
          received += chunk.length;
          input.add(chunk);
          await output.writeFrom(chunk);
          onProgress?.call('Downloading', received, size);
        }
        await output.flush();
      } finally {
        await output.close();
      }
      input.close();
      onProgress?.call('Verifying', received, size);
      if (received != size || digest.value.toString() != expected) {
        throw const FormatException(
          'The downloaded APK did not match its release checksum and size.',
        );
      }
      cancellation._throwIfCancelled();
      final source = await partial.open();
      final header = await source.read(4);
      await source.close();
      if (header.length < 4 || header[0] != 0x50 || header[1] != 0x4b) {
        throw const FormatException(
          'The selected Android asset is not a ZIP-based APK.',
        );
      }
      await partial.rename(finalFile.path);
      onProgress?.call('Verified', received, size);
      return VerifiedUpdateDownload(finalFile, expected);
    } catch (error) {
      if (cancellation.isCancelled) throw UpdateDownloadCanceled();
      rethrow;
    } finally {
      cancellation._remove(abort);
      transport.close();
      try {
        if (await partial.exists()) await partial.delete();
        await folder.delete();
      } on FileSystemException {
        // A successfully renamed verified file keeps its unique staging folder.
      }
    }
  }

  static Future<int?> _readFreeBytes() async {
    try {
      return await const MethodChannel('com.bookledger.mobile/app_settings')
          .invokeMethod<int>('getUpdateFreeBytes');
    } on PlatformException {
      return null;
    } on MissingPluginException {
      return null;
    }
  }

  static Future<Uint8List> _readBounded(
    UpdateDownloadTransport transport,
    Uri uri, {
    required int? expectedSize,
    required int maxSize,
    required UpdateDownloadCancellation cancellation,
  }) async {
    final output = BytesBuilder(copy: false);
    await for (final chunk in _downloadStream(
      transport,
      uri,
      expectedSize: expectedSize,
      maxSize: maxSize,
      cancellation: cancellation,
    )) {
      output.add(chunk);
    }
    return output.takeBytes();
  }

  static Stream<List<int>> _downloadStream(
    UpdateDownloadTransport transport,
    Uri initial, {
    required int? expectedSize,
    required int maxSize,
    required UpdateDownloadCancellation cancellation,
  }) async* {
    var uri = initial;
    for (var redirects = 0; redirects <= 3; redirects++) {
      cancellation._throwIfCancelled();
      if (uri.scheme != 'https' ||
          !_downloadHosts.contains(uri.host) ||
          uri.userInfo.isNotEmpty ||
          uri.port != 443) {
        throw const FormatException(
          'The download URL or redirect is not approved.',
        );
      }
      final response = await transport.get(uri);
      if ([301, 302, 303, 307, 308].contains(response.statusCode)) {
        final location = response.headers['location'];
        if (location == null || redirects == 3) {
          throw const FormatException('The download redirect is invalid.');
        }
        await response.body.drain<void>().timeout(const Duration(seconds: 15));
        uri = uri.resolve(location);
        continue;
      }
      if (response.statusCode != HttpStatus.ok) {
        throw HttpException(
          'GitHub download failed (HTTP ${response.statusCode}).',
        );
      }
      final contentLength = response.headers[HttpHeaders.contentLengthHeader];
      if (contentLength != null &&
          (!RegExp(r'^[0-9]+$').hasMatch(contentLength) ||
              int.parse(contentLength) > maxSize ||
              expectedSize != null &&
                  int.parse(contentLength) != expectedSize)) {
        throw const FormatException(
          'The server size does not match the release metadata.',
        );
      }
      var received = 0;
      await for (final chunk in response.body.timeout(
        const Duration(seconds: 15),
      )) {
        cancellation._throwIfCancelled();
        received += chunk.length;
        if (received > maxSize ||
            expectedSize != null && received > expectedSize) {
          throw const FormatException(
            'The download exceeds its configured size limit.',
          );
        }
        yield chunk;
      }
      if (expectedSize != null && received != expectedSize) {
        throw const FormatException('The download is truncated.');
      }
      return;
    }
    throw const FormatException('The download exceeded the redirect limit.');
  }

  static String _manifestDigest(Uint8List bytes, String assetName) {
    final text = ascii.decode(bytes, allowInvalid: false);
    final entries = <String, String>{};
    final seen = <String>{};
    for (final line in const LineSplitter().convert(text)) {
      final match = RegExp(r'^([0-9a-fA-F]{64}) [ *]([^/\\\x00]+)$')
          .firstMatch(line);
      final name = match?.group(2);
      if (match == null || !seen.add(name!.toLowerCase())) {
        throw const FormatException(
          'The release checksum manifest is malformed or has duplicate entries.',
        );
      }
      entries[name] = match.group(1)!.toLowerCase();
    }
    final matches = entries[assetName];
    if (matches == null) {
      throw const FormatException(
        'The checksum manifest does not contain the selected APK exactly once.',
      );
    }
    return matches;
  }

  static Future<Object?> _readLatest() async {
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 5);
    try {
      return await (() async {
        final request = await client.getUrl(Uri.parse(latestReleaseEndpoint));
        request.followRedirects = false;
        request.headers.set('Accept', 'application/vnd.github+json');
        request.headers.set('User-Agent', 'BookLedger Mobile update check');
        final response = await request.close();
        if (response.statusCode != 200) {
          throw HttpException('Release service unavailable');
        }
        final bytes = <int>[];
        await for (final chunk in response) {
          bytes.addAll(chunk);
          if (bytes.length > 2 * 1024 * 1024) {
            throw const FormatException('Oversized release');
          }
        }
        return jsonDecode(utf8.decode(bytes));
      })().timeout(const Duration(seconds: 5));
    } finally {
      client.close(force: true);
    }
  }
}

extension on UpdateDownloadCancellation {
  void _throwIfCancelled() {
    if (isCancelled) throw UpdateDownloadCanceled();
  }
}
