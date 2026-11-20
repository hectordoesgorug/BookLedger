import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../settings/mobile_app_settings.dart';
import 'update_service.dart';

class UpdateCheckAction extends StatefulWidget {
  const UpdateCheckAction({required this.settings, this.service, super.key});
  final MobileAppSettings settings;
  final UpdateService? service;

  @override
  State<UpdateCheckAction> createState() => _UpdateCheckActionState();
}

class _UpdateCheckActionState extends State<UpdateCheckAction> {
  bool _checking = false;

  Future<void> _check() async {
    if (_checking) return;
    setState(() => _checking = true);
    await widget.settings.initialize();
    final result = await (widget.service ?? UpdateService()).check(
      widget.settings.version,
      supported: widget.settings.supportsUpdates,
    );
    if (!mounted) return;
    setState(() => _checking = false);
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(result.state),
        content: SizedBox(
          width: 500,
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Installed: ${result.installed}${widget.settings.versionCode == null ? '' : ' (code ${widget.settings.versionCode})'}',
                ),
                Text('Available: ${result.available ?? 'unknown'}'),
                const SizedBox(height: 12),
                Text(result.message),
                if (result.notes.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  const Text(
                    'Release Notes',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  SelectableText(result.notes),
                ],
              ],
            ),
          ),
        ),
        actions: [
          if (result.releaseUrl != null)
            TextButton(
              onPressed: () async {
                try {
                  final opened = await const MethodChannel(
                    'com.bookledger.mobile/external_url',
                  ).invokeMethod<bool>('openRelease', result.releaseUrl);
                  if (opened != true) throw StateError('Browser unavailable');
                } on Object {
                  if (dialogContext.mounted) {
                    ScaffoldMessenger.of(dialogContext).showSnackBar(
                      const SnackBar(
                        content: Text(
                          'Could not open a browser. Visit BookLedger’s GitHub Releases page.',
                        ),
                      ),
                    );
                  }
                }
              },
              child: const Text('Open Release Page'),
            ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => TextButton.icon(
    key: const ValueKey('check-for-updates'),
    onPressed: _checking ? null : _check,
    icon: _checking
        ? const SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        : const Icon(Icons.system_update_alt),
    label: Text(_checking ? 'Checking…' : 'Check for Updates'),
  );
}
