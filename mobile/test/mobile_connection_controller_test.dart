import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/connection/desktop_discovery.dart';
import 'package:mobile/connection/mobile_connection_controller.dart';

class _MemoryPairingStore implements PairingStore {
  DesktopPairing? pairing;
  int writes = 0;
  int clears = 0;
  bool failWrites = false;
  bool failVerify = false;

  @override
  Future<DesktopPairing?> read() async => pairing;

  @override
  Future<void> write(DesktopPairing value) async {
    writes++;
    if (failWrites) {
      throw StateError('Secure storage unavailable');
    }
    pairing = value;
  }

  @override
  Future<void> clear() async {
    clears++;
    pairing = null;
  }

  @override
  Future<void> verify() async {
    if (failVerify) {
      throw StateError('Secure storage unavailable');
    }
  }
}

class _FakeConnectionTransport implements ConnectionTransport {
  DesktopEndpoint? validateResult;
  Object? validateError;
  bool unpairResult = true;
  int pairCalls = 0;
  int validateCalls = 0;
  int unpairCalls = 0;
  final validationRequests = <List<DesktopEndpoint>>[];
  final validationResults = <DesktopEndpoint?>[];

  @override
  Future<DesktopPairing> pair(
    List<DesktopEndpoint> endpoints,
    String pairingCredential,
    String deviceName,
  ) async {
    pairCalls++;
    return DesktopPairing(
      endpoints: endpoints,
      lastEndpoint: endpoints.first,
      deviceToken: 'device-token-${List.filled(48, 'x').join()}',
      deviceName: deviceName,
    );
  }

  @override
  Future<DesktopEndpoint?> validate(
    List<DesktopEndpoint> endpoints,
    String deviceToken,
  ) async {
    validateCalls++;
    validationRequests.add(List.of(endpoints));
    if (validateError case final error?) {
      throw error;
    }
    if (validationResults.isNotEmpty) {
      return validationResults.removeAt(0);
    }
    return validateResult;
  }

  @override
  Future<bool> unpair(
    List<DesktopEndpoint> endpoints,
    String deviceToken,
  ) async {
    unpairCalls++;
    return unpairResult;
  }

  @override
  void close() {}
}

class _FakeDesktopDiscovery implements DesktopDiscovery {
  _FakeDesktopDiscovery(this.result);

  final DesktopEndpoint? result;
  int discoverCalls = 0;
  int stopCalls = 0;

  @override
  Future<DesktopEndpoint?> discover() async {
    discoverCalls++;
    return result;
  }

  @override
  Future<void> stop() async {
    stopCalls++;
  }
}

final _endpoint = DesktopEndpoint(address: '192.168.1.20', port: 43821);

DesktopPairing _savedPairing() => DesktopPairing(
  endpoints: [_endpoint],
  deviceToken: 'device-token-${List.filled(48, 'x').join()}',
  deviceName: 'Poco X6',
  lastEndpoint: _endpoint,
);

