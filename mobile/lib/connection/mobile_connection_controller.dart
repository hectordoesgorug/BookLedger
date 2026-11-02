import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'desktop_discovery.dart';

const mobileProtocolId = 'bookledger-mobile';
const mobileProtocolVersion = 1;
const mobileApiPrefix = '/api/v1';
const _pairingStorageKey = 'desktop_pairing_v1';

String _defaultDeviceName() {
  final hostname = Platform.localHostname.trim();
  if (hostname.isEmpty || hostname.toLowerCase() == 'localhost') {
    return Platform.isAndroid ? 'Android companion' : 'BookLedger companion';
  }
  return hostname.substring(0, min(hostname.length, 80));
}

enum MobileConnectionStatus {
  notPaired,
  pairing,
  connecting,
  connected,
  disconnected,
  desktopUnavailable,
  pairingRejected,
  authenticationRejected,
  serviceError,
}

class DesktopEndpoint {
  const DesktopEndpoint({required this.address, required this.port});

  final String address;
  final int port;

  Uri get baseUri => Uri(scheme: 'http', host: address, port: port);

  factory DesktopEndpoint.validated(String address, int port) {
    final parsed = InternetAddress.tryParse(address.trim());
    final bytes = parsed?.rawAddress;
    final isPrivateIpv4 =
        bytes != null &&
        (bytes[0] == 10 ||
            (bytes[0] == 172 && bytes[1] >= 16 && bytes[1] <= 31) ||
            (bytes[0] == 192 && bytes[1] == 168));
    if (parsed == null ||
        parsed.type != InternetAddressType.IPv4 ||
        !isPrivateIpv4 ||
        parsed.isLoopback ||
        parsed.address == '0.0.0.0' ||
        parsed.isMulticast ||
        port < 1 ||
        port > 65535) {
      throw const FormatException(
        'Enter a usable desktop IPv4 address and port.',
      );
    }
    return DesktopEndpoint(address: parsed.address, port: port);
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is DesktopEndpoint &&
          other.address == address &&
          other.port == port;

  @override
  int get hashCode => Object.hash(address, port);

  Map<String, Object> toJson() => {'address': address, 'port': port};

  factory DesktopEndpoint.fromJson(Object? value) {
    if (value is! Map<String, dynamic> ||
        value['address'] is! String ||
        value['port'] is! int) {
      throw const FormatException('A saved desktop endpoint is invalid.');
    }
    return DesktopEndpoint.validated(
      value['address'] as String,
      value['port'] as int,
    );
  }
}

class DesktopPairing {
  const DesktopPairing({
    required this.endpoints,
    required this.deviceToken,
    required this.deviceName,
    this.lastEndpoint,
  });

  final List<DesktopEndpoint> endpoints;
  final String deviceToken;
  final String deviceName;
  final DesktopEndpoint? lastEndpoint;

  DesktopPairing copyWith({
    List<DesktopEndpoint>? endpoints,
    DesktopEndpoint? lastEndpoint,
  }) => DesktopPairing(
    endpoints: endpoints ?? this.endpoints,
    deviceToken: deviceToken,
    deviceName: deviceName,
    lastEndpoint: lastEndpoint ?? this.lastEndpoint,
  );

  Map<String, Object?> toJson() => {
    'endpoints': endpoints.map((endpoint) => endpoint.toJson()).toList(),
    'device_token': deviceToken,
    'device_name': deviceName,
    if (lastEndpoint != null) 'last_endpoint': lastEndpoint!.toJson(),
  };

