import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'capture/bulk_capture_queue.dart';
import 'capture/camera_permission.dart';
import 'capture/captured_photo_preview.dart';
import 'capture/framing_guides.dart';
import 'capture/isbn_scanner_screen.dart';
import 'capture/photo_camera_view.dart';
import 'capture/queue_action_button.dart';
import 'capture/share_photo_button.dart';
import 'capture/single_entry_workflow.dart';
import 'connection/mobile_connection_controller.dart';
import 'connection/mobile_setup_screen.dart';
import 'settings/about_screen.dart';
import 'settings/mobile_app_settings.dart';
import 'settings/settings_screen.dart';
import 'success_notification.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({this.connectionController, this.appSettings, super.key});

  final MobileConnectionController? connectionController;
  final MobileAppSettings? appSettings;

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  late final MobileConnectionController _connectionController;
  late final MobileAppSettings _appSettings;
  late final bool _ownsAppSettings;

  @override
  void initState() {
    super.initState();
    _connectionController =
        widget.connectionController ?? MobileConnectionController();
    _ownsAppSettings = widget.appSettings == null;
    _appSettings = widget.appSettings ?? MobileAppSettings();
    unawaited(_connectionController.initialize());
    unawaited(_appSettings.initialize());
  }

  @override
  void dispose() {
    _connectionController.dispose();
    if (_ownsAppSettings) _appSettings.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const seedColor = Color(0xFF346B63);
    return AnimatedBuilder(
      animation: _appSettings,
      builder: (context, _) => MaterialApp(
        title: 'BookLedger Mobile',
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: seedColor,
            surface: const Color(0xFFF7F7F3),
          ),
          useMaterial3: true,
          scaffoldBackgroundColor: const Color(0xFFF7F7F3),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFFF7F7F3),
            foregroundColor: Color(0xFF202A28),
            centerTitle: false,
          ),
        ),
        darkTheme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: seedColor,
            brightness: Brightness.dark,
            surface: const Color(0xFF171C1B),
          ),
          useMaterial3: true,
          scaffoldBackgroundColor: const Color(0xFF171C1B),
          appBarTheme: const AppBarTheme(centerTitle: false),
        ),
        themeMode: _appSettings.themeMode,
        home: HomeScreen(
          connectionController: _connectionController,
          appSettings: _appSettings,
        ),
      ),
    );
  }
}

enum _HomeMenuAction { about, settings, exit }

const _externalUrlChannel = MethodChannel('com.bookledger.mobile/external_url');
const _githubUrl = 'https://github.com/hectordoesgorug/BookLedger';

class HomeScreen extends StatelessWidget {
  const HomeScreen({this.connectionController, this.appSettings, super.key});

  final MobileConnectionController? connectionController;
  final MobileAppSettings? appSettings;

