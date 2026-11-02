import 'dart:async';
import 'dart:developer' as developer;
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import 'camera_photo_storage.dart';
import 'photo_camera_configuration.dart';

class PhotoCameraView extends StatefulWidget {
  const PhotoCameraView({
    required this.captureRequestId,
    required this.onCaptured,
    required this.onCancel,
    super.key,
  });

  final int captureRequestId;
  final Future<void> Function(String path) onCaptured;
  final VoidCallback onCancel;

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
      final controller = _controller;
      _controller = null;
      if (mounted) {
        setState(() {
          _loading = false;
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

      // Use the widest zoom level this camera exposes. Clamp to 1x because
      // CameraController's cross-platform contract defines zoom from 1x up.
      final minZoom = await candidate.getMinZoomLevel();
      final maxZoom = await candidate.getMaxZoomLevel();
      final widestSupportedZoom = widestSupportedZoomLevel(
        minimum: minZoom,
        maximum: maxZoom,
      );
      await candidate.setZoomLevel(widestSupportedZoom);
      developer.log(
        'Photo camera ${selectedCamera.name} (${selectedCamera.lensType}), '
        'preview ${candidate.value.previewSize}, '
        'zoom range $minZoom–$maxZoom; selected $widestSupportedZoom.',
        name: 'BookLedger.camera',
      );

      if (!mounted || generation != _cameraGeneration || !_appResumed) {
        await candidate.dispose();
        return;
      }

      _controller = candidate;
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
      _errorMessage = null;
    });
    String? storedPath;
    var photoHandedToWorkflow = false;
    try {
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

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    return Stack(
      fit: StackFit.expand,
      children: [
        if (controller != null && controller.value.isInitialized)
          ColoredBox(
            color: Theme.of(context).colorScheme.surface,
            child: ClipRect(child: Center(child: CameraPreview(controller))),
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
      ],
    );
  }
}
