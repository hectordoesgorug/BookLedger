import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import 'isbn_validator.dart';

class IsbnScannerPreview extends StatefulWidget {
  const IsbnScannerPreview({
    required this.onIsbnCaptured,
    required this.onCancel,
    super.key,
  });

  final ValueChanged<String> onIsbnCaptured;
  final VoidCallback onCancel;

  @override
  State<IsbnScannerPreview> createState() => _IsbnScannerPreviewState();
}

class _IsbnScannerPreviewState extends State<IsbnScannerPreview> {
  late final MobileScannerController _controller;
  DateTime? _lastInvalidFeedback;
  bool _handlingValidBarcode = false;
  bool _closing = false;

  @override
  void initState() {
    super.initState();
    _controller = MobileScannerController(
      autoStart: true,
      facing: CameraFacing.back,
      detectionSpeed: DetectionSpeed.noDuplicates,
      formats: const [BarcodeFormat.ean13, BarcodeFormat.code128],
    );
  }

  Future<void> _handleBarcode(BarcodeCapture capture) async {
    if (_handlingValidBarcode || _closing) {
      return;
    }

    for (final barcode in capture.barcodes) {
      final isbn = IsbnValidator.normalizeAndValidate(barcode.rawValue);
      if (isbn != null) {
        _handlingValidBarcode = true;
        try {
          await _controller.stop();
        } catch (_) {
          // Disposing this preview also releases the scanner if stopping fails.
        }
        if (!mounted) {
          return;
        }
        await SystemSound.play(SystemSoundType.alert);
        await HapticFeedback.mediumImpact();
        if (mounted) {
          widget.onIsbnCaptured(isbn);
        }
        return;
      }
    }

    final now = DateTime.now();
    if (_lastInvalidFeedback == null ||
        now.difference(_lastInvalidFeedback!) >
            const Duration(milliseconds: 1800)) {
      _lastInvalidFeedback = now;
      if (mounted) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(
            const SnackBar(
              content: Text(
                'That barcode is not a valid ISBN. Try another one.',
              ),
              duration: Duration(seconds: 2),
            ),
          );
      }
    }
  }

  Future<void> _cancel() async {
    if (_closing) {
      return;
    }
    _closing = true;
    try {
      await _controller.stop();
    } catch (_) {
      // Disposing this preview also releases the scanner if stopping fails.
    }
    if (mounted) {
      widget.onCancel();
    }
  }

  Widget _errorMessage(BuildContext context, MobileScannerException error) {
    final permissionDenied =
        error.errorCode == MobileScannerErrorCode.permissionDenied;
    return ColoredBox(
      color: Colors.black,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.camera_alt_outlined,
                color: Colors.white,
                size: 42,
              ),
              const SizedBox(height: 16),
              Text(
                permissionDenied
                    ? 'Camera permission was denied.'
                    : 'The scanner camera could not start.',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white),
              ),
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: () async {
                  try {
                    await _controller.start();
                  } catch (_) {
                    if (!context.mounted) {
                      return;
                    }
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Could not start the scanner camera.'),
                      ),
                    );
                  }
                },
                child: const Text('Try again'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        MobileScanner(
          controller: _controller,
          onDetect: _handleBarcode,
          errorBuilder: _errorMessage,
        ),
        IgnorePointer(
          child: Center(
            child: Container(
              width: 300,
              height: 120,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.white, width: 2),
                borderRadius: BorderRadius.circular(16),
              ),
            ),
          ),
        ),
        Positioned(
          top: 4,
          right: 4,
          child: IconButton.filledTonal(
            tooltip: 'Exit ISBN scanning',
            onPressed: _cancel,
            icon: const Icon(Icons.close),
          ),
        ),
        const Positioned(
          left: 20,
          right: 20,
          bottom: 28,
          child: Text(
            'Center the book barcode in the frame',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w600,
              shadows: [Shadow(blurRadius: 4, color: Colors.black)],
            ),
          ),
        ),
      ],
    );
  }
}
