import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import 'capture/bulk_capture_queue.dart';
import 'capture/camera_permission.dart';
import 'capture/captured_photo_preview.dart';
import 'capture/isbn_scanner_screen.dart';
import 'capture/photo_camera_view.dart';
import 'capture/queue_action_button.dart';
import 'capture/share_photo_button.dart';
import 'capture/single_entry_workflow.dart';
import 'connection/mobile_connection_controller.dart';
import 'connection/mobile_setup_screen.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({this.connectionController, super.key});

  final MobileConnectionController? connectionController;

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  late final MobileConnectionController _connectionController;

  @override
  void initState() {
    super.initState();
    _connectionController =
        widget.connectionController ?? MobileConnectionController();
    unawaited(_connectionController.initialize());
  }

  @override
  void dispose() {
    _connectionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const seedColor = Color(0xFF346B63);
    return MaterialApp(
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
      home: HomeScreen(connectionController: _connectionController),
    );
  }
}

enum _HomeMenuAction { about, settings, exit }

class HomeScreen extends StatelessWidget {
  const HomeScreen({this.connectionController, super.key});

  final MobileConnectionController? connectionController;

  void _openPlaceholder(BuildContext context, String title) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => PlaceholderScreen(title: title)),
    );
  }

  void _handleMenu(BuildContext context, _HomeMenuAction action) {
    switch (action) {
      case _HomeMenuAction.about:
        _openPlaceholder(context, 'About');
      case _HomeMenuAction.settings:
        if (connectionController == null) {
          _openPlaceholder(context, 'Settings');
        } else {
          Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) =>
                  MobileSetupScreen(controller: connectionController!),
            ),
          );
        }
      case _HomeMenuAction.exit:
        showDialog<void>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Exit'),
            content: const Text(
              'Exit controls will be available in a later version.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Close'),
              ),
            ],
          ),
        );
    }
  }

  void _openSingleEntry(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => CaptureScreen(
          mode: CaptureMode.single,
          connectionController: connectionController,
        ),
      ),
    );
  }

  void _openBulkEntry(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) =>
            QueueSizeScreen(connectionController: connectionController),
      ),
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
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 22, 20, 18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'BookLedger',
                      style: Theme.of(context).textTheme.headlineMedium
                          ?.copyWith(
                            fontWeight: FontWeight.w700,
                            letterSpacing: -0.5,
                          ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Capture books and send them to your desktop library.',
                      style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const Spacer(),
                    Row(
                      children: [
                        Expanded(
                          child: _EntryCard(
                            label: 'Single Entry',
                            description: 'Capture one book',
                            icon: Icons.book_outlined,
                            onTap: () => _openSingleEntry(context),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: _EntryCard(
                            label: 'Bulk Entry',
                            description: 'Capture a queue',
                            icon: Icons.library_books_outlined,
                            onTap: () => _openBulkEntry(context),
                          ),
                        ),
                      ],
                    ),
                    const Spacer(),
                  ],
                ),
              ),
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
        child: SizedBox(
          height: 168,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Icon(icon, size: 30, color: colors.onPrimaryContainer),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
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
                      style: Theme.of(context).textTheme.bodySmall
                          ?.copyWith(color: colors.onPrimaryContainer),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

enum CaptureMode { single, bulk }

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({
    required this.mode,
    this.queueTarget,
    this.bulkQueue,
    this.workflow,
    this.connectionController,
    super.key,
  });

  final CaptureMode mode;
  final int? queueTarget;
  final BulkCaptureQueue? bulkQueue;
  final SingleEntryWorkflow? workflow;
  final MobileConnectionController? connectionController;

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
  bool _queueing = false;

  bool get _isBulk => widget.mode == CaptureMode.bulk;
  bool get _batchReady => _bulkQueue?.isBatchReady ?? false;
  bool get _canFinishBatch =>
      _isBulk &&
      !_batchReady &&
      !_queueing &&
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
    _ownsBulkQueue = widget.bulkQueue == null;
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

  void _saveCaptureStep() {
    if (_workflow.stage == SingleCaptureStage.isbnScanned) {
      _workflow.saveIsbn();
    } else if (_workflow.stage == SingleCaptureStage.photoCaptured) {
      _workflow.savePhoto();
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

  Future<void> _handlePhotoCaptured(String path) async {
    if (!await _workflow.photoCaptured(path)) {
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
    final isbn = _workflow.pairedIsbn;
    final photoPath = _workflow.photoPath;
    if (!_isBulk ||
        queue == null ||
        queue.isBatchReady ||
        _queueing ||
        isbn == null ||
        photoPath == null ||
        _workflow.stage != SingleCaptureStage.paired) {
      return;
    }

    setState(() => _queueing = true);
    try {
      await queue.addCapture(isbn: isbn, photoPath: photoPath);
      if (mounted) {
        _workflow.resetAfterSuccessfulQueue();
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(
            const SnackBar(
              content: Text(
                'Could not add this capture. Its ISBN and photo are still '
                'available.',
              ),
            ),
          );
      }
    } finally {
      if (mounted) {
        setState(() => _queueing = false);
      }
    }
  }

  void _finishBatchEarly() {
    if (_bulkQueue?.finishEarly() == true) {
      _showQueueMessage('Batch ready. Transfer is not available yet.');
    }
  }

  void _showSendUnavailable() {
    _showQueueMessage(
      'This batch is ready. Transfer will be available in a later version.',
    );
  }

  void _showQueueMessage(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  List<String> get _labels => <String>[
    'Scan',
    'Take Photo',
    'Retake',
    'Save',
    _batchReady ? 'Send' : (_isBulk ? 'Queue' : 'Send'),
    'Clear',
  ];

  bool _buttonEnabled(int index) {
    if (_isBulk) {
      if (_batchReady) {
        return false;
      }
      if (_queueing) {
        return false;
      }
      switch (index) {
        case 0:
          return !_workflow.photoCameraActive && !_workflow.scannerActive;
        case 1:
          return _workflow.photoCameraActive;
        case 2:
          return !_workflow.photoCameraActive &&
              !_workflow.scannerActive &&
              (_workflow.stage == SingleCaptureStage.photoCaptured ||
                  _workflow.stage == SingleCaptureStage.paired);
        case 3:
          return !_workflow.scannerActive &&
              (_workflow.stage == SingleCaptureStage.isbnScanned ||
                  _workflow.stage == SingleCaptureStage.photoCaptured);
        case 4:
          return false;
        case 5:
          return _workflow.hasCaptureData;
        default:
          return false;
      }
    }

    switch (index) {
      case 0:
        return !_workflow.photoCameraActive && !_workflow.scannerActive;
      case 1:
        return _workflow.photoCameraActive;
      case 2:
        return !_workflow.photoCameraActive &&
            !_workflow.scannerActive &&
            (_workflow.stage == SingleCaptureStage.photoCaptured ||
                _workflow.stage == SingleCaptureStage.paired);
      case 3:
        return !_workflow.scannerActive &&
            (_workflow.stage == SingleCaptureStage.isbnScanned ||
                _workflow.stage == SingleCaptureStage.photoCaptured);
      case 4:
        return false;
      case 5:
        return _workflow.hasCaptureData;
      default:
        return false;
    }
  }

  void _onCaptureButtonPressed(int index) {
    switch (index) {
      case 0:
        unawaited(_openScanner());
      case 1:
        _requestPhotoCapture();
      case 2:
        unawaited(_openPhotoCamera());
      case 3:
        _saveCaptureStep();
      case 4:
        if (_batchReady) {
          _showSendUnavailable();
        } else if (_isBulk) {
          unawaited(_queueCurrentCapture());
        }
      case 5:
        unawaited(_clearCapture());
    }
  }

  String _stageDescription() {
    if (_workflow.scannerActive) {
      return 'Scan an ISBN to replace the current capture.';
    }
    switch (_workflow.stage) {
      case SingleCaptureStage.empty:
        return '';
      case SingleCaptureStage.isbnScanned:
        return 'ISBN scanned. Save it to continue.';
      case SingleCaptureStage.isbnSaved:
        return 'ISBN saved. Take a photo of the front cover.';
      case SingleCaptureStage.photoCamera:
        return 'Camera active. Frame the front cover and take a photo.';
      case SingleCaptureStage.photoCaptured:
        return 'Photo captured. Save to pair it with this ISBN.';
      case SingleCaptureStage.paired:
        return _isBulk
            ? 'Capture ready to add to the queue.'
            : 'Capture ready for transfer.';
    }
  }

  Widget _captureCanvas(BuildContext context) {
    if (_workflow.scannerActive) {
      return IsbnScannerPreview(
        onIsbnCaptured: (isbn) => unawaited(_acceptScannedIsbn(isbn)),
        onCancel: _workflow.cancelIsbnScan,
      );
    }
    if (_workflow.photoCameraActive) {
      return PhotoCameraView(
        captureRequestId: _photoCaptureRequestId,
        onCaptured: _handlePhotoCaptured,
        onCancel: _workflow.cancelPhotoCapture,
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
    if (isbn == null) {
      return const SizedBox.shrink();
    }

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
            _workflow.stage == SingleCaptureStage.paired
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
                  isbn,
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
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
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
                  crossAxisCount: 3,
                  mainAxisExtent: 56,
                  mainAxisSpacing: 10,
                  crossAxisSpacing: 10,
                ),
                itemBuilder: (context, index) {
                  if (_isBulk && index == 4) {
                    return QueueActionButton(
                      label: _batchReady ? 'Send' : 'Queue',
                      canTap:
                          _batchReady ||
                          (_workflow.stage == SingleCaptureStage.paired &&
                              !_queueing),
                      canLongPress: _canFinishBatch,
                      onTap: _batchReady
                          ? _showSendUnavailable
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
    );
  }
}

class QueueSizeScreen extends StatefulWidget {
  const QueueSizeScreen({this.connectionController, super.key});

  final MobileConnectionController? connectionController;

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

  Color _color(BuildContext context, MobileConnectionStatus status) =>
      switch (status) {
        MobileConnectionStatus.connected => Colors.green,
        MobileConnectionStatus.pairing || MobileConnectionStatus.connecting =>
          Theme.of(context).colorScheme.primary,
        MobileConnectionStatus.disconnected ||
        MobileConnectionStatus.desktopUnavailable => Colors.orange,
        MobileConnectionStatus.pairingRejected ||
        MobileConnectionStatus.authenticationRejected ||
        MobileConnectionStatus.serviceError => Colors.red,
        MobileConnectionStatus.notPaired => Theme.of(
          context,
        ).colorScheme.outline,
      };

  @override
  Widget build(BuildContext context) {
    final connectionController = controller;
    if (connectionController == null) {
      return _buildStatus(
        context,
        MobileConnectionStatus.notPaired,
        'Not paired',
      );
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
          Icon(Icons.circle, size: 10, color: _color(context, status)),
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
