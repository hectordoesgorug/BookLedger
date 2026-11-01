import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

class PhotoCameraView extends StatefulWidget {
  const PhotoCameraView({
    required this.onCaptured,
    required this.onCancel,
    super.key,
  });

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
        unawaited(controller.dispose());
      }
    } else if (state == AppLifecycleState.resumed) {
      _appResumed = true;
      unawaited(_initializeCamera());
    }
  }

  Future<void> _initializeCamera() async {
    if (!mounted || !_appResumed || _loading && _controller != null) {
      return;
    }
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

      candidate = CameraController(
        backCameras.first,
        ResolutionPreset.high,
        enableAudio: false,
      );
      await candidate.initialize();
      if (!mounted || generation != _cameraGeneration || !_appResumed) {
        await candidate.dispose();
        return;
      }

      _controller = candidate;
      candidate = null;
    } on CameraException catch (error) {
      _errorMessage = _cameraErrorText(error);
    } catch (_) {
      _errorMessage = 'The camera could not be initialized.';
    } finally {
      if (candidate != null) {
        await candidate.dispose();
      }
      if (mounted && generation == _cameraGeneration) {
        setState(() => _loading = false);
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

  Future<void> _releaseCamera() async {
    final controller = _controller;
    _controller = null;
    if (controller != null) {
      await controller.dispose();
    }
  }

  Future<void> _takePhoto() async {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized || _takingPhoto) {
      return;
    }

    setState(() {
      _takingPhoto = true;
      _errorMessage = null;
    });
    String? storedPath;
    try {
      final captured = await controller.takePicture();
      final temporaryDirectory = await getTemporaryDirectory();
      final filename =
          'bookledger_capture_${DateTime.now().microsecondsSinceEpoch}.jpg';
      final destination = File('${temporaryDirectory.path}/$filename');
      await File(captured.path).copy(destination.path);
      storedPath = destination.path;

      try {
        await File(captured.path).delete();
      } on FileSystemException {
        // The camera plugin's temporary file may already have been removed.
      }

      await _releaseCamera();
      if (!mounted) {
        await _deleteFile(storedPath);
        return;
      }
      await widget.onCaptured(storedPath);
    } catch (_) {
      if (storedPath != null) {
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
      unawaited(controller.dispose());
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
          CameraPreview(controller)
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
        if (controller != null && controller.value.isInitialized)
          Positioned(
            left: 0,
            right: 0,
            bottom: 16,
            child: Center(
              child: FilledButton.icon(
                onPressed: _takingPhoto ? null : _takePhoto,
                icon: const Icon(Icons.camera_alt),
                label: Text(_takingPhoto ? 'Taking photo…' : 'Take photo'),
              ),
            ),
          ),
      ],
    );
  }
}