  void _openPlaceholder(BuildContext context, String title) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => PlaceholderScreen(title: title)),
    );
  }

  void _handleMenu(BuildContext context, _HomeMenuAction action) {
    switch (action) {
      case _HomeMenuAction.about:
        if (appSettings == null) {
          _openPlaceholder(context, 'About');
        } else {
          Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => AboutScreen(
                settings: appSettings!,
                onVisitGitHub: () => _openGithub(context),
              ),
            ),
          );
        }
      case _HomeMenuAction.settings:
        if (connectionController == null || appSettings == null) {
          _openPlaceholder(context, 'Settings');
        } else {
          Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => SettingsScreen(
                controller: connectionController!,
                settings: appSettings!,
              ),
            ),
          );
        }
      case _HomeMenuAction.exit:
        unawaited(SystemNavigator.pop());
    }
  }

  void _openConnection(BuildContext context) {
    if (connectionController == null) {
      _openPlaceholder(context, 'Mobile App Setup');
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => MobileSetupScreen(controller: connectionController!),
      ),
    );
  }

  void _openSingleEntry(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => CaptureScreen(
          mode: CaptureMode.single,
          connectionController: connectionController,
          appSettings: appSettings,
        ),
      ),
    );
  }

  void _openBulkEntry(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => QueueSizeScreen(
          connectionController: connectionController,
          appSettings: appSettings,
        ),
      ),
    );
  }

  Future<void> _openGithub(BuildContext context) async {
    try {
      final opened = await _externalUrlChannel.invokeMethod<bool>(
        'openGithub',
        _githubUrl,
      );
      if (opened == true || !context.mounted) return;
    } on Object {
      if (!context.mounted) return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Could not open GitHub. Please try again.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: PopupMenuButton<_HomeMenuAction>(
          tooltip: 'Menu',
          icon: const Icon(Icons.menu),
          onSelected: (action) => _handleMenu(context, action),
          itemBuilder: (context) => const [
            PopupMenuItem(value: _HomeMenuAction.about, child: Text('About')),
            PopupMenuItem(
              value: _HomeMenuAction.settings,
              child: Text('Settings'),
            ),
            PopupMenuItem(value: _HomeMenuAction.exit, child: Text('Exit')),
          ],
        ),
      ),
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Image.asset(
                      'assets/banner.png',
                      key: const ValueKey('home-banner'),
                      width: double.infinity,
                      fit: BoxFit.contain,
                    ),
                    const SizedBox(height: 24),
                    _EntryCard(
                      label: 'Single Entry',
                      description: 'Scan and capture one book.',
                      icon: Icons.book_outlined,
                      onTap: () => _openSingleEntry(context),
                    ),
                    const SizedBox(height: 14),
                    _EntryCard(
                      label: 'Bulk Entry',
                      description: 'Capture multiple books in a queue.',
                      icon: Icons.library_books_outlined,
                      onTap: () => _openBulkEntry(context),
                    ),
                    const SizedBox(height: 14),
                    OutlinedButton.icon(
                      onPressed: () => _openConnection(context),
                      icon: const Icon(Icons.devices),
                      label: const Text('Pair / Connect'),
                    ),
                  ],
                ),
              ),
            ),
            Column(
              key: const ValueKey('home-footer-links'),
              mainAxisSize: MainAxisSize.min,
              children: [
                TextButton.icon(
                  onPressed: () => unawaited(_openGithub(context)),
                  icon: Image.asset(
                    'assets/github-mark.png',
                    width: 22,
                    height: 22,
                    semanticLabel: 'GitHub logo',
                  ),
                  label: const Text('Visit GitHub'),
                ),
                if (appSettings != null) ...[
                  const SizedBox(height: 4),
                  AnimatedBuilder(
                    animation: appSettings!,
                    builder: (context, _) => Text(
                      mobileVersionLabel(appSettings!.version),
                      key: const ValueKey('home-version'),
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                ],
              ],
            ),
            ConnectionStatus(controller: connectionController),
          ],
        ),
      ),
    );
  }
}

class _EntryCard extends StatelessWidget {
  const _EntryCard({
    required this.label,
    required this.description,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final String description;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Material(
      color: colors.primaryContainer,
      borderRadius: BorderRadius.circular(20),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Icon(icon, size: 32, color: colors.onPrimaryContainer),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      label,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                        color: colors.onPrimaryContainer,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      description,
                      style: Theme.of(context).textTheme.bodyMedium
                          ?.copyWith(color: colors.onPrimaryContainer),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: colors.onPrimaryContainer),
            ],
          ),
        ),
      ),
    );
  }
}

class _ManualIsbnDialog extends StatefulWidget {
  const _ManualIsbnDialog({required this.initialValue});

  final String initialValue;

  @override
  State<_ManualIsbnDialog> createState() => _ManualIsbnDialogState();
}

class _ManualIsbnDialogState extends State<_ManualIsbnDialog> {
  late final TextEditingController _input;

