import 'dart:async';

import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import 'mobile_connection_controller.dart';

class MobileSetupScreen extends StatelessWidget {
  const MobileSetupScreen({required this.controller, super.key});

  final MobileConnectionController controller;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Pairing')),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [PairingSettingsSection(controller: controller)],
      ),
    ),
  );
}

class PairingSettingsSection extends StatefulWidget {
  const PairingSettingsSection({
    required this.controller,
    this.compact = false,
    super.key,
  });

  final MobileConnectionController controller;
  final bool compact;

  @override
  State<PairingSettingsSection> createState() => _PairingSettingsSectionState();
}

class _PairingSettingsSectionState extends State<PairingSettingsSection> {
  final _addressController = TextEditingController();
  final _portController = TextEditingController(text: '43821');
  final _credentialController = TextEditingController();

  @override
  void dispose() {
    _addressController.dispose();
    _portController.dispose();
    _credentialController.dispose();
    super.dispose();
  }

  Future<void> _scanQr() async {
    final paired = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => _QrPairingScreen(controller: widget.controller),
      ),
    );
    if (!mounted || paired != false) {
      return;
    }
    final message = widget.controller.message;
    if (message != null && message.isNotEmpty) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(message)));
    }
  }

  Future<void> _pairManually() async {
    final port = int.tryParse(_portController.text.trim());
    if (port == null) {
      await widget.controller.pairManually(
        address: _addressController.text,
        port: -1,
        pairingCredential: _credentialController.text,
      );
      return;
    }
    await widget.controller.pairManually(
      address: _addressController.text,
      port: port,
      pairingCredential: _credentialController.text,
    );
  }

  Future<void> _forgetPairing() async {
    final approved = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Forget this desktop on this phone?'),
        content: const Text(
          'This removes the saved connection credentials from this device. '
          'It does not revoke the pairing stored on the desktop. If that '
          'desktop is still paired, unpair this phone in Desktop Mobile App '
          'Setup before pairing again.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Forget'),
          ),
        ],
      ),
    );
    if (approved == true) {
      await widget.controller.forgetPairing();
    }
  }

  Future<void> _unpair() async {
    final approved = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Unpair this phone?'),
        content: const Text(
          'The desktop token will be revoked and you will need to pair again.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Unpair'),
          ),
        ],
      ),
    );
    if (approved == true) {
      await widget.controller.unpair();
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final controller = widget.controller;
        final pairing = controller.pairing;
        final compact = widget.compact;
        final buttonStyle = compact
            ? FilledButton.styleFrom(
                minimumSize: const Size(0, 48),
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
              )
            : null;
        final fieldPadding = compact
            ? const EdgeInsets.symmetric(horizontal: 12, vertical: 10)
            : null;
        final fieldGap = compact ? 6.0 : 10.0;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _ConnectionStatusCard(controller: controller, compact: compact),
            if (pairing != null) ...[
              SizedBox(height: compact ? 8 : 12),
              Text('Paired with ${pairing.deviceName}'),
              SizedBox(height: fieldGap),
              Text(
                'Saved desktop addresses: ${pairing.endpoints.map((endpoint) => '${endpoint.address}:${endpoint.port}').join(', ')}',
              ),
              SizedBox(height: fieldGap),
              FilledButton.tonal(
                onPressed: controller.isBusy
                    ? null
                    : controller.manualReconnect,
                style: buttonStyle,
                child: const Text('Reconnect now'),
              ),
              OutlinedButton(
                onPressed: controller.isBusy ? null : _unpair,
                style: compact
                    ? OutlinedButton.styleFrom(
                        minimumSize: const Size(0, 48),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 8,
                        ),
                      )
                    : null,
                child: const Text('Unpair this phone'),
              ),
              OutlinedButton(
                onPressed: controller.canForgetPairing ? _forgetPairing : null,
                style: compact
                    ? OutlinedButton.styleFrom(
                        minimumSize: const Size(0, 48),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 8,
                        ),
                      )
                    : null,
                child: const Text('Forget Pairing'),
              ),
            ] else ...[
              SizedBox(height: compact ? 8 : 12),
              FilledButton.icon(
                onPressed: controller.isBusy ? null : _scanQr,
                style: buttonStyle,
                icon: const Icon(Icons.qr_code_scanner),
                label: const Text('Pair with desktop QR code'),
              ),
              SizedBox(height: compact ? 10 : 20),
              Text(
                'Pair manually',
                style: compact
                    ? Theme.of(context).textTheme.titleSmall
                    : Theme.of(context).textTheme.titleMedium,
              ),
              SizedBox(height: compact ? 4 : 8),
              TextField(
                controller: _addressController,
                keyboardType: TextInputType.text,
                textInputAction: TextInputAction.next,
                decoration: InputDecoration(
                  labelText: 'Desktop IPv4 address',
                  hintText: 'For example, 192.168.1.25',
                  border: OutlineInputBorder(),
                  isDense: compact,
                  contentPadding: fieldPadding,
                ),
              ),
              SizedBox(height: fieldGap),
              TextField(
                controller: _portController,
                keyboardType: TextInputType.number,
                textInputAction: TextInputAction.next,
                decoration: InputDecoration(
                  labelText: 'Port',
                  border: OutlineInputBorder(),
                  isDense: compact,
                  contentPadding: fieldPadding,
                ),
              ),
              SizedBox(height: fieldGap),
              TextField(
                controller: _credentialController,
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => _pairManually(),
                decoration: InputDecoration(
                  labelText: 'Temporary pairing code',
                  helperText: 'Shown in Mobile App Setup on the desktop',
                  border: OutlineInputBorder(),
                  isDense: compact,
                  contentPadding: fieldPadding,
                ),
              ),
              SizedBox(height: compact ? 8 : 12),
              FilledButton(
                onPressed: controller.isBusy ? null : _pairManually,
                style: buttonStyle,
                child: const Text('Pair manually'),
              ),
            ],
            SizedBox(height: compact ? 10 : 20),
            const Text(
              'HTTP traffic is not encrypted. Pair only on a trusted local network.',
            ),
          ],
        );
      },
    );
  }
}

