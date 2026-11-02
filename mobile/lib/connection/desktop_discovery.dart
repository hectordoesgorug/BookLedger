import 'package:flutter/services.dart';

import 'mobile_connection_controller.dart';

abstract interface class DesktopDiscovery {
  Future<DesktopEndpoint?> discover();
  Future<void> stop();
}

class NsdDesktopDiscovery implements DesktopDiscovery {
  NsdDesktopDiscovery({MethodChannel? channel})
    : _channel =
          channel ??
          const MethodChannel('com.bookledger.mobile/desktop_discovery');

  final MethodChannel _channel;

  @override
  Future<DesktopEndpoint?> discover() async {
    try {
      final value = await _channel
          .invokeMapMethod<String, Object?>('discoverDesktop')
          .timeout(const Duration(seconds: 9));
      if (value == null ||
          value['address'] is! String ||
          value['port'] is! int) {
        return null;
      }
      return DesktopEndpoint.validated(
        value['address'] as String,
        value['port'] as int,
      );
    } on Object {
      await stop();
      return null;
    }
  }

  @override
  Future<void> stop() async {
    try {
      await _channel.invokeMethod<void>('stopDiscovery');
    } on Object {
      // Discovery is supplementary; saved-address recovery remains available.
    }
  }
}