  @override
  void initState() {
    super.initState();
    _input = TextEditingController(text: widget.initialValue);
  }

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Enter ISBN manually'),
    content: TextField(
      controller: _input,
      autofocus: true,
      keyboardType: TextInputType.number,
      textInputAction: TextInputAction.done,
      onSubmitted: (value) => Navigator.pop(context, value),
      decoration: const InputDecoration(labelText: 'ISBN-10 or ISBN-13'),
    ),
    actions: [
      TextButton(
        onPressed: () => _input.text = '${_input.text}X',
        child: const Text('Add X'),
      ),
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: () => Navigator.pop(context, _input.text),
        child: const Text('Continue'),
      ),
    ],
  );
}

enum CaptureMode { single, bulk }

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({
    required this.mode,
    this.queueTarget,
    this.bulkQueue,
    this.workflow,
    this.connectionController,
    this.appSettings,
    super.key,
  });

  final CaptureMode mode;
  final int? queueTarget;
  final BulkCaptureQueue? bulkQueue;
  final SingleEntryWorkflow? workflow;
  final MobileConnectionController? connectionController;
  final MobileAppSettings? appSettings;

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen>
    with WidgetsBindingObserver {
  late final SingleEntryWorkflow _workflow;
  late final bool _ownsWorkflow;
  BulkCaptureQueue? _bulkQueue;
  late final bool _ownsBulkQueue;
  int _photoCaptureRequestId = 0;
  FramingGuideMode _guideMode = FramingGuideMode.lFrame;
  double _preferredZoom = 1.0;
  late bool _cameraPreferencesReady;
  bool _queueing = false;
  bool _transferring = false;
  String _singleBatchId = newCaptureUuid();

  bool get _isBulk => widget.mode == CaptureMode.bulk;
  bool get _batchReady => _bulkQueue?.isBatchReady ?? false;
  bool get _canFinishBatch =>
      _isBulk &&
      !_batchReady &&
      !_queueing &&
      !_transferring &&
      _bulkQueue!.count > 0 &&
      !_workflow.hasCaptureData &&
      !_workflow.scannerActive &&
      !_workflow.photoCameraActive;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _ownsWorkflow = widget.workflow == null;
    _workflow = widget.workflow ?? SingleEntryWorkflow();
    _workflow.addListener(_onWorkflowChanged);
    _cameraPreferencesReady = widget.appSettings == null;
    final settings = widget.appSettings;
    if (settings != null) {
      unawaited(_loadCameraPreferences(settings));
    }
    _ownsBulkQueue = widget.bulkQueue == null;
    widget.connectionController?.addListener(_onWorkflowChanged);
    if (_isBulk) {
      _bulkQueue = widget.bulkQueue;
      _bulkQueue ??= BulkCaptureQueue(
        capacity: widget.queueTarget ?? BulkCaptureQueue.minimumCapacity,
      );
      _bulkQueue!.addListener(_onWorkflowChanged);
    }
  }

  void _onWorkflowChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  Future<void> _loadCameraPreferences(MobileAppSettings settings) async {
    await settings.initialize();
    if (!mounted) return;
    setState(() {
      _guideMode = framingGuideModeFromPreference(settings.cameraGuideMode);
      _preferredZoom = settings.cameraZoom;
      _cameraPreferencesReady = true;
    });
  }

  void _handleGuideModeChanged(FramingGuideMode mode) {
    if (_guideMode == mode) return;
    setState(() => _guideMode = mode);
    final settings = widget.appSettings;
    if (settings != null) unawaited(_saveGuideMode(settings, mode));
  }

  Future<void> _saveGuideMode(
    MobileAppSettings settings,
    FramingGuideMode mode,
  ) async {
    final saved = await settings.setCameraGuideMode(mode.preferenceValue);
    if (!saved && mounted && _guideMode == mode) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('The camera guide preference could not be saved.'),
        ),
      );
    }
  }

  void _handleZoomChanged(double zoom) {
    if (_preferredZoom != zoom) setState(() => _preferredZoom = zoom);
    final settings = widget.appSettings;
    if (settings != null) unawaited(_saveZoom(settings, zoom));
  }

  Future<void> _saveZoom(MobileAppSettings settings, double zoom) async {
    final saved = await settings.setCameraZoom(zoom);
    if (!saved && mounted && _preferredZoom == zoom) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('The camera zoom preference could not be saved.'),
        ),
      );
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (_isBulk && state == AppLifecycleState.detached) {
      unawaited(_bulkQueue?.clearSession() ?? Future<void>.value());
      unawaited(_workflow.clear());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _workflow.removeListener(_onWorkflowChanged);
    widget.connectionController?.removeListener(_onWorkflowChanged);
    if (_ownsWorkflow) {
      _workflow.dispose();
    }
    _bulkQueue?.removeListener(_onWorkflowChanged);
    if (_ownsBulkQueue) {
      _bulkQueue?.dispose();
    }
    super.dispose();
  }

  Future<void> _openScanner() async {
    if (!await requestCaptureCameraPermission(
      context,
      purpose: 'scan a book ISBN',
    )) {
      return;
    }
    if (mounted) {
      _workflow.beginIsbnScan();
    }
  }

  Future<void> _openManualIsbn() async {
    final value = await showDialog<String>(
      context: context,
      builder: (_) =>
          _ManualIsbnDialog(initialValue: _workflow.displayedIsbn ?? ''),
    );
    if (value == null || !mounted) {
      return;
    }
    if (!_workflow.chooseManualIsbn(value)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Enter a valid ISBN-10 or ISBN-13.')),
      );
    }
  }

  Future<void> _acceptScannedIsbn(String isbn) async {
    final isValidIsbn = await _workflow.scanIsbn(isbn);
    if (!mounted || isValidIsbn) {
      return;
    }
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('That is not a valid ISBN.')));
  }

  void _requestPhotoCapture() {
    if (_workflow.photoCameraActive) {
      setState(() => _photoCaptureRequestId++);
    }
  }

  Future<void> _openPhotoCamera() async {
    if (!await requestCaptureCameraPermission(
      context,
      purpose: 'photograph the book cover',
    )) {
      return;
    }
    if (mounted) {
      _workflow.beginPhotoCapture();
    }
  }

  Future<void> _clearCapture() async {
    if (!_workflow.hasCaptureData) {
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Clear this capture?'),
        content: const Text(
          'The scanned ISBN and any captured photo will be discarded.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Keep capture'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Clear'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await _workflow.clear();
    }
  }

  Future<void> _handlePhotoCaptured(String path, int session) async {
    if (!await _workflow.photoCaptured(path, session: session)) {
      try {
        await File(path).delete();
      } on FileSystemException {
        // The capture was no longer active; remove its temporary file
        // if present.
      }
    }
  }

  Future<void> _queueCurrentCapture() async {
    final queue = _bulkQueue;
    final photoPath = _workflow.photoPath;
    if (!_isBulk ||
        queue == null ||
        queue.isBatchReady ||
        _queueing ||
        !_workflow.isCaptureReady ||
        photoPath == null) {
      return;
    }

    setState(() => _queueing = true);
    try {
      await queue.addCapture(
        isbn: _workflow.captureIsbn,
        photoPath: photoPath,
        captureId: _workflow.captureId,
      );
      if (mounted) {
        _workflow.resetAfterSuccessfulQueue();
        if (!queue.isBatchReady) await _openScanner();
      }
    } catch (_) {
      if (mounted) {
        _showQueueMessage(
          'Could not queue this capture. Its ISBN and photo remain available.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _queueing = false);
      }
    }
  }

  Future<void> _sendSingleCapture() async {
    final controller = widget.connectionController;
    final photoPath = _workflow.photoPath;
    if (_isBulk ||
        controller == null ||
        !controller.isConnected ||
        !_workflow.isCaptureReady ||
        photoPath == null ||
        _transferring) {
      return;
    }
    setState(() => _transferring = true);
    try {
      final entry = CaptureEntry(
        captureId: _workflow.captureId,
        isbn: _workflow.captureIsbn,
        photoPath: photoPath,
        sequence: 1,
        capturedAt: DateTime.now(),
      );
      final sent = await controller.transferCaptures(
        batchId: _singleBatchId,
        entries: [entry],
        onAcknowledged: (_) {},
      );
      if (sent && mounted) {
        await _workflow.clear();
        _singleBatchId = newCaptureUuid();
        _showSuccessMessage(
          'Desktop received the capture. Cataloging will follow on desktop.',
        );
      } else if (mounted) {
        _showQueueMessage(
          controller.message ??
              'Transfer failed. The capture remains available.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _transferring = false);
      }
    }
  }

  Future<void> _sendBulkBatch() async {
    final controller = widget.connectionController;
    final queue = _bulkQueue;
    if (!_isBulk ||
        controller == null ||
        queue == null ||
        !controller.isConnected ||
        !queue.isBatchReady ||
        _transferring) {
      return;
    }
    setState(() => _transferring = true);
    try {
      final sent = await controller.transferCaptures(
        batchId: queue.batchId,
        entries: queue.entries,
        onAcknowledged: queue.markAcknowledged,
      );
      if (sent && mounted) {
        await queue.clearSession();
        _showSuccessMessage(
          'Desktop received the batch. Cataloging will follow on desktop.',
        );
      } else if (mounted) {
        _showQueueMessage(
          controller.message ??
              'Transfer incomplete. Queued captures are retained.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _transferring = false);
      }
    }
  }

  void _finishBatchEarly() {
    if (_bulkQueue?.finishEarly() == true) {
      _showQueueMessage('Batch ready to send.');
    }
  }

  void _showQueueMessage(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  void _showSuccessMessage(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(successNotification(context, message));
  }

  List<String> get _labels => [
    'Take Photo',
    'Retake',
    _isBulk && !_batchReady ? 'Queue' : 'Send',
    'Clear',
  ];

  bool get _operationActive =>
      _queueing || _transferring || widget.connectionController?.isBusy == true;

  bool _buttonEnabled(int index) {
    if (_operationActive || (_isBulk && _batchReady)) return false;
    switch (index) {
      case 0:
        return _workflow.photoCameraActive ||
            (_workflow.isbnChosen &&
                _workflow.photoPath == null &&
                !_workflow.scannerActive);
      case 1:
        return _workflow.isCaptureReady;
      case 2:
        return _workflow.isCaptureReady &&
            widget.connectionController?.isConnected == true;
      case 3:
        return _workflow.hasCaptureData;
      default:
        return false;
    }
  }

  void _onCaptureButtonPressed(int index) {
    switch (index) {
      case 0:
        if (_workflow.photoCameraActive) {
          _requestPhotoCapture();
        } else {
          unawaited(_openPhotoCamera());
        }
      case 1:
        unawaited(_openPhotoCamera());
      case 2:
        unawaited(_sendSingleCapture());
      case 3:
        unawaited(_clearCapture());
    }
  }

  String _stageDescription() {
    if (_workflow.changingIdentifier) {
      return 'Choose a corrected identifier or cancel.';
    }
    if (_workflow.scannerActive) return 'Scan the book ISBN.';
    switch (_workflow.stage) {
      case SingleCaptureStage.empty:
        return 'Choose how to identify this book.';
      case SingleCaptureStage.identifierSelected:
        return 'Ready to photograph the front cover. Tap Take Photo to reopen the camera.';
      case SingleCaptureStage.photoCamera:
        return 'Camera active. Frame the front cover and take a photo.';
      case SingleCaptureStage.ready:
        return _isBulk
            ? 'Capture ready to add to the queue.'
            : 'Capture ready to send.';
    }
  }

  Widget _captureCanvas(BuildContext context) {
    if (_batchReady) {
      return const Center(
        child: Text(
          'Batch ready to send.',
          style: TextStyle(color: Colors.white),
        ),
      );
    }
    if (_workflow.scannerActive) {
      return IsbnScannerPreview(
        onIsbnCaptured: (isbn) => unawaited(_acceptScannedIsbn(isbn)),
        onCancel: _workflow.cancelIsbnScan,
      );
    }
    if (!_workflow.isbnChosen && !_workflow.photoCameraActive) {
      return Center(
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.white,
                    side: const BorderSide(color: Colors.white70),
                  ),
                  onPressed: () => unawaited(_openScanner()),
                  icon: const Icon(Icons.qr_code_scanner),
                  label: const Text('Scan'),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.white,
                    side: const BorderSide(color: Colors.white70),
                  ),
                  onPressed: () => unawaited(_openManualIsbn()),
                  icon: const Icon(Icons.dialpad),
                  label: const Text('Enter Manually'),
                ),
                const SizedBox(height: 12),
                TextButton.icon(
                  style: TextButton.styleFrom(foregroundColor: Colors.white),
                  onPressed: () {
                    _workflow.chooseNoIsbn();
                  },
                  icon: const Icon(Icons.not_interested),
                  label: const Text('No ISBN'),
                ),
                if (_workflow.changingIdentifier)
                  TextButton(
                    style: TextButton.styleFrom(foregroundColor: Colors.white),
                    onPressed: _workflow.cancelIdentifierChange,
                    child: const Text('Cancel change'),
                  ),
              ],
            ),
          ),
        ),
      );
    }
    if (_workflow.photoCameraActive) {
      if (!_cameraPreferencesReady) {
        return const ColoredBox(
          color: Colors.black,
          child: Center(child: CircularProgressIndicator()),
        );
      }
      final session = _workflow.cameraSession;
      return Stack(
        fit: StackFit.expand,
        children: [
          PhotoCameraView(
            key: ValueKey(session),
            captureRequestId: _photoCaptureRequestId,
            guideMode: _guideMode,
            onGuideModeChanged: _handleGuideModeChanged,
            preferredZoom: _preferredZoom,
            onZoomChanged: _handleZoomChanged,
            onCaptured: (path) => _handlePhotoCaptured(path, session),
            onCaptureFailed: () {
              if (!mounted || session != _workflow.cameraSession) return;
              _workflow.cancelPhotoCapture();
              _showQueueMessage(
                'Photo capture failed. The previous photo and identifier are retained; try again.',
              );
            },
            onCancel: _workflow.cancelPhotoCapture,
          ),
          if (_workflow.captureIsbn != null)
            Positioned(
              top: 12,
              left: 12,
              right: 12,
              child: Center(
                child: DecoratedBox(
                  decoration: const BoxDecoration(color: Colors.black54),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 6,
                    ),
                    child: Text(
                      _workflow.captureIsbn!,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
              ),
            ),
        ],
      );
    }

    final photoPath = _workflow.photoPath;
    if (photoPath != null) {
      return CapturedPhotoPreview(file: File(photoPath));
    }

    return Semantics(label: 'Camera preview area', child: SizedBox.expand());
  }

  Widget _captureStatus(BuildContext context) {
    final isbn = _workflow.displayedIsbn;
    if (!_workflow.hasCaptureData) {
      return const SizedBox.shrink();
    }
    final title = isbn ?? 'No ISBN';
    final colors = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: colors.secondaryContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(
            _workflow.stage == SingleCaptureStage.ready
                ? Icons.check_circle_outline
                : Icons.info_outline,
            color: colors.onSecondaryContainer,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  key: const ValueKey('captured-isbn'),
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: colors.onSecondaryContainer,
                  ),
                ),
                Text(
                  _stageDescription(),
                  style: Theme.of(context).textTheme.bodySmall
                      ?.copyWith(color: colors.onSecondaryContainer),
                ),
              ],
            ),
          ),
          if (_workflow.isbnChosen)
            TextButton(
              onPressed: _operationActive ? null : _workflow.returnToIsbnChoice,
              child: const Text('Change'),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope<void>(
      canPop:
          !_workflow.photoCameraActive &&
          !_workflow.scannerActive &&
          !_queueing &&
          !_transferring,
      child: Scaffold(
        appBar: AppBar(
          title: Text(_isBulk ? 'Bulk Entry' : 'Single Entry'),
          actions: [
            SharePhotoButton(
              file: !_isBulk && _workflow.photoPath != null
                  ? File(_workflow.photoPath!)
                  : null,
            ),
          ],
        ),
        body: SafeArea(
          top: false,
          child: Column(
            children: [
              if (_isBulk)
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 8),
                  child: Row(
                    children: [
                      Text(
                        'Queue',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const Spacer(),
                      Text(
                        '${_bulkQueue!.count} / ${_bulkQueue!.capacity}',
                        key: const ValueKey('queue-counter'),
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                    ],
                  ),
                ),
              _captureStatus(context),
              Expanded(
                child: Container(
                  width: double.infinity,
                  margin: const EdgeInsets.fromLTRB(16, 4, 16, 14),
                  clipBehavior: Clip.antiAlias,
                  decoration: BoxDecoration(
                    color: Colors.black,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: _captureCanvas(context),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: _labels.length,
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    mainAxisExtent: 56,
                    mainAxisSpacing: 10,
                    crossAxisSpacing: 10,
                  ),
                  itemBuilder: (context, index) {
                    if (_isBulk && index == 2) {
                      return QueueActionButton(
                        label: _batchReady ? 'Send' : 'Queue',
                        canTap: _batchReady
                            ? widget.connectionController?.isConnected ==
                                      true &&
                                  !_operationActive
                            : _workflow.isCaptureReady && !_operationActive,
                        canLongPress: _canFinishBatch,
                        onTap: _batchReady
                            ? () => unawaited(_sendBulkBatch())
                            : () => unawaited(_queueCurrentCapture()),
                        onLongPress: _finishBatchEarly,
                      );
                    }

                    final enabled = _buttonEnabled(index);
                    return ElevatedButton(
                      onPressed: enabled
                          ? () => _onCaptureButtonPressed(index)
                          : null,
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 4),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        child: Text(_labels[index]),
                      ),
                    );
                  },
                ),
              ),
              if (_isBulk && _canFinishBatch)
                const Padding(
                  padding: EdgeInsets.only(top: 6),
                  child: Text(
                    'Hold Queue to finish batch early.',
                    textAlign: TextAlign.center,
                  ),
                ),
              const SizedBox(height: 12),
              ConnectionStatus(controller: widget.connectionController),
            ],
          ),
        ),
      ),
    );
  }
}