  factory DesktopPairing.fromJson(Object? value) {
    if (value is! Map<String, dynamic> ||
        value['endpoints'] is! List ||
        value['device_token'] is! String ||
        value['device_name'] is! String) {
      throw const FormatException('Saved pairing information is invalid.');
    }
    final endpoints = (value['endpoints'] as List)
        .map(DesktopEndpoint.fromJson)
        .toSet()
        .toList(growable: false);
    if (endpoints.isEmpty || endpoints.length > 32) {
      throw const FormatException('Saved desktop addresses are invalid.');
    }
    final token = value['device_token'] as String;
    final name = value['device_name'] as String;
    if (token.length < 40 || name.isEmpty || name.length > 80) {
      throw const FormatException('Saved pairing information is invalid.');
    }
    final lastEndpoint = value['last_endpoint'] == null
        ? null
        : DesktopEndpoint.fromJson(value['last_endpoint']);
    return DesktopPairing(
      endpoints: endpoints,
      deviceToken: token,
      deviceName: name,
      lastEndpoint: lastEndpoint,
    );
  }
}

class QrPairingPayload {
  const QrPairingPayload({
    required this.endpoints,
    required this.pairingCredential,
  });

  final List<DesktopEndpoint> endpoints;
  final String pairingCredential;

  factory QrPairingPayload.parse(String encoded) {
    final value = jsonDecode(encoded);
    if (value is! Map<String, dynamic> ||
        value['protocol'] != mobileProtocolId ||
        value['version'] != mobileProtocolVersion ||
        value['addresses'] is! List ||
        value['port'] is! int ||
        value['pairing_credential'] is! String) {
      throw const FormatException(
        'This is not a supported BookLedger pairing code.',
      );
    }
    final addresses = value['addresses'] as List;
    if (addresses.any((address) => address is! String)) {
      throw const FormatException(
        'The pairing code contains an invalid address.',
      );
    }
    final port = value['port'] as int;
    final endpoints = addresses
        .cast<String>()
        .map((address) => DesktopEndpoint.validated(address, port))
        .toList(growable: false);
    final credential = value['pairing_credential'] as String;
    if (endpoints.isEmpty ||
        endpoints.length > 32 ||
        credential.length < 32 ||
        credential.length > 128) {
      throw const FormatException('The pairing code is incomplete or invalid.');
    }
    return QrPairingPayload(
      endpoints: endpoints,
      pairingCredential: credential,
    );
  }
}

abstract interface class PairingStore {
  Future<DesktopPairing?> read();
  Future<void> write(DesktopPairing pairing);
  Future<void> clear();
  Future<void> verify();
}

class SecurePairingStore implements PairingStore {
  SecurePairingStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  @override
  Future<DesktopPairing?> read() async {
    final value = await _storage.read(key: _pairingStorageKey);
    if (value == null) {
      return null;
    }
    return DesktopPairing.fromJson(jsonDecode(value));
  }

  @override
  Future<void> write(DesktopPairing pairing) => _storage.write(
    key: _pairingStorageKey,
    value: jsonEncode(pairing.toJson()),
  );

  @override
  Future<void> clear() => _storage.delete(key: _pairingStorageKey);

  @override
  Future<void> verify() async {
    const key = 'secure_storage_probe_v1';
    final random = Random.secure();
    final challenge = base64Url.encode(
      List<int>.generate(32, (_) => random.nextInt(256)),
    );
    try {
      await _storage.write(key: key, value: challenge);
      final result = await _storage.read(key: key);
      if (result != challenge) {
        throw StateError('Secure-storage round trip did not match.');
      }
    } finally {
      await _storage.delete(key: key);
    }
  }
}

class PairingRejectedException implements Exception {
  const PairingRejectedException(this.message);
  final String message;
}

class PairingResponseException implements Exception {
  const PairingResponseException(this.statusCode, this.errorCode);
  final int statusCode;
  final String? errorCode;
}

class DeviceAuthenticationRejectedException implements Exception {
  const DeviceAuthenticationRejectedException();
}

abstract interface class ConnectionTransport {
  Future<DesktopPairing> pair(
    List<DesktopEndpoint> endpoints,
    String pairingCredential,
    String deviceName,
  );