String _qrPayload({
  List<String> addresses = const ['192.168.1.20', '192.168.137.1'],
  String protocol = mobileProtocolId,
  int version = mobileProtocolVersion,
}) => jsonEncode({
  'protocol': protocol,
  'version': version,
  'addresses': addresses,
  'port': 43821,
  'pairing_credential': 'temporary-${List.filled(40, 'p').join()}',
});

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'QR parser accepts candidate addresses and rejects invalid payloads',
    () {
      final payload = QrPairingPayload.parse(_qrPayload());

      expect(payload.endpoints, hasLength(2));
      expect(payload.endpoints.first.address, '192.168.1.20');
      expect(payload.pairingCredential, startsWith('temporary-'));

      expect(
        () => QrPairingPayload.parse(_qrPayload(protocol: 'other')),
        throwsFormatException,
      );
      expect(
        () => QrPairingPayload.parse(_qrPayload(addresses: ['127.0.0.1'])),
        throwsFormatException,
      );
      expect(
        () => QrPairingPayload.parse(
          _qrPayload(addresses: ['192.168.1.20', 'bad']),
        ),
        throwsFormatException,
      );
      expect(
        () => DesktopEndpoint.validated('8.8.8.8', 43821),
        throwsFormatException,
      );
      expect(
        DesktopEndpoint.validated('172.31.8.4', 43821).address,
        '172.31.8.4',
      );
      expect(
        () => DesktopEndpoint.validated('172.32.8.4', 43821),
        throwsFormatException,
      );
    },
  );

  test(
    'QR pairing stores a device token separately from the QR credential',
    () async {
      final store = _MemoryPairingStore();
      final transport = _FakeConnectionTransport()..validateResult = _endpoint;
      final controller = MobileConnectionController(
        store: store,
        transport: transport,
        deviceName: 'Poco X6',
      );
      addTearDown(controller.dispose);

      expect(await controller.pairFromQr(_qrPayload()), isTrue);

      expect(transport.pairCalls, 1);
      expect(store.writes, 1);
      expect(controller.status, MobileConnectionStatus.connected);
      expect(store.pairing!.deviceToken, startsWith('device-token-'));
      expect(store.pairing!.deviceToken, isNot(contains('temporary-')));
      expect(store.pairing!.endpoints, hasLength(2));
    },
  );

  test('saved endpoints compare by address and port and deduplicate', () {
    final endpoint = DesktopEndpoint(address: '192.168.1.20', port: 43821);
    final saved = DesktopPairing.fromJson({
      'endpoints': [
        endpoint.toJson(),
        DesktopEndpoint(address: '192.168.1.20', port: 43821).toJson(),
      ],
      'last_endpoint': DesktopEndpoint(
        address: '192.168.1.20',
        port: 43821,
      ).toJson(),
      'device_token': 'device-token-${List.filled(48, 'x').join()}',
      'device_name': 'Poco X6',
    });

    expect(saved.endpoints, [endpoint]);
    expect(saved.lastEndpoint, endpoint);
  });

  test(
    'secure-storage self test reports write/read failures without pairing',
    () async {
      final store = _MemoryPairingStore()..failVerify = true;
      final controller = MobileConnectionController(
        store: store,
        transport: _FakeConnectionTransport(),
      );
      addTearDown(controller.dispose);

      expect(await controller.verifySecureStorage(), isFalse);
      expect(controller.message, contains('StateError'));
      expect(controller.isPaired, isFalse);
    },
  );

  test('failed secure storage rolls back the issued desktop pairing', () async {
    final store = _MemoryPairingStore()..failWrites = true;
    final transport = _FakeConnectionTransport();
    final controller = MobileConnectionController(
      store: store,
      transport: transport,
    );
    addTearDown(controller.dispose);

    expect(await controller.pairFromQr(_qrPayload()), isFalse);

    expect(transport.pairCalls, 1);
    expect(transport.unpairCalls, 1);
    expect(store.clears, 1);
    expect(controller.isPaired, isFalse);
    expect(controller.status, MobileConnectionStatus.serviceError);
  });

  test(
    'invalid manual IP and pairing code are rejected before network access',
    () async {
      final store = _MemoryPairingStore();
      final transport = _FakeConnectionTransport();
      final controller = MobileConnectionController(
        store: store,
        transport: transport,
      );
      addTearDown(controller.dispose);

      expect(
        await controller.pairManually(
          address: '127.0.0.1',
          port: 43821,
          pairingCredential: 'temporary-${List.filled(40, 'p').join()}',
        ),
        isFalse,
      );
      expect(
        await controller.pairManually(
          address: '192.168.1.20',
          port: 43821,
          pairingCredential: 'short',
        ),
        isFalse,
      );
      expect(transport.pairCalls, 0);
      expect(controller.status, MobileConnectionStatus.pairingRejected);
    },
  );

  test(
    'startup validates saved pairing and foregrounding reconnects',
    () async {
      final store = _MemoryPairingStore()..pairing = _savedPairing();
      final transport = _FakeConnectionTransport()..validateResult = _endpoint;
      final controller = MobileConnectionController(
        store: store,
        transport: transport,
      );
      addTearDown(controller.dispose);

      await controller.initialize();
      await Future<void>.delayed(const Duration(milliseconds: 10));

      expect(transport.validateCalls, 1);
      expect(controller.status, MobileConnectionStatus.connected);
      expect(store.writes, 1);

      controller.didChangeAppLifecycleState(AppLifecycleState.paused);
      await Future<void>.delayed(const Duration(milliseconds: 30));
      expect(transport.validateCalls, 1);

      controller.didChangeAppLifecycleState(AppLifecycleState.resumed);
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(transport.validateCalls, 2);
    },
  );

  testWidgets('desktop outage retries with exponential backoff', (
    tester,
  ) async {
    final store = _MemoryPairingStore()..pairing = _savedPairing();
    final transport = _FakeConnectionTransport();
    final controller = MobileConnectionController(
      store: store,
      transport: transport,
      discovery: _FakeDesktopDiscovery(null),
    );
    await controller.initialize();
    await tester.pump();

    expect(transport.validateCalls, 1);
    expect(controller.status, MobileConnectionStatus.desktopUnavailable);

    await tester.pump(const Duration(seconds: 1));
    expect(transport.validateCalls, 1);
    await tester.pump(const Duration(seconds: 1));
    await tester.pump();
    expect(transport.validateCalls, 2);
    expect(controller.status, MobileConnectionStatus.desktopUnavailable);
    controller.dispose();
  });

  test(
    'reconnect discovers a changed private endpoint before saved fallbacks',
    () async {
      final oldEndpoint = DesktopEndpoint(address: '192.168.1.20', port: 43821);
      final fallbackEndpoint = DesktopEndpoint(
        address: '192.168.1.21',
        port: 43821,
      );
      final discoveredEndpoint = DesktopEndpoint(
        address: '192.168.137.1',
        port: 43821,
      );
      final saved = DesktopPairing(
        endpoints: [oldEndpoint, fallbackEndpoint],
        lastEndpoint: oldEndpoint,
        deviceToken: _savedPairing().deviceToken,
        deviceName: 'Poco X6',
      );
      final store = _MemoryPairingStore()..pairing = saved;
      final transport = _FakeConnectionTransport()
        ..validationResults.addAll([null, discoveredEndpoint]);
      final discovery = _FakeDesktopDiscovery(discoveredEndpoint);
      final controller = MobileConnectionController(
        store: store,
        transport: transport,
        discovery: discovery,
      );
      addTearDown(controller.dispose);

      await controller.initialize();
      await Future<void>.delayed(const Duration(milliseconds: 10));

      expect(transport.validationRequests.first, [oldEndpoint]);
      expect(transport.validationRequests[1], [discoveredEndpoint]);
      expect(discovery.discoverCalls, 1);
      expect(controller.status, MobileConnectionStatus.connected);
      expect(controller.pairing!.lastEndpoint, discoveredEndpoint);
      expect(controller.pairing!.endpoints, [
        fallbackEndpoint,
        discoveredEndpoint,
      ]);
      expect(transport.validationRequests, hasLength(2));
    },
  );
  test(
    'forget pairing clears local credentials without contacting desktop',
    () async {
      final store = _MemoryPairingStore()..pairing = _savedPairing();
      final transport = _FakeConnectionTransport();
      final discovery = _FakeDesktopDiscovery(null);
      final controller = MobileConnectionController(
        store: store,
        transport: transport,
        discovery: discovery,
      );
      addTearDown(controller.dispose);

      await controller.initialize();
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(transport.validateCalls, 1);
      expect(await controller.forgetPairing(), isTrue);
      await Future<void>.delayed(const Duration(milliseconds: 2100));
      expect(transport.validateCalls, 1);

      expect(store.pairing, isNull);
      expect(store.clears, 1);
      expect(controller.isPaired, isFalse);
      expect(controller.status, MobileConnectionStatus.notPaired);
      expect(controller.message, contains('not revoked'));
      expect(transport.unpairCalls, 0);
      expect(discovery.stopCalls, greaterThan(0));
    },
  );

  test(
    'authentication rejection stops retries but network failure retries',
    () async {
      final store = _MemoryPairingStore()..pairing = _savedPairing();
      final transport = _FakeConnectionTransport()
        ..validateError = const DeviceAuthenticationRejectedException();
      final discovery = _FakeDesktopDiscovery(null);
      final controller = MobileConnectionController(
        store: store,
        transport: transport,
        discovery: discovery,
      );
      addTearDown(controller.dispose);

      await controller.initialize();
      await Future<void>.delayed(const Duration(milliseconds: 10));

      expect(controller.status, MobileConnectionStatus.authenticationRejected);
      expect(controller.message, contains('Forget Pairing'));
      expect(await controller.manualReconnect(), isFalse);
      expect(transport.validateCalls, 1);
      expect(await controller.forgetPairing(), isTrue);
      expect(controller.status, MobileConnectionStatus.notPaired);
      expect(transport.unpairCalls, 0);
    },
  );

  test(
    'unpair revokes the token before clearing secure pairing data',
    () async {
      final store = _MemoryPairingStore()..pairing = _savedPairing();
      final transport = _FakeConnectionTransport()..validateResult = _endpoint;
      final controller = MobileConnectionController(
        store: store,
        transport: transport,
      );
      addTearDown(controller.dispose);

      await controller.initialize();
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(await controller.unpair(), isTrue);

      expect(transport.unpairCalls, 1);
      expect(store.clears, 1);
      expect(controller.isPaired, isFalse);
      expect(controller.status, MobileConnectionStatus.notPaired);
    },
  );
}