class QueueSizeScreen extends StatefulWidget {
  const QueueSizeScreen({
    this.connectionController,
    this.appSettings,
    super.key,
  });

  final MobileConnectionController? connectionController;
  final MobileAppSettings? appSettings;

  @override
  State<QueueSizeScreen> createState() => _QueueSizeScreenState();
}

class _QueueSizeScreenState extends State<QueueSizeScreen> {
  static const int _minimum = 5;
  static const int _maximum = 20;
  int _queueSize = _minimum;

  void _continue() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(
        builder: (_) => CaptureScreen(
          mode: CaptureMode.bulk,
          queueTarget: _queueSize,
          connectionController: widget.connectionController,
          appSettings: widget.appSettings,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Bulk Entry')),
      body: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 20),
              Text(
                'Queue size',
                style: Theme.of(context).textTheme.headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              Text(
                'Choose how many books to capture in this queue.',
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              const SizedBox(height: 36),
              Center(
                child: Text(
                  '$_queueSize',
                  key: const ValueKey('selected-queue-size'),
                  style: Theme.of(context).textTheme.displayMedium
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
              ),
              Slider(
                value: _queueSize.toDouble(),
                min: _minimum.toDouble(),
                max: _maximum.toDouble(),
                divisions: _maximum - _minimum,
                label: '$_queueSize',
                onChanged: (value) =>
                    setState(() => _queueSize = value.round()),
              ),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: const [Text('$_minimum'), Text('$_maximum')],
              ),
              const Spacer(),
              FilledButton(onPressed: _continue, child: const Text('OK')),
              const SizedBox(height: 12),
            ],
          ),
        ),
      ),
    );
  }
}

