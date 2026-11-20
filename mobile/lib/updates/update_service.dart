import 'dart:async';
import 'dart:convert';
import 'dart:io';

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
  });

  final String state, installed, notes, message;
  final String? available, releaseUrl, assetUrl, checksumUrl;
}

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
  }) => UpdateResult(
    state,
    installed,
    available: version,
    notes: notes,
    message: message,
    releaseUrl: url,
    assetUrl: asset,
    checksumUrl: checksum,
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
  String? assetUrl(String name) {
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
        ? expected
        : null;
  }

  final apk = assetUrl('BookLedger-$tag-Android.apk');
  final checksum = assetUrl('SHA256SUMS.txt');
  if (apk == null || checksum == null) {
    return result(
      'Unsupported Update',
      'The release is missing a complete Android APK or checksum manifest.',
    );
  }
  return result(
    'Update Available',
    'Review the official release instructions. Download and verify the official APK before using Android’s normal installation approval. '
        'The package, signing certificate and higher version code must match. Do not uninstall or clear data. '
        'Send all pending captures first: they are session-only and may be lost when installation closes the app. '
        'This check does not download or install updates.',
    asset: apk,
    checksum: checksum,
  );
}

class UpdateService {
  UpdateService({Future<Object?> Function()? fetchRelease})
    : _fetchRelease = fetchRelease ?? _readLatest;
  final Future<Object?> Function() _fetchRelease;

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