class _ConnectionStatusCard extends StatelessWidget {
  const _ConnectionStatusCard({required this.controller, this.compact = false});

  final MobileConnectionController controller;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final status = controller.status;
    final (label, color) = switch (status) {
      MobileConnectionStatus.notPaired => (
        'Not paired',
        Theme.of(context).colorScheme.outline,
      ),
      MobileConnectionStatus.pairing => (
        'Pairing in progress',
        Theme.of(context).colorScheme.primary,
      ),
      MobileConnectionStatus.connecting => (
        'Connecting',
        Theme.of(context).colorScheme.primary,
      ),
      MobileConnectionStatus.connected => (
        'Connected',
        Theme.of(context).colorScheme.tertiary,
      ),
      MobileConnectionStatus.disconnected => (
        'Disconnected',
        Theme.of(context).colorScheme.secondary,
      ),
      MobileConnectionStatus.desktopUnavailable => (
        'Desktop unavailable',
        Theme.of(context).colorScheme.secondary,
      ),
      MobileConnectionStatus.pairingRejected => (
        'Pairing rejected',
        Theme.of(context).colorScheme.error,
      ),
      MobileConnectionStatus.authenticationRejected => (
        'Pairing no longer valid',
        Theme.of(context).colorScheme.error,
      ),
      MobileConnectionStatus.serviceError => (
        'Connection error',
        Theme.of(context).colorScheme.error,
      ),
    };
    return Card(
      child: Padding(
        padding: EdgeInsets.all(compact ? 12 : 16),
        child: Row(
          children: [
            Icon(Icons.circle, size: 12, color: color),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: Theme.of(context).textTheme.titleMedium),
                  if (controller.message != null)
                    Text(
                      controller.message!,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _QrPairingScreen extends StatefulWidget {
  const _QrPairingScreen({required this.controller});

  final MobileConnectionController controller;

  @override
  State<_QrPairingScreen> createState() => _QrPairingScreenState();
}

class _QrPairingScreenState extends State<_QrPairingScreen> {
  late final MobileScannerController _scannerController;
  bool _handling = false;

  @override
  void initState() {
    super.initState();
    _scannerController = MobileScannerController(
      facing: CameraFacing.back,
      detectionSpeed: DetectionSpeed.noDuplicates,
      formats: const [BarcodeFormat.qrCode],
    );
  }

  Future<void> _onDetect(BarcodeCapture capture) async {
    if (_handling) {
      return;
    }
    String? rawValue;
    for (final barcode in capture.barcodes) {
      if (barcode.rawValue != null) {
        rawValue = barcode.rawValue;
        break;
      }
    }
    if (rawValue == null) {
      return;
    }
    _handling = true;
    await _scannerController.stop();
    if (!mounted) return;
    final paired = await widget.controller.pairFromQr(rawValue);
    if (mounted) {
      Navigator.of(context).pop(paired);
    }
  }

  @override
  void dispose() {
    unawaited(_scannerController.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan desktop QR code')),
      body: MobileScanner(
        controller: _scannerController,
        onDetect: _onDetect,
        errorBuilder: (context, error) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text('Camera unavailable: ${error.errorCode.name}'),
          ),
        ),
      ),
    );
  }
}
