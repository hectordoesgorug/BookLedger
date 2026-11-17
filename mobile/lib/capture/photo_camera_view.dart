import 'dart:async';
import 'dart:developer' as developer;
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import 'camera_photo_storage.dart';
import 'framing_guides.dart';
import 'photo_camera_configuration.dart';

class PhotoCameraView extends StatefulWidget {
  const PhotoCameraView({
    required this.captureRequestId,
    required this.guideMode,
    required this.onGuideModeChanged,
    required this.preferredZoom,
    required this.onZoomChanged,
    required this.onCaptured,
    required this.onCancel,
    this.onCaptureFailed,
    super.key,
  });

  final int captureRequestId;
  final FramingGuideMode guideMode;
  final ValueChanged<FramingGuideMode> onGuideModeChanged;
  final double preferredZoom;
  final ValueChanged<double> onZoomChanged;
  final Future<void> Function(String path) onCaptured;
  final VoidCallback onCancel;
  final VoidCallback? onCaptureFailed;

  @override
  State<PhotoCameraView> createState() => _PhotoCameraViewState();
}

class _PhotoCameraViewState extends State<PhotoCameraView>
    with WidgetsBindingObserver {
  CameraController? _controller;
  bool _loading = true;
  bool _takingPhoto = false;
  bool _captureRequestedWhileLoading = false;
  bool _cameraInitializationInFlight = false;
  bool _appResumed = true;
  bool _torchAvailable = true;
  bool _torchOn = false;
  bool _zoomAvailable = false;
  List<double> _supportedZoomLevels = const [];
  double _zoomLevel = 1;
  double _appliedZoomLevel = 1;
  double? _queuedZoomLevel;
  bool _zoomUpdateInFlight = false;
  String? _errorMessage;
  int _cameraGeneration = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_initializeCamera());
  }

  @override
  void didUpdateWidget(covariant PhotoCameraView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.captureRequestId != oldWidget.captureRequestId) {
      unawaited(_takePhoto());
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden) {
      _appResumed = false;
      _cameraGeneration++;
      _queuedZoomLevel = null;
      final controller = _controller;
      _controller = null;
      if (mounted) {
        setState(() {
          _loading = false;
          _torchOn = false;
          _errorMessage = 'Camera paused while the app was in the background.';
        });
      }
      if (controller != null) {
        unawaited(_disposeCameraController(controller));
      }
    } else if (state == AppLifecycleState.resumed) {
      _appResumed = true;
      unawaited(_initializeCamera());
    }
  }

  Future<void> _initializeCamera() async {
    if (!mounted ||
        !_appResumed ||
        _cameraInitializationInFlight ||
        _takingPhoto ||
        _controller?.value.isInitialized == true) {
      return;
    }
    _cameraInitializationInFlight = true;
    final generation = ++_cameraGeneration;
    setState(() {
      _loading = true;
      _errorMessage = null;
    });

    CameraController? candidate;
    try {
      final cameras = await availableCameras();
      if (generation != _cameraGeneration || !_appResumed) {
        return;
      }
      final backCameras = cameras
          .where((camera) => camera.lensDirection == CameraLensDirection.back)
          .toList();
      if (backCameras.isEmpty) {
        throw CameraException(
          'NoBackCamera',
          'No rear-facing camera is available on this device.',
        );
      }

      final selectedCamera = backCameras.first;
      candidate = CameraController(
        selectedCamera,
        photoCameraResolutionPreset,
        enableAudio: false,
      );
      await candidate.initialize();

      var supportedZoomLevels = <double>[];
      var initialZoom = 1.0;
      var zoomAvailable = false;
      var cameraMinimumZoom = double.nan;
      var cameraMaximumZoom = double.nan;
      try {
        cameraMinimumZoom = await candidate.getMinZoomLevel();
        cameraMaximumZoom = await candidate.getMaxZoomLevel();
        supportedZoomLevels = supportedCameraZoomLevels(
          minimum: cameraMinimumZoom,
          maximum: cameraMaximumZoom,
        );
        if (supportedZoomLevels.isNotEmpty) {
          initialZoom = nearestCameraZoomLevel(
            widget.preferredZoom,
            supportedZoomLevels,
          );
          zoomAvailable = supportedZoomLevels.length > 1;
          await candidate.setZoomLevel(initialZoom);
        }
      } on Object catch (error, stackTrace) {
        developer.log(
          'Photo camera zoom controls are unavailable.',
          name: 'BookLedger.camera',
          error: error,
          stackTrace: stackTrace,
        );
        supportedZoomLevels = [];
        initialZoom = 1;
        zoomAvailable = false;
      }

      var torchAvailable = true;
      try {
        await candidate.setFlashMode(FlashMode.off);
      } on Object catch (error, stackTrace) {
        developer.log(
          'Photo camera torch control is unavailable.',
          name: 'BookLedger.camera',
          error: error,
          stackTrace: stackTrace,
        );
        torchAvailable = false;
      }
      developer.log(
        'Photo camera ${selectedCamera.name} (${selectedCamera.lensType}), '
        'preview ${candidate.value.previewSize}, '
        'camera zoom range $cameraMinimumZoom–$cameraMaximumZoom, '
        'discrete levels $supportedZoomLevels; selected $initialZoom.',
        name: 'BookLedger.camera',
      );

      if (!mounted || generation != _cameraGeneration || !_appResumed) {
        await candidate.dispose();
        return;
      }

      _controller = candidate;
      _supportedZoomLevels = supportedZoomLevels;
      _zoomLevel = initialZoom;
      _appliedZoomLevel = initialZoom;
      _zoomAvailable = zoomAvailable;
      _queuedZoomLevel = null;
      _torchAvailable = torchAvailable;
      _torchOn = false;
      candidate = null;
    } on CameraException catch (error, stackTrace) {
      developer.log(
        'Photo camera initialization failed (${error.code}).',
        name: 'BookLedger.camera',
        error: error,
        stackTrace: stackTrace,
      );
      _errorMessage = _cameraErrorText(error);
    } catch (error, stackTrace) {
      developer.log(
        'Photo camera initialization failed.',
        name: 'BookLedger.camera',
        error: error,
        stackTrace: stackTrace,
      );
      _errorMessage = 'The camera could not be initialized.';
    } finally {
      if (candidate != null) {
        await _disposeCameraController(candidate);
      }
      _cameraInitializationInFlight = false;
      if (mounted) {
        if (generation == _cameraGeneration) {
          setState(() => _loading = false);
          if (_errorMessage != null) {
            _captureRequestedWhileLoading = false;
          } else if (_captureRequestedWhileLoading) {
            _captureRequestedWhileLoading = false;
            unawaited(_takePhoto());
          }
        } else if (_appResumed && _controller == null) {
          unawaited(_initializeCamera());
        }
      }
    }
  }

  String _cameraErrorText(CameraException error) {
    switch (error.code) {
      case 'CameraAccessDenied':
      case 'CameraAccessDeniedWithoutPrompt':
        return 'Camera access was denied. Allow it in app settings and try again.';
      case 'CameraAccessRestricted':
        return 'Camera access is restricted on this device.';
      default:
        return 'The camera could not start. Please try again.';
    }
  }

  Future<void> _disposeCameraController(CameraController controller) async {
    if (controller.value.isInitialized) {
      try {
        await controller.setFlashMode(FlashMode.off);
      } on Object catch (error, stackTrace) {
        developer.log(
          'Photo camera torch could not be switched off before disposal.',
          name: 'BookLedger.camera',
          error: error,
          stackTrace: stackTrace,
        );
      }
    }
    try {
      await controller.dispose();
    } catch (error, stackTrace) {
      developer.log(
        'Photo camera disposal failed.',
        name: 'BookLedger.camera',
        error: error,
        stackTrace: stackTrace,
      );
    }
  }

  Future<void> _toggleTorch() async {
    final controller = _controller;
    if (controller == null || !_torchAvailable || _takingPhoto) return;

    final enable = !_torchOn;
    try {
      await controller.setFlashMode(enable ? FlashMode.torch : FlashMode.off);
      if (!mounted || !identical(controller, _controller)) return;
      setState(() => _torchOn = enable);
    } on Object catch (error, stackTrace) {
      developer.log(
        'Photo camera torch change failed.',
        name: 'BookLedger.camera',
        error: error,
        stackTrace: stackTrace,
      );
      if (!mounted || !identical(controller, _controller)) return;
      setState(() {
        if (enable) {
          _torchAvailable = false;
          _torchOn = false;
        }
      });
      if (!enable) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('The torch could not be switched off.')),
        );
      }
    }
  }

  void _requestZoomLevel(double value) {
    final controller = _controller;
    if (controller == null || !_zoomAvailable || _takingPhoto) return;

    final requested = nearestCameraZoomLevel(value, _supportedZoomLevels);
    setState(() => _zoomLevel = requested);
    _queuedZoomLevel = requested;
    if (!_zoomUpdateInFlight) {
      unawaited(_applyQueuedZoom(controller));
    }
  }

  Future<void> _applyQueuedZoom(CameraController controller) async {
    _zoomUpdateInFlight = true;
    try {
      while (_queuedZoomLevel != null) {
        if (!mounted || !_appResumed || !identical(controller, _controller)) {
          _queuedZoomLevel = null;
          return;
        }
        final requested = _queuedZoomLevel!;
        _queuedZoomLevel = null;
        await controller.setZoomLevel(requested);
        _appliedZoomLevel = requested;
        if (mounted && identical(controller, _controller)) {
          widget.onZoomChanged(requested);
        }
      }
    } on Object catch (error, stackTrace) {
      developer.log(
        'Photo camera zoom change failed.',
        name: 'BookLedger.camera',
        error: error,
        stackTrace: stackTrace,
      );
      if (mounted && identical(controller, _controller)) {
        setState(() {
          _zoomAvailable = false;
          _queuedZoomLevel = null;
          _zoomLevel = _appliedZoomLevel;
        });
      }
    } finally {
      _zoomUpdateInFlight = false;
      if (_queuedZoomLevel != null &&
          mounted &&
          _appResumed &&
          identical(controller, _controller)) {
        unawaited(_applyQueuedZoom(controller));
      }
    }
  }

  Future<void> _takePhoto() async {
    final controller = _controller;
    if (_takingPhoto) {
      return;
    }
    if (controller == null || !controller.value.isInitialized) {
      _captureRequestedWhileLoading = _loading;
      return;
    }

    setState(() {
      _takingPhoto = true;
      _torchOn = false;
      _errorMessage = null;
    });
    String? storedPath;
    var photoHandedToWorkflow = false;
    try {
      try {
        await controller.setFlashMode(FlashMode.off);
      } on Object catch (error, stackTrace) {
        developer.log(
          'Photo camera torch could not be switched off before capture.',
          name: 'BookLedger.camera',
          error: error,
          stackTrace: stackTrace,
        );
      }
      final captured = await controller.takePicture();
      final temporaryDirectory = await getTemporaryDirectory();
      // Preview scaling is display-only; retain the original camera JPEG bytes.
      final storedPhoto = await storeOriginalCameraPhoto(
        File(captured.path),
        temporaryDirectory,
      );
      storedPath = storedPhoto.path;

      try {
        await File(captured.path).delete();
      } on FileSystemException {
        // The camera plugin's temporary file may already have been removed.
      }

      if (!mounted) {
        await _deleteFile(storedPath);
        return;
      }
      // The parent replaces this camera widget with the captured image. Let the
      // widget dispose the controller after it leaves the tree, avoiding a
      // frame that still renders a disposed CameraPreview.
      photoHandedToWorkflow = true;
      await widget.onCaptured(storedPath);
      if (mounted) {
        setState(() => _takingPhoto = false);
      }
    } catch (error, stackTrace) {
      developer.log(
        'Photo capture or handoff failed.',
        name: 'BookLedger.camera',
        error: error,
        stackTrace: stackTrace,
      );
      if (storedPath != null && !photoHandedToWorkflow) {
        await _deleteFile(storedPath);
      }
      if (mounted) {
        setState(() {
          _takingPhoto = false;
          _errorMessage = 'The photo could not be captured. Please try again.';
        });
        widget.onCaptureFailed?.call();
      }
      if (_controller == null && _appResumed) {
        unawaited(_initializeCamera());
      }
    }
  }

  Future<void> _deleteFile(String path) async {
    try {
      final file = File(path);
      if (await file.exists()) {
        await file.delete();
      }
    } on FileSystemException {
      // Temporary cleanup is best-effort.
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _cameraGeneration++;
    final controller = _controller;
    _controller = null;
    if (controller != null) {
      unawaited(_disposeCameraController(controller));
    }
    super.dispose();
  }

  Widget _controlButton({
    required String tooltip,
    required IconData icon,
    required VoidCallback? onPressed,
  }) => Container(
    decoration: BoxDecoration(
      color: Colors.black.withAlpha(170),
      shape: BoxShape.circle,
      border: Border.all(color: Colors.white70),
    ),
    child: IconButton(
      tooltip: tooltip,
      onPressed: onPressed,
      iconSize: 18,
      color: Colors.white.withValues(alpha: 0.8),
      disabledColor: Colors.white.withValues(alpha: 0.304),
      constraints: const BoxConstraints.tightFor(width: 48, height: 48),
      padding: EdgeInsets.zero,
      icon: Icon(icon),
    ),
  );

  Widget _guideOverlay() => IgnorePointer(
    child: CustomPaint(painter: FramingGuidesPainter(widget.guideMode)),
  );

  Widget _cameraControls() => Row(
    children: [
      _controlButton(
        tooltip: _torchAvailable
            ? (_torchOn ? 'Torch: on' : 'Torch: off')
            : 'Torch unavailable',
        icon: _torchOn ? Icons.flash_on : Icons.flash_off,
        onPressed: _torchAvailable ? _toggleTorch : null,
      ),
      const SizedBox(width: 8),
      Expanded(
        child: Container(
          height: 48,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          decoration: BoxDecoration(
            color: Colors.black.withAlpha(170),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: Colors.white70),
          ),
          child: Row(
            children: [
              if (_supportedZoomLevels.isNotEmpty) ...[
                Text(
                  '${_zoomLevel.toStringAsFixed(1)}×',
                  key: const ValueKey('camera-zoom-value'),
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(width: 4),
              ],
              if (_zoomAvailable)
                Expanded(
                  child: SliderTheme(
                    data: const SliderThemeData(
                      trackHeight: 2,
                      activeTrackColor: Color(0xFFFFEB3B),
                      inactiveTrackColor: Colors.white70,
                      thumbColor: Colors.white,
                      overlayColor: Color(0x33FFFFFF),
                      thumbShape: RoundSliderThumbShape(enabledThumbRadius: 7),
                      overlayShape: RoundSliderOverlayShape(overlayRadius: 16),
                    ),
                    child: Semantics(
                      label: 'Zoom',
                      value: '${_zoomLevel.toStringAsFixed(1)}×',
                      child: Slider(
                        key: const ValueKey('camera-zoom-slider'),
                        min: _supportedZoomLevels.first,
                        max: _supportedZoomLevels.last,
                        divisions: _supportedZoomLevels.length - 1,
                        value: _zoomLevel,
                        onChanged: _requestZoomLevel,
                      ),
                    ),
                  ),
                )
              else
                Expanded(
                  child: Text(
                    _supportedZoomLevels.isEmpty ? 'Unavailable' : 'Fixed',
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white70),
                  ),
                ),
            ],
          ),
        ),
      ),
      const SizedBox(width: 8),
      _controlButton(
        tooltip: 'Guide: ${widget.guideMode.label}',
        icon: widget.guideMode.icon,
        onPressed: () => widget.onGuideModeChanged(widget.guideMode.next),
      ),
    ],
  );

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    return Stack(
      fit: StackFit.expand,
      children: [
        if (controller != null && controller.value.isInitialized)
          ColoredBox(
            color: Theme.of(context).colorScheme.surface,
            child: ClipRect(
              child: Center(
                child: CameraPreview(
                  controller,
                  child: _takingPhoto ? null : _guideOverlay(),
                ),
              ),
            ),
          )
        else
          ColoredBox(
            color: Colors.black,
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (_loading)
                      const CircularProgressIndicator()
                    else ...[
                      const Icon(
                        Icons.camera_alt_outlined,
                        color: Colors.white,
                        size: 40,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        _errorMessage ?? 'Camera unavailable.',
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: Colors.white),
                      ),
                      const SizedBox(height: 12),
                      OutlinedButton(
                        onPressed: _initializeCamera,
                        child: const Text('Try again'),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        Positioned(
          top: 4,
          right: 4,
          child: IconButton.filledTonal(
            tooltip: 'Back to capture',
            onPressed: widget.onCancel,
            icon: const Icon(Icons.close),
          ),
        ),
        if (controller != null &&
            controller.value.isInitialized &&
            !_takingPhoto)
          Positioned(left: 8, right: 8, bottom: 8, child: _cameraControls()),
      ],
    );
  }
}