  Future<DesktopEndpoint?> validate(
    List<DesktopEndpoint> endpoints,
    String deviceToken,
  );

  Future<bool> unpair(List<DesktopEndpoint> endpoints, String deviceToken);

  void close();
}

class HttpConnectionTransport implements ConnectionTransport {
  HttpConnectionTransport({HttpClient? client})
    : _client = client ?? HttpClient() {
    _client.connectionTimeout = const Duration(seconds: 2);
    _client.idleTimeout = const Duration(seconds: 10);
  }

  final HttpClient _client;

  Future<(int, Map<String, dynamic>?)> _request(
    DesktopEndpoint endpoint,
    String method,
    String path, {
    String? token,
    Map<String, Object?>? body,
  }) async {
    try {
      DesktopEndpoint.validated(endpoint.address, endpoint.port);
      const allowedRequests = <String, Set<String>>{
        'GET': {'$mobileApiPrefix/health', '$mobileApiPrefix/connection'},
        'POST': {'$mobileApiPrefix/pair'},
        'DELETE': {'$mobileApiPrefix/pair'},
      };
      if (!allowedRequests.containsKey(method) ||
          !allowedRequests[method]!.contains(path)) {
        throw const FormatException('Unsupported BookLedger API request.');
      }
      final request = await _client
          .openUrl(method, endpoint.baseUri.replace(path: path))
          .timeout(const Duration(seconds: 3));
      request.followRedirects = false;
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      request.headers.set(HttpHeaders.cacheControlHeader, 'no-cache');
      if (token != null) {
        request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      }
      if (body != null) {
        final encodedBody = jsonEncode(body);
        request.headers.contentType = ContentType.json;
        request.contentLength = utf8.encode(encodedBody).length;
        request.write(encodedBody);
      }
      final response = await request.close().timeout(
        const Duration(seconds: 3),
      );
      if (response.contentLength > 8192) {
        unawaited(response.drain<void>());
        return (response.statusCode, null);
      }
      final text = await utf8.decoder
          .bind(response)
          .join()
          .timeout(const Duration(seconds: 3));
      final decoded = text.isEmpty ? null : jsonDecode(text);
      return (
        response.statusCode,
        decoded is Map<String, dynamic> ? decoded : null,
      );
    } on TimeoutException {
      return (0, null);
    } on SocketException {
      return (0, null);
    } on HttpException {
      return (0, null);
    } on FormatException {
      return (0, null);
    }
  }

  Future<DesktopEndpoint?> _firstReachable(
    List<DesktopEndpoint> endpoints,
  ) async {
    final checks = endpoints.map((endpoint) async {
      final (status, body) = await _request(
        endpoint,
        'GET',
        '$mobileApiPrefix/health',
      );
      if (status == 200 &&
          body?['ok'] == true &&
          body?['protocol'] == mobileProtocolId &&
          body?['version'] == mobileProtocolVersion) {
        return endpoint;
      }
      return null;
    });
    final results = await Future.wait(checks);
    for (final endpoint in results) {
      if (endpoint != null) {
        return endpoint;
      }
    }
    return null;
  }

  @override
  Future<DesktopPairing> pair(
    List<DesktopEndpoint> endpoints,
    String pairingCredential,
    String deviceName,
  ) async {
    final endpoint = await _firstReachable(endpoints);
    if (endpoint == null) {
      throw const SocketException('BookLedger desktop is unavailable.');
    }
    final (status, body) = await _request(
      endpoint,
      'POST',
      '$mobileApiPrefix/pair',
      body: {
        'pairing_credential': pairingCredential,
        'device_name': deviceName,
      },
    );
    if (status == 401 || status == 409) {
      throw PairingRejectedException(
        status == 409
            ? 'Another mobile device is already paired. Unpair it on the desktop first.'
            : 'The pairing code was rejected or has expired. Generate a new code on the desktop.',
      );
    }
    final token = body?['device_token'];
    if (status != 201 ||
        token is! String ||
        token.length < 40 ||
        token.length > 128) {
      const safeErrorCodes = {
        'content_type_required',
        'invalid_content_length',
        'invalid_json',
        'object_required',
        'invalid_pairing_request',
        'pairing_storage_failed',
        'saved_pairing_unreadable',
      };
      final error = body?['error'];
      throw PairingResponseException(
        status,
        error is String && safeErrorCodes.contains(error) ? error : null,
      );
    }
    return DesktopPairing(
      endpoints: endpoints,
      lastEndpoint: endpoint,
      deviceToken: token,
      deviceName: deviceName,
    );
  }