class ConnectionStatus extends StatelessWidget {
  const ConnectionStatus({this.controller, super.key});

  final MobileConnectionController? controller;

  String _label(MobileConnectionStatus status) => switch (status) {
    MobileConnectionStatus.notPaired => 'Not paired',
    MobileConnectionStatus.pairing => 'Pairing',
    MobileConnectionStatus.connecting => 'Connecting',
    MobileConnectionStatus.connected => 'Connected',
    MobileConnectionStatus.disconnected => 'Disconnected',
    MobileConnectionStatus.desktopUnavailable => 'Desktop unavailable',
    MobileConnectionStatus.pairingRejected => 'Pairing rejected',
    MobileConnectionStatus.authenticationRejected => 'Pairing no longer valid',
    MobileConnectionStatus.serviceError => 'Connection error',
  };

  Color _color(
    BuildContext context,
    MobileConnectionStatus status,
  ) => switch (status) {
    MobileConnectionStatus.connected => Theme.of(context).colorScheme.tertiary,
    MobileConnectionStatus.pairing ||
    MobileConnectionStatus.connecting => Theme.of(context).colorScheme.primary,
    MobileConnectionStatus.disconnected ||
    MobileConnectionStatus.desktopUnavailable => Theme.of(
      context,
    ).colorScheme.secondary,
    MobileConnectionStatus.pairingRejected ||
    MobileConnectionStatus.authenticationRejected ||
    MobileConnectionStatus.serviceError => Theme.of(context).colorScheme.error,
    MobileConnectionStatus.notPaired => Theme.of(context).colorScheme.outline,
  };

