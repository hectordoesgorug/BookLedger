import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';

import 'isbn_validator.dart';

enum SingleCaptureStage {
  empty,
  isbnScanned,
  isbnSaved,
  photoCamera,
  photoCaptured,
  paired,
}

class SingleEntryWorkflow extends ChangeNotifier {
  String? _scannedIsbn;
  String? _savedIsbn;
  String? _photoPath;
  String? _pairedIsbn;
  bool _photoCameraActive = false;
  bool _disposed = false;

  SingleCaptureStage get stage {
    if (_photoCameraActive) {
      return SingleCaptureStage.photoCamera;
    }
    if (_pairedIsbn != null && _pairedIsbn == _savedIsbn) {
      return SingleCaptureStage.paired;
    }
    if (_photoPath != null) {
      return SingleCaptureStage.photoCaptured;
    }
    if (_savedIsbn != null) {
      return SingleCaptureStage.isbnSaved;
    }
    if (_scannedIsbn != null) {
      return SingleCaptureStage.isbnScanned;
    }
    return SingleCaptureStage.empty;
  }

  String? get displayedIsbn => _savedIsbn ?? _scannedIsbn;
  String? get photoPath => _photoPath;
  String? get pairedIsbn => _pairedIsbn;
  bool get photoCameraActive => _photoCameraActive;
  bool get hasCaptureData => stage != SingleCaptureStage.empty;

  Future<bool> scanIsbn(String rawValue) async {
    final isbn = IsbnValidator.normalizeAndValidate(rawValue);
    if (isbn == null) {
      return false;
    }

    final previousPhotoPath = _photoPath;
    _scannedIsbn = isbn;
    _savedIsbn = null;
    _photoPath = null;
    _pairedIsbn = null;
    _photoCameraActive = false;
    _notifyListeners();
    await _deletePhoto(previousPhotoPath);
    return true;
  }

  bool saveIsbn() {
    if (stage != SingleCaptureStage.isbnScanned || _scannedIsbn == null) {
      return false;
    }

    _savedIsbn = _scannedIsbn;
    _notifyListeners();
    return true;
  }

  bool beginPhotoCapture() {
    if (_savedIsbn == null || _photoCameraActive) {
      return false;
    }

    _photoCameraActive = true;
    _notifyListeners();
    return true;
  }

  void cancelPhotoCapture() {
    if (!_photoCameraActive) {
      return;
    }

    _photoCameraActive = false;
    _notifyListeners();
  }

  Future<bool> photoCaptured(String path) async {
    if (!_photoCameraActive || _savedIsbn == null) {
      return false;
    }

    final previousPhotoPath = _photoPath;
    _photoPath = path;
    _pairedIsbn = null;
    _photoCameraActive = false;
    _notifyListeners();
    await _deletePhoto(previousPhotoPath);
    return true;
  }

  bool savePhoto() {
    if (stage != SingleCaptureStage.photoCaptured ||
        _savedIsbn == null ||
        _photoPath == null) {
      return false;
    }

    _pairedIsbn = _savedIsbn;
    _notifyListeners();
    return true;
  }

  Future<void> clear() async {
    final previousPhotoPath = _photoPath;
    _scannedIsbn = null;
    _savedIsbn = null;
    _photoPath = null;
    _pairedIsbn = null;
    _photoCameraActive = false;
    _notifyListeners();
    await _deletePhoto(previousPhotoPath);
  }

  void _deletePhotoLater(String? path) {
    if (path != null) {
      unawaited(_deletePhoto(path));
    }
  }

  Future<void> _deletePhoto(String? path) async {
    if (path == null) {
      return;
    }

    try {
      final photoFile = File(path);
      if (await photoFile.exists()) {
        await photoFile.delete();
      }
    } on FileSystemException {
      // Temporary cleanup is best-effort; no user library data is affected.
    }
  }

  void _notifyListeners() {
    if (!_disposed) {
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _deletePhotoLater(_photoPath);
    _photoPath = null;
    super.dispose();
  }
}
