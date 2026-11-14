import 'dart:async';
import 'dart:io';
import 'dart:math';

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
  String _captureId = _newUuid();
  bool _isbnChosen = false;
  bool _captureConfirmed = false;
  bool _scannerActive = false;
  bool _photoCameraActive = false;
  bool _disposed = false;

  static String _newUuid() {
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final hex = bytes
        .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
        .join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
  }

  SingleCaptureStage get stage {
    if (_photoCameraActive) {
      return SingleCaptureStage.photoCamera;
    }
    if (_photoPath != null) {
      return _captureConfirmed
          ? SingleCaptureStage.paired
          : SingleCaptureStage.photoCaptured;
    }
    if (_scannedIsbn != null) {
      return SingleCaptureStage.isbnScanned;
    }
    return _isbnChosen
        ? SingleCaptureStage.isbnSaved
        : SingleCaptureStage.empty;
  }

  String? get displayedIsbn => _scannedIsbn ?? _savedIsbn;
  String? get photoPath => _photoPath;
  String? get pairedIsbn => _captureConfirmed ? captureIsbn : null;
  String? get captureIsbn => _scannedIsbn ?? _savedIsbn;
  String get captureId => _captureId;
  bool get isCaptureReady => _captureConfirmed && _photoPath != null;
  bool get isbnChosen => _isbnChosen;
  bool get isNoIsbn => _isbnChosen && captureIsbn == null;
  bool get scannerActive => _scannerActive;
  bool get photoCameraActive => _photoCameraActive;
  bool get hasCaptureData => _isbnChosen || _photoPath != null;

  bool beginIsbnScan() {
    if (_scannerActive || _photoCameraActive) {
      return false;
    }
    _scannerActive = true;
    _notifyListeners();
    return true;
  }

  void cancelIsbnScan() {
    if (!_scannerActive) {
      return;
    }
    _scannerActive = false;
    _notifyListeners();
  }

  Future<bool> scanIsbn(String rawValue) async {
    final isbn = IsbnValidator.normalizeAndValidate(rawValue);
    if (isbn == null) {
      return false;
    }
    _scannerActive = false;
    _scannedIsbn = isbn;
    _savedIsbn = null;
    _isbnChosen = true;
    _captureConfirmed = false;
    _notifyListeners();
    return true;
  }

  bool saveIsbn() {
    if (stage != SingleCaptureStage.isbnScanned || _scannedIsbn == null) {
      return false;
    }
    _savedIsbn = _scannedIsbn;
    _scannedIsbn = null;
    _photoCameraActive = true;
    _notifyListeners();
    return true;
  }

  bool chooseManualIsbn(String rawValue) {
    final isbn = IsbnValidator.normalizeAndValidate(rawValue);
    if (isbn == null || _photoCameraActive || _scannerActive) {
      return false;
    }
    _scannedIsbn = null;
    _savedIsbn = isbn;
    _isbnChosen = true;
    _captureConfirmed = false;
    if (_photoPath == null) {
      _photoCameraActive = true;
    }
    _notifyListeners();
    return true;
  }

  bool chooseNoIsbn() {
    if (_photoCameraActive || _scannerActive) {
      return false;
    }
    _scannedIsbn = null;
    _savedIsbn = null;
    _isbnChosen = true;
    _captureConfirmed = false;
    if (_photoPath == null) {
      _photoCameraActive = true;
    }
    _notifyListeners();
    return true;
  }

  void returnToIsbnChoice() {
    if (_photoCameraActive || _scannerActive) {
      return;
    }
    _scannedIsbn = null;
    _savedIsbn = null;
    _isbnChosen = false;
    _captureConfirmed = false;
    _notifyListeners();
  }

  bool beginPhotoCapture() {
    if (!_isbnChosen ||
        _scannedIsbn != null ||
        _photoCameraActive ||
        _scannerActive) {
      return false;
    }
    _photoCameraActive = true;
    _captureConfirmed = false;
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
    if (!_photoCameraActive || !_isbnChosen) {
      return false;
    }
    final previousPhotoPath = _photoPath;
    _photoPath = path;
    _captureConfirmed = false;
    _photoCameraActive = false;
    _notifyListeners();
    if (previousPhotoPath != path) {
      await _deletePhoto(previousPhotoPath);
    }
    return true;
  }

  bool savePhoto() {
    if (stage != SingleCaptureStage.photoCaptured || !_isbnChosen) {
      return false;
    }
    _captureConfirmed = true;
    _notifyListeners();
    return true;
  }

  bool resetAfterSuccessfulQueue() => resetAfterSuccessfulTransfer();

  bool resetAfterSuccessfulTransfer() {
    if (!isCaptureReady || _photoPath == null) {
      return false;
    }
    _scannedIsbn = null;
    _savedIsbn = null;
    _photoPath = null;
    _captureId = _newUuid();
    _isbnChosen = false;
    _captureConfirmed = false;
    _scannerActive = false;
    _photoCameraActive = false;
    _notifyListeners();
    return true;
  }

  Future<void> clear() async {
    final previousPhotoPath = _photoPath;
    _scannedIsbn = null;
    _savedIsbn = null;
    _photoPath = null;
    _captureId = _newUuid();
    _isbnChosen = false;
    _captureConfirmed = false;
    _scannerActive = false;
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
      // Temporary capture cleanup is best-effort.
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
    _scannerActive = false;
    _photoCameraActive = false;
    super.dispose();
  }
}
