import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import 'capture/camera_permission.dart';
import 'capture/isbn_scanner_screen.dart';
import 'capture/photo_camera_view.dart';
import 'capture/single_entry_workflow.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

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
      home: const HomeScreen(),
    );
  }
}

enum _HomeMenuAction { about, settings, exit }

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

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
        _openPlaceholder(context, 'Settings');
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
        builder: (_) => const CaptureScreen(mode: CaptureMode.single),
      ),
    );
  }

  void _openBulkEntry(BuildContext context) {
    Navigator.of(context)
        .push(MaterialPageRoute<void>(builder: (_) => const QueueSizeScreen()));
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
            const ConnectionStatus(),
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
  const CaptureScreen({required this.mode, this.queueTarget, super.key});

  final CaptureMode mode;
  final int? queueTarget;

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  late final SingleEntryWorkflow _workflow;

  bool get _isBulk => widget.mode == CaptureMode.bulk;

  @override
  void initState() {
    super.initState();
    _workflow = SingleEntryWorkflow()..addListener(_onWorkflowChanged);
  }

  void _onWorkflowChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  void dispose() {
    _workflow
      ..removeListener(_onWorkflowChanged)
      ..dispose();
    super.dispose();
  }

  Future<void> _openScanner() async {
    if (!await requestCaptureCameraPermission(
      context,
      purpose: 'scan a book ISBN',
    )) {
      return;
    }
    if (!mounted) {
      return;
    }

    final isbn = await Navigator.of(context).push<String>(
      MaterialPageRoute<String>(builder: (_) => const IsbnScannerScreen()),
    );
    if (!mounted || isbn == null) {
      return;
    }
    final isValidIsbn = await _workflow.scanIsbn(isbn);
    if (!mounted) {
      return;
    }
    if (!isValidIsbn) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('That is not a valid ISBN.')),
      );
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
        // The capture was no longer active; remove its temporary file if present.
      }
    }
  }

  List<String> get _labels => <String>[
    'Scan',
    'Take Photo',
    'Retake',
    'Save',
    _isBulk ? 'Queue' : 'Send',
    'Clear',
  ];

  bool _buttonEnabled(int index) {
    if (_isBulk) {
      return index == 0;
    }

    switch (index) {
      case 0:
        return !_workflow.photoCameraActive;
      case 1:
        return _workflow.stage == SingleCaptureStage.isbnSaved;
      case 2:
        return _workflow.stage == SingleCaptureStage.photoCaptured ||
            _workflow.stage == SingleCaptureStage.paired;
      case 3:
        return _workflow.stage == SingleCaptureStage.isbnScanned ||
            _workflow.stage == SingleCaptureStage.photoCaptured;
      case 4:
        return false;
      case 5:
        return _workflow.hasCaptureData;
      default:
        return false;
    }
  }

  void _onCaptureButtonPressed(int index) {
    if (_isBulk) {
      return;
    }

    switch (index) {
      case 0:
        unawaited(_openScanner());
      case 1:
      case 2:
        unawaited(_openPhotoCamera());
      case 3:
        _saveCaptureStep();
      case 5:
        unawaited(_clearCapture());
    }
  }

  String _stageDescription() {
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
        return 'Capture ready for transfer.';
    }
  }

  Widget _captureCanvas(BuildContext context) {
    if (!_isBulk && _workflow.photoCameraActive) {
      return PhotoCameraView(
        onCaptured: _handlePhotoCaptured,
        onCancel: _workflow.cancelPhotoCapture,
      );
    }

    final photoPath = _isBulk ? null : _workflow.photoPath;
    if (photoPath != null) {
      return Image.file(
        File(photoPath),
        fit: BoxFit.contain,
        errorBuilder: (context, error, stackTrace) => const Center(
          child: Icon(
            Icons.broken_image_outlined,
            color: Colors.white,
            size: 42,
          ),
        ),
      );
    }

    return Semantics(label: 'Camera preview area', child: SizedBox.expand());
  }

  Widget _captureStatus(BuildContext context) {
    final isbn = _workflow.displayedIsbn;
    if (_isBulk || isbn == null) {
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
      appBar: AppBar(title: Text(_isBulk ? 'Bulk Entry' : 'Single Entry')),
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            if (_isBulk)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
                child: Row(
                  children: [
                    Text(
                      'Queue',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const Spacer(),
                    Text(
                      '0 / ${widget.queueTarget ?? 5}',
                      key: const ValueKey('queue-counter'),
                      style: Theme.of(context).textTheme.titleMedium
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              )
            else
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
                  mainAxisExtent: 62,
                  mainAxisSpacing: 10,
                  crossAxisSpacing: 10,
                ),
                itemBuilder: (context, index) {
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
            const SizedBox(height: 12),
            const ConnectionStatus(),
          ],
        ),
      ),
    );
  }
}

class QueueSizeScreen extends StatefulWidget {
  const QueueSizeScreen({super.key});

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
        builder: (_) =>
            CaptureScreen(mode: CaptureMode.bulk, queueTarget: _queueSize),
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
  const ConnectionStatus({super.key});

  @override
  Widget build(BuildContext context) {
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
          Icon(
            Icons.circle,
            size: 10,
            color: Theme.of(context).colorScheme.outline,
          ),
          const SizedBox(width: 10),
          Text(
            'Not connected',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              fontWeight: FontWeight.w500,
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
