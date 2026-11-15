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
    required this.onVisitGitHub,
    this.clearPendingPhotos,
    super.key,
  });

  final MobileConnectionController controller;
  final MobileAppSettings settings;
  final Future<void> Function() onVisitGitHub;
  final Future<void> Function()? clearPendingPhotos;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _clearing = false;

  void _openPairing() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => MobileSetupScreen(controller: widget.controller),
      ),
    );
  }

  void _openTheme() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ThemeSelectionScreen(settings: widget.settings),
      ),
    );
  }

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
        padding: const EdgeInsets.all(16),
        children: [
          _SettingsRow(
            icon: Icons.devices_outlined,
            title: 'Pairing',
            subtitle: 'Manage the desktop connection.',
            onTap: _openPairing,
          ),
          _SettingsRow(
            icon: Icons.delete_outline,
            title: 'Clear Data',
            subtitle: 'Delete pending captures and forget pairing.',
            destructive: true,
            enabled: !_clearing,
            onTap: _clearData,
          ),
          _SettingsRow(
            icon: Icons.palette_outlined,
            title: 'Theme',
            subtitle: 'Choose Default or Dark appearance.',
            onTap: _openTheme,
          ),
          if (_clearing)
            const Padding(
              padding: EdgeInsets.all(20),
              child: Center(child: CircularProgressIndicator()),
            ),
        ],
      ),
    ),
  );
}

class _SettingsRow extends StatelessWidget {
  const _SettingsRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.destructive = false,
    this.enabled = true,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final bool destructive;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final color = destructive ? Theme.of(context).colorScheme.error : null;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      child: ListTile(
        minVerticalPadding: 14,
        leading: Icon(icon, color: color),
        title: Text(title, style: TextStyle(color: color)),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: enabled ? onTap : null,
      ),
    );
  }
}

class ThemeSelectionScreen extends StatelessWidget {
  const ThemeSelectionScreen({required this.settings, super.key});

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
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Theme')),
    body: AnimatedBuilder(
      animation: settings,
      builder: (context, _) => SafeArea(
        child: ListView(
          children: [
            RadioGroup<ThemeMode>(
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
                  RadioListTile<ThemeMode>(
                    value: ThemeMode.dark,
                    title: Text('Dark'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
