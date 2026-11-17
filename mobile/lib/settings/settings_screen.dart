import 'dart:async';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import '../connection/mobile_connection_controller.dart';
import '../connection/mobile_setup_screen.dart';
import '../success_notification.dart';
import 'clear_mobile_data.dart';
import 'mobile_app_settings.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    required this.controller,
    required this.settings,
    this.clearPendingPhotos,
    super.key,
  });

  final MobileConnectionController controller;
  final MobileAppSettings settings;
  final Future<void> Function()? clearPendingPhotos;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _clearing = false;

  Future<void> _clearData() async {
    if (_clearing) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Clear Mobile Data?'),
        content: const Text(
          'This will permanently delete locally stored pending ISBNs, photos, '
          'and unsent captures. It will also forget the current desktop '
          'pairing on this phone. Books already saved in the desktop '
          'BookLedger library will not be deleted. This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const ValueKey('clear-data-confirm'),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(dialogContext).colorScheme.error,
              foregroundColor: Theme.of(dialogContext).colorScheme.onError,
            ),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Clear Data'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _clearing = true);
    try {
      await widget.controller.initialize();
      if (widget.controller.isBusy) {
        _showMessage(
          'Wait for the current connection operation to finish, then retry.',
        );
        return;
      }
      if (!await widget.controller.clearLocalPairing()) {
        _showMessage(
          widget.controller.message ?? 'The saved pairing could not be cleared. No capture files were deleted.',
        );
        return;
      }

      try {
        if (widget.clearPendingPhotos == null) {
          await clearPendingCapturePhotos(await getTemporaryDirectory());
        } else {
          await widget.clearPendingPhotos!();
        }
      } on Object {
        _showMessage(
          'Pairing was forgotten, but pending photos could not all be deleted. Retry Clear Data.',
        );
        return;
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        successNotification(
          context,
          'Pending captures deleted and pairing forgotten on this phone.',
        ),
      );
      Navigator.of(context).popUntil((route) => route.isFirst);
    } on Object {
      _showMessage('Clear Data could not finish. Please retry.');
    } finally {
      if (mounted) setState(() => _clearing = false);
    }
  }

  void _showMessage(String message) {
    if (mounted) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(message)));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Settings')),
    body: SafeArea(
      child: ListView(
        key: const ValueKey('settings-list'),
        padding: const EdgeInsets.all(12),
        children: [
          _sectionHeading(
            context,
            'Pairing',
            key: const ValueKey('settings-pairing-heading'),
          ),
          PairingSettingsSection(controller: widget.controller, compact: true),
          const SizedBox(height: 12),
          DarkModeSwitch(
            settings: widget.settings,
            key: const ValueKey('dark-mode-section'),
          ),
          const SizedBox(height: 12),
          _sectionHeading(
            context,
            'Clear Data',
            key: const ValueKey('settings-clear-data-heading'),
          ),
          const Text(
            'Delete pending captures and forget pairing on this phone.',
          ),
          const SizedBox(height: 4),
          FilledButton.icon(
            key: const ValueKey('clear-data-action'),
            onPressed: _clearing ? null : _clearData,
            style: FilledButton.styleFrom(
              minimumSize: const Size(0, 48),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              backgroundColor: Theme.of(context).colorScheme.error,
              foregroundColor: Theme.of(context).colorScheme.onError,
            ),
            icon: const Icon(Icons.delete_outline),
            label: const Text('Clear Data'),
          ),
          if (_clearing)
            const Padding(
              padding: EdgeInsets.all(8),
              child: Center(child: CircularProgressIndicator()),
            ),
        ],
      ),
    ),
  );
}

Widget _sectionHeading(BuildContext context, String title, {Key? key}) =>
    Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Text(
        title,
        key: key,
        style: Theme.of(context).textTheme.titleMedium,
      ),
    );

class DarkModeSwitch extends StatelessWidget {
  const DarkModeSwitch({required this.settings, super.key});

  final MobileAppSettings settings;

  Future<void> _select(BuildContext context, ThemeMode mode) async {
    try {
      await settings.setThemeMode(mode);
    } on Object {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('The theme preference could not be saved.'),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: settings,
    builder: (context, _) => SwitchListTile(
      key: const ValueKey('dark-mode-switch'),
      contentPadding: EdgeInsets.zero,
      title: const Text('Dark Mode'),
      value: settings.themeMode == ThemeMode.dark,
      onChanged: (enabled) => unawaited(
        _select(context, enabled ? ThemeMode.dark : ThemeMode.light),
      ),
    ),
  );
}