  IconData _icon(MobileConnectionStatus status) => switch (status) {
    MobileConnectionStatus.notPaired => Icons.link_off,
    MobileConnectionStatus.pairing ||
    MobileConnectionStatus.connecting => Icons.sync,
    MobileConnectionStatus.connected => Icons.check_circle,
    MobileConnectionStatus.disconnected ||
    MobileConnectionStatus.desktopUnavailable => Icons.cloud_off,
    MobileConnectionStatus.pairingRejected ||
    MobileConnectionStatus.authenticationRejected ||
    MobileConnectionStatus.serviceError => Icons.error_outline,
  };

  @override
  Widget build(BuildContext context) {
    final connectionController = controller;
    if (connectionController == null) {
      return _buildStatus(context, MobileConnectionStatus.notPaired, null);
    }
    return AnimatedBuilder(
      animation: connectionController,
      builder: (context, _) => _buildStatus(
        context,
        connectionController.status,
        connectionController.message,
      ),
    );
  }

  Widget _buildStatus(
    BuildContext context,
    MobileConnectionStatus status,
    String? message,
  ) {
    final label = _label(status);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 14),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        border: Border(
          top: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
        ),
      ),
      child: Row(
        children: [
          Icon(_icon(status), size: 18, color: _color(context, status)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message == null || message.isEmpty ? label : '$label · $message',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class PlaceholderScreen extends StatelessWidget {
  const PlaceholderScreen({required this.title, super.key});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(child: Text('$title will be available in a later version.')),
    );
  }
}
