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
        padding: const EdgeInsets.all(16),
        children: [
          _sectionHeading(context, 'Pairing'),
          PairingSettingsSection(controller: widget.controller),
          const SizedBox(height: 24),
          _sectionHeading(context, 'Clear Data'),
          const Text(
            'Delete pending captures and forget the desktop pairing on this phone.',
          ),
          const SizedBox(height: 8),
          FilledButton.icon(
            key: const ValueKey('clear-data-action'),
            onPressed: _clearing ? null : _clearData,
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
              foregroundColor: Theme.of(context).colorScheme.onError,
            ),
            icon: const Icon(Icons.delete_outline),
            label: const Text('Clear Data'),
          ),
          if (_clearing)
            const Padding(
              padding: EdgeInsets.all(12),
              child: Center(child: CircularProgressIndicator()),
            ),
          const SizedBox(height: 24),
          _sectionHeading(context, 'Dark Mode'),
          ThemeSelectionSection(settings: widget.settings),
        ],
      ),
    ),
  );
}

Widget _sectionHeading(BuildContext context, String title) => Padding(
  padding: const EdgeInsets.only(bottom: 8),
  child: Text(title, style: Theme.of(context).textTheme.titleLarge),
);

class ThemeSelectionSection extends StatelessWidget {
  const ThemeSelectionSection({required this.settings, super.key});

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
    builder: (context, _) => RadioGroup<ThemeMode>(
      groupValue: settings.themeMode,
      onChanged: (mode) {
        if (mode != null) unawaited(_select(context, mode));
      },
      child: const Column(
        children: [
          RadioListTile<ThemeMode>(
            value: ThemeMode.light,
            title: Text('Default'),
          ),
          RadioListTile<ThemeMode>(value: ThemeMode.dark, title: Text('Dark')),
        ],
      ),
    ),
  );
}
