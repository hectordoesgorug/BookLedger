import 'dart:async';

import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import 'mobile_connection_controller.dart';

class MobileSetupScreen extends StatefulWidget {
  const MobileSetupScreen({required this.controller, super.key});

  final MobileConnectionController controller;

  @override
  State<MobileSetupScreen> createState() => _MobileSetupScreenState();
}

class _MobileSetupScreenState extends State<MobileSetupScreen> {
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
    return Scaffold(
      appBar: AppBar(title: const Text('Mobile App Setup')),
      body: AnimatedBuilder(
        animation: widget.controller,
        builder: (context, _) {
          final controller = widget.controller;
          final pairing = controller.pairing;
          return SafeArea(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                _ConnectionStatusCard(controller: controller),
                if (pairing != null) ...[
                  const SizedBox(height: 12),
                  Text('Paired with ${pairing.deviceName}'),
                  const SizedBox(height: 8),
                  Text(
                    'Saved desktop addresses: ${pairing.endpoints.map((endpoint) => '${endpoint.address}:${endpoint.port}').join(', ')}',
                  ),
                  const SizedBox(height: 12),
                  FilledButton.tonal(
                    onPressed: controller.isBusy
                        ? null
                        : controller.manualReconnect,
                    child: const Text('Reconnect now'),
                  ),
                  OutlinedButton(
                    onPressed: controller.isBusy ? null : _unpair,
                    child: const Text('Unpair this phone'),
                  ),
                  OutlinedButton(
                    onPressed: controller.canForgetPairing
                        ? _forgetPairing
                        : null,
                    child: const Text('Forget Pairing'),
                  ),
                ] else ...[
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: controller.isBusy
                        ? null
                        : controller.verifySecureStorage,
                    icon: const Icon(Icons.lock_outline),
                    label: const Text('Test secure storage'),
                  ),
                  const SizedBox(height: 18),
                  FilledButton.icon(
                    onPressed: controller.isBusy ? null : _scanQr,
                    icon: const Icon(Icons.qr_code_scanner),
                    label: const Text('Pair with desktop QR code'),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    'Pair manually',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _addressController,
                    keyboardType: TextInputType.text,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: 'Desktop IPv4 address',
                      hintText: 'For example, 192.168.1.25',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _portController,
                    keyboardType: TextInputType.number,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: 'Port',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _credentialController,
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) => _pairManually(),
                    decoration: const InputDecoration(
                      labelText: 'Temporary pairing code',
                      helperText: 'Shown in Mobile App Setup on the desktop',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: controller.isBusy ? null : _pairManually,
                    child: const Text('Pair manually'),
                  ),
                ],
                const SizedBox(height: 20),
                const Text(
                  'HTTP traffic is not encrypted. Pair only on a trusted local network.',
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _ConnectionStatusCard extends StatelessWidget {
  const _ConnectionStatusCard({required this.controller});

  final MobileConnectionController controller;

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
      MobileConnectionStatus.connected => ('Connected', Colors.green),
      MobileConnectionStatus.disconnected => ('Disconnected', Colors.orange),
      MobileConnectionStatus.desktopUnavailable => (
        'Desktop unavailable',
        Colors.orange,
      ),
      MobileConnectionStatus.pairingRejected => (
        'Pairing rejected',
        Colors.red,
      ),
      MobileConnectionStatus.authenticationRejected => (
        'Pairing no longer valid',
        Colors.red,
      ),
      MobileConnectionStatus.serviceError => ('Connection error', Colors.red),
    };
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
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