  @override
  Future<DesktopEndpoint?> validate(
    List<DesktopEndpoint> endpoints,
    String deviceToken,
  ) async {
    final checks = endpoints.map((endpoint) async {
      final (status, body) = await _request(
        endpoint,
        'GET',
        '$mobileApiPrefix/connection',
        token: deviceToken,
      );
      if ((status == 401 || status == 403) &&
          body?['error'] == 'unauthorized') {
        throw const DeviceAuthenticationRejectedException();
      }
      if (status == 200 && body?['ok'] == true) {
        return endpoint;
      }
      return null;
    });
    final results = await Future.wait(checks);
    for (final endpoint in results) {
      if (endpoint != null) {
        return endpoint;
      }
    }
    return null;
  }

  @override
  Future<bool> unpair(
    List<DesktopEndpoint> endpoints,
    String deviceToken,
  ) async {
    final endpoint = await validate(endpoints, deviceToken);
    if (endpoint == null) {
      return false;
    }
    final (status, body) = await _request(
      endpoint,
      'DELETE',
      '$mobileApiPrefix/pair',
      token: deviceToken,
    );
    return status == 200 && body?['paired'] == false;
  }

  @override
  void close() => _client.close(force: true);
}

class MobileConnectionController extends ChangeNotifier
    with WidgetsBindingObserver {
  MobileConnectionController({
    PairingStore? store,
    ConnectionTransport? transport,
    DesktopDiscovery? discovery,
    String? deviceName,
  }) : _store = store ?? SecurePairingStore(),
       _transport = transport ?? HttpConnectionTransport(),
       _discovery = discovery ?? NsdDesktopDiscovery(),
       _deviceName = deviceName ?? _defaultDeviceName();

  final PairingStore _store;
  final ConnectionTransport _transport;
  final DesktopDiscovery _discovery;
  final String _deviceName;
  DesktopPairing? _pairing;
  Timer? _reconnectTimer;
  MobileConnectionStatus _status = MobileConnectionStatus.notPaired;
  String? _message;
  bool _initialized = false;
  bool _foreground = true;
  bool _busy = false;
  bool _reconnecting = false;
  bool _forgetting = false;
  bool _disposed = false;
  int _failureCount = 0;
  int _operationGeneration = 0;
  Future<void> _storeMutationTail = Future<void>.value();

  MobileConnectionStatus get status => _status;
  String? get message => _message;
  DesktopPairing? get pairing => _pairing;
  bool get isPaired => _pairing != null;
  bool get isBusy => _busy || _forgetting;
  bool get canForgetPairing =>
      _pairing != null && (!_busy || _reconnecting) && !_forgetting;

  Future<void> _mutateStore(Future<void> Function() mutation) {
    final next = _storeMutationTail.then((_) => mutation());
    _storeMutationTail = next.catchError((Object _) {});
    return next;
  }

  Future<bool> verifySecureStorage() async {
    try {
      await _store.verify();
      _message = 'Secure storage write/read test passed.';
      debugPrint('[BookLedger] Secure-storage probe passed.');
      return true;
    } on Object catch (error) {
      final detail = _safeErrorLabel(error);
      debugPrint('[BookLedger] Secure-storage probe failed: $detail');
      _message = 'Secure storage test failed ($detail).';
      return false;
    } finally {
      _notify();
    }
  }

  String _safeErrorLabel(Object error) {
    if (error is PlatformException) {
      return 'PlatformException code=${error.code}';
    }
    return error.runtimeType.toString();
  }

  Future<void> initialize() async {
    if (_initialized) {
      return;
    }
    _initialized = true;
    WidgetsBinding.instance.addObserver(this);
    try {
      _pairing = await _store.read();
    } catch (_) {
      _status = MobileConnectionStatus.serviceError;
      _message = 'Saved pairing information could not be read securely.';
      _notify();
      return;
    }
    if (_pairing == null) {
      _status = MobileConnectionStatus.notPaired;
      _notify();
      return;
    }
    unawaited(reconnect());
  }

  Future<bool> pairFromQr(String encoded) async {
    try {
      final payload = QrPairingPayload.parse(encoded);
      return await _pairWith(payload.endpoints, payload.pairingCredential);
    } on FormatException catch (error) {
      _status = MobileConnectionStatus.pairingRejected;
      _message = error.message;
      _notify();
      return false;
    }
  }

  Future<bool> pairManually({
    required String address,
    required int port,
    required String pairingCredential,
  }) async {
    try {
      final endpoint = DesktopEndpoint.validated(address, port);
      if (pairingCredential.trim().length < 32) {
        throw const FormatException(
          'Enter the pairing code shown on the desktop.',
        );
      }
      return await _pairWith([endpoint], pairingCredential.trim());
    } on FormatException catch (error) {
      _status = MobileConnectionStatus.pairingRejected;
      _message = error.message;
      _notify();
      return false;
    }
  }

  Future<bool> _pairWith(
    List<DesktopEndpoint> endpoints,
    String pairingCredential,
  ) async {
    if (_busy || _forgetting) {
      return false;
    }
    _busy = true;
    _status = MobileConnectionStatus.pairing;
    _message = 'Connecting to the desktop…';
    _notify();
    DesktopPairing? issuedPairing;
    var phase = 'desktop_pair_request';
    try {
      final pairing = await _transport.pair(
        endpoints,
        pairingCredential,
        _deviceName,
      );
      debugPrint(
        '[BookLedger] Desktop accepted pairing and returned a device token.',
      );
      issuedPairing = pairing;
      phase = 'secure_storage_write';
      await _mutateStore(() => _store.write(pairing));
      _pairing = pairing;
      _status = MobileConnectionStatus.connected;
      _message = 'Paired and connected to ${pairing.deviceName}.';
      _failureCount = 0;
      _scheduleReconnect(const Duration(seconds: 20));
      return true;
    } on PairingRejectedException catch (error) {
      _status = MobileConnectionStatus.pairingRejected;
      _message = error.message;
      return false;
    } on PairingResponseException catch (error) {
      final reason = error.errorCode;
      debugPrint(
        '[BookLedger] Pairing response was unusable: HTTP ${error.statusCode}'
        '${reason == null ? '' : ' ($reason)'}.',
      );
      _status = MobileConnectionStatus.serviceError;
      _message = reason == 'invalid_pairing_request'
          ? 'The desktop rejected the pairing request fields. Check the device name and retry.'
          : reason == 'pairing_storage_failed' || error.statusCode == 500
          ? 'The desktop could not save the pairing. Check the desktop app and retry.'
          : error.statusCode == 0
          ? 'The desktop pairing response could not be read. Check the connection and retry.'
          : 'The desktop returned HTTP ${error.statusCode} during pairing. Retry with a new pairing code.';
      return false;
    } on SocketException {
      _status = MobileConnectionStatus.desktopUnavailable;
      _message = 'BookLedger desktop could not be reached. Check the address and Wi-Fi.';
      return false;
    } on Object catch (error) {
      final detail = _safeErrorLabel(error);
      debugPrint('[BookLedger] Pairing failed during $phase: $detail');
      var rolledBack = false;
      if (issuedPairing != null) {
        try {
          rolledBack = await _transport.unpair(
            issuedPairing.endpoints,
            issuedPairing.deviceToken,
          );
        } catch (_) {
          // Do not log response payloads, pairing credentials, or device tokens.
        }
        try {
          await _mutateStore(_store.clear);
        } catch (_) {
          // Keep the original failure visible.
        }
      }
      _status = MobileConnectionStatus.serviceError;
      if (issuedPairing != null) {
        _message = rolledBack
            ? 'Desktop pairing was accepted, but secure storage failed ($detail). Test secure storage and retry.'
            : 'Desktop pairing was accepted, but secure storage failed ($detail). Unpair the phone on desktop before retrying.';
      } else {
        _message =
            'Pairing failed during $phase ($detail). Check the desktop address and try again.';
      }
      return false;
    } finally {
      _busy = false;
      _notify();
    }
  }

  Future<void> reconnect() async {
    if (_busy || !_foreground || _pairing == null || _disposed) {
      return;
    }
    _busy = true;
    _reconnecting = true;
    final operationGeneration = _operationGeneration;
    final wasConnected = _status == MobileConnectionStatus.connected;
    _status = MobileConnectionStatus.connecting;
    _message = 'Checking the desktop connection…';
    _notify();
    try {
      final pairing = _pairing!;
      final lastEndpoint = pairing.lastEndpoint;
      DesktopEndpoint? endpoint;
      if (lastEndpoint != null) {
        endpoint = await _transport.validate([
          lastEndpoint,
        ], pairing.deviceToken);
      }
      if (operationGeneration != _operationGeneration || _pairing == null) {
        return;
      }
      if (endpoint == null) {
        final discovered = await _discovery.discover();
        if (operationGeneration != _operationGeneration || _pairing == null) {
          return;
        }
        if (discovered != null) {
          endpoint = await _transport.validate([
            discovered,
          ], pairing.deviceToken);
        }
      }
      if (operationGeneration != _operationGeneration || _pairing == null) {
        return;
      }
      if (endpoint == null) {
        final fallbackEndpoints = pairing.endpoints
            .where((saved) => saved != lastEndpoint)
            .toList(growable: false);
        if (fallbackEndpoints.isNotEmpty) {
          endpoint = await _transport.validate(
            fallbackEndpoints,
            pairing.deviceToken,
          );
        }
      }
      if (endpoint != null) {
        final updatedEndpoints = <DesktopEndpoint>[
          ...pairing.endpoints.where(
            (saved) => saved != endpoint && saved != lastEndpoint,
          ),
          endpoint,
        ];
        final updatedPairing = pairing.copyWith(
          endpoints: updatedEndpoints.take(32).toList(growable: false),
          lastEndpoint: endpoint,
        );
        _pairing = updatedPairing;
        await _mutateStore(() => _store.write(updatedPairing));
        if (operationGeneration != _operationGeneration || _pairing == null) {
          return;
        }
        _status = MobileConnectionStatus.connected;
        _message = 'Connected to ${_pairing!.deviceName}.';
        _failureCount = 0;
        _scheduleReconnect(const Duration(seconds: 20));
      } else {
        _failureCount++;
        _status = wasConnected
            ? MobileConnectionStatus.disconnected
            : MobileConnectionStatus.desktopUnavailable;
        _message = wasConnected
            ? 'Connection lost. Reconnecting…'
            : 'Desktop unavailable. Retrying automatically…';
        _scheduleReconnect(_retryDelay());
      }
    } on DeviceAuthenticationRejectedException {
      if (operationGeneration == _operationGeneration && _pairing != null) {
        _reconnectTimer?.cancel();
        _status = MobileConnectionStatus.authenticationRejected;
        _message = 'This desktop rejected the saved pairing. Forget Pairing, then pair again.';
      }
    } on Object {
      if (operationGeneration == _operationGeneration && _pairing != null) {
        _failureCount++;
        _status = MobileConnectionStatus.desktopUnavailable;
        _message = 'Desktop unavailable. Retrying automatically…';
        _scheduleReconnect(_retryDelay());
      }
    } finally {
      _reconnecting = false;
      _busy = false;
      _notify();
    }
  }

  List<DesktopEndpoint> _orderedEndpoints(DesktopPairing pairing) => [
    if (pairing.lastEndpoint != null) pairing.lastEndpoint!,
    ...pairing.endpoints.where((endpoint) => endpoint != pairing.lastEndpoint),
  ];

  Duration _retryDelay() {
    const seconds = [2, 4, 8, 16, 30];
    return Duration(seconds: seconds[(_failureCount - 1).clamp(0, 4).toInt()]);
  }

  void _scheduleReconnect(Duration delay) {
    _reconnectTimer?.cancel();
    if (_foreground && _pairing != null && !_disposed) {
      _reconnectTimer = Timer(delay, () => unawaited(reconnect()));
    }
  }

  Future<bool> manualReconnect() async {
    if (_forgetting ||
        _status == MobileConnectionStatus.authenticationRejected) {
      return false;
    }
    if (_pairing == null) {
      _status = MobileConnectionStatus.notPaired;
      _message = 'Pair with BookLedger desktop first.';
      _notify();
      return false;
    }
    _reconnectTimer?.cancel();
    await reconnect();
    return _status == MobileConnectionStatus.connected;
  }

  Future<bool> forgetPairing() async {
    final pairing = _pairing;
    if (pairing == null || (_busy && !_reconnecting) || _forgetting) {
      return false;
    }
    _forgetting = true;
    _operationGeneration++;
    _reconnectTimer?.cancel();
    _pairing = null;
    _status = MobileConnectionStatus.notPaired;
    _message = 'Saved pairing forgotten on this phone. Desktop pairing was not revoked.';
    _notify();
    try {
      try {
        await _discovery.stop();
      } on Object {
        // Forgetting local credentials must continue if discovery cannot stop.
      }
      await _mutateStore(_store.clear);
      _failureCount = 0;
      return true;
    } on Object {
      _pairing = pairing;
      _status = MobileConnectionStatus.serviceError;
      _message = 'Saved pairing could not be removed from secure storage.';
      return false;
    } finally {
      _forgetting = false;
      _busy = false;
      _notify();
    }
  }

  Future<bool> unpair() async {
    final pairing = _pairing;
    if (pairing == null || _busy || _forgetting) {
      return false;
    }
    _busy = true;
    _status = MobileConnectionStatus.connecting;
    _message = 'Unpairing from the desktop…';
    _notify();
    try {
      final success = await _transport.unpair(
        _orderedEndpoints(pairing),
        pairing.deviceToken,
      );
      if (!success) {
        _status = MobileConnectionStatus.desktopUnavailable;
        _message = 'The desktop must be reachable to unpair this device.';
        return false;
      }
      await _mutateStore(_store.clear);
      _operationGeneration++;
      _pairing = null;
      _reconnectTimer?.cancel();
      _status = MobileConnectionStatus.notPaired;
      _message = 'Mobile device unpaired.';
      return true;
    } on Object {
      _status = MobileConnectionStatus.serviceError;
      _message = 'The saved pairing could not be removed.';
      return false;
    } finally {
      _busy = false;
      _notify();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _foreground = true;
      if (_pairing != null &&
          _status != MobileConnectionStatus.authenticationRejected) {
        _reconnectTimer?.cancel();
        unawaited(reconnect());
      }
    } else if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      _foreground = false;
      _reconnectTimer?.cancel();
      unawaited(_discovery.stop());
    }
  }

  void _notify() {
    if (!_disposed) {
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _reconnectTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_discovery.stop());
    _transport.close();
    super.dispose();
  }
}
