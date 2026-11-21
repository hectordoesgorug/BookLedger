import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../settings/mobile_app_settings.dart';
import 'update_installer.dart';
import 'update_service.dart';

class UpdateCheckAction extends StatefulWidget {
  const UpdateCheckAction({
    required this.settings,
    this.service,
    this.installer,
    super.key,
  });
  final MobileAppSettings settings;
  final UpdateService? service;
  final UpdateInstaller? installer;

  @override
  State<UpdateCheckAction> createState() => _UpdateCheckActionState();
}

class _UpdateCheckActionState extends State<UpdateCheckAction> {
  bool _checking = false;

  Future<void> _check() async {
    if (_checking) return;
    setState(() => _checking = true);
    await widget.settings.initialize();
    final service = widget.service ?? UpdateService();
    final result = await service.check(
      widget.settings.version,
      supported: widget.settings.supportsUpdates,
    );
    if (!mounted) return;
    setState(() => _checking = false);
    await showDialog<void>(
      context: context,
      builder: (_) => _UpdateResultDialog(
        result: result,
        settings: widget.settings,
        service: service,
        installer: widget.installer ?? const PlatformUpdateInstaller(),
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

class _UpdateResultDialog extends StatefulWidget {
  const _UpdateResultDialog({
    required this.result,
    required this.settings,
    required this.service,
    required this.installer,
  });
  final UpdateResult result;
  final MobileAppSettings settings;
  final UpdateService service;
  final UpdateInstaller installer;

  @override
  State<_UpdateResultDialog> createState() => _UpdateResultDialogState();
}

class _UpdateResultDialogState extends State<_UpdateResultDialog>
    with WidgetsBindingObserver {
  UpdateDownloadCancellation? _cancellation;
  VerifiedUpdateDownload? _verified;
  UpdateApkEligibility? _eligibility;
  String? _failure;
  String? _installMessage;
  bool _installing = false;
  String _state = 'Idle';
  int _downloaded = 0;
  int? _total;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      _cancellation?.cancel();
    }
  }

  Future<void> _download() async {
    if (_cancellation != null || !widget.settings.supportsUpdates) return;
    final cancellation = UpdateDownloadCancellation();
    setState(() {
      _cancellation = cancellation;
      _state = 'Downloading';
      _downloaded = 0;
      _total = widget.result.assetSize;
      _failure = null;
    });
    try {
      final verified = await widget.service.download(
        widget.result,
        supported: widget.settings.supportsUpdates,
        cancellation: cancellation,
        onProgress: (state, bytes, total) {
          if (mounted) {
            setState(() {
              _state = state;
              _downloaded = bytes;
              _total = total;
            });
          }
        },
      );
      if (!mounted) return;
      setState(() {
        _verified = verified;
        _state = 'Checking APK';
      });
      final installedCode = widget.settings.versionCode;
      if (installedCode == null) {
        throw const FormatException(
          'The installed Android version code is unavailable.',
        );
      }
      final eligibility = await widget.installer.inspect(
        verified,
        installedCode,
      );
      if (eligibility.packageName != 'com.bookledger.mobile' ||
          eligibility.versionCode <= installedCode) {
        throw const FormatException(
          'This APK is not a newer BookLedger Mobile update.',
        );
      }
      if (mounted) {
        setState(() {
          _eligibility = eligibility;
          _state = 'Verified Download';
        });
      }
    } on UpdateDownloadCanceled {
      if (mounted) setState(() => _state = 'Canceled');
    } on Object catch (error) {
      if (mounted) {
        setState(() {
          _state = 'Failed';
          _failure = error.toString();
        });
      }
    } finally {
      if (mounted) setState(() => _cancellation = null);
    }
  }

  Future<void> _install() async {
    final verified = _verified;
    final eligibility = _eligibility;
    if (verified == null || eligibility == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Install BookLedger update?'),
        content: const Text(
          'Any unsent captures may be lost if the update closes BookLedger. '
          'Send pending entries to the desktop before proceeding.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const ValueKey('confirm-install-update'),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Continue'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() {
      _installing = true;
      _installMessage = 'Opening Android installer…';
    });
    try {
      final status = await widget.installer.install(
        verified,
        eligibility.versionCode,
      );
      if (!mounted) return;
      setState(() {
        _installing = false;
        _installMessage = switch (status) {
          'installed' =>
            'Android confirmed BookLedger ${widget.result.available} is installed.',
          'permissionRequired' => 'Allow BookLedger to install updates in Android settings, then tap Install Update again.',
          'canceled' => 'Installation was canceled. The existing app and its data were not cleared.',
          'unavailable' => 'Android could not open the package installer. The existing app remains available.',
          _ => 'Android did not confirm the update. Reopen BookLedger and check its installed version.',
        };
      });
    } on Object catch (error) {
      if (mounted) {
        setState(() {
          _installing = false;
          _installMessage = 'Could not start installation: $error';
        });
      }
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _cancellation?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      _verified == null
          ? (_state == 'Idle' ? widget.result.state : _state)
          : 'Verified Download',
    ),
    content: SizedBox(
      width: 500,
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Installed: ${widget.result.installed}${widget.settings.versionCode == null ? '' : ' (code ${widget.settings.versionCode})'}',
            ),
            Text('Available: ${widget.result.available ?? 'unknown'}'),
            if (widget.result.assetName != null)
              Text(
                'Package: ${widget.result.assetName} (${widget.result.assetSize ?? 'unknown'} bytes)',
              ),
            const SizedBox(height: 12),
            Text(
              _verified == null
                  ? widget.result.message
                  : 'Verified ${_verified!.file.uri.pathSegments.last}. The checksum matches the official release manifest.'
                        '${_eligibility == null ? (_failure == null ? ' Checking package details…' : ' Android rejected the APK for installation.') : ' Package and version code are eligible for installation.'}',
            ),
            if (_cancellation != null) ...[
              const SizedBox(height: 12),
              LinearProgressIndicator(
                value: _total == null || _total == 0
                    ? null
                    : _downloaded / _total!,
              ),
              const SizedBox(height: 6),
              Text(
                _state == 'Verifying'
                    ? 'Verifying SHA-256…'
                    : '${_downloaded.toString()} of ${_total?.toString() ?? 'unknown'} bytes',
              ),
            ],
            if (_verified != null) ...[
              const SizedBox(height: 8),
              SelectableText(_verified!.file.path),
            ],
            if (_failure != null) ...[
              const SizedBox(height: 8),
              Text('The APK could not be checked for installation: $_failure'),
            ],
            if (_installMessage != null) ...[
              const SizedBox(height: 8),
              Text(_installMessage!),
            ],
            if (widget.result.notes.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text(
                'Release Notes',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              SelectableText(widget.result.notes),
            ],
          ],
        ),
      ),
    ),
    actions: [
      if (widget.result.releaseUrl != null)
        TextButton(
          onPressed: () async {
            try {
              final opened = await const MethodChannel(
                'com.bookledger.mobile/external_url',
              ).invokeMethod<bool>('openRelease', widget.result.releaseUrl);
              if (opened != true) throw StateError('Browser unavailable');
            } on Object {
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
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
      if (_verified == null &&
          widget.result.state == 'Update Available' &&
          widget.settings.supportsUpdates)
        TextButton(
          onPressed: _cancellation == null ? _download : null,
          child: const Text('Download & Verify'),
        ),
      if (_cancellation != null)
        TextButton(
          onPressed: () {
            _cancellation?.cancel();
            setState(() => _state = 'Canceling');
          },
          child: const Text('Cancel Download'),
        ),
      if (_eligibility != null && _verified != null)
        FilledButton(
          key: const ValueKey('install-update'),
          onPressed: _installing ? null : _install,
          child: Text(_installing ? 'Opening Installer…' : 'Install Update'),
        ),
      TextButton(
        onPressed: () => Navigator.of(context).pop(),
        child: const Text('Close'),
      ),
    ],
  );
}
