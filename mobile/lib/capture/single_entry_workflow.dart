import 'dart:async';
import 'dart:io';
import 'dart:math';

import 'package:flutter/foundation.dart';

import 'isbn_validator.dart';

enum SingleCaptureStage { empty, identifierSelected, photoCamera, ready }

class SingleEntryWorkflow extends ChangeNotifier {
  String? _isbn;
  String? _photoPath;
  String _captureId = _newUuid();
  bool _isbnChosen = false;
  bool _changingIdentifier = false;
  bool _scannerActive = false;
  bool _photoCameraActive = false;
  bool _disposed = false;
  int _cameraSession = 0;

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
    if (_photoCameraActive) return SingleCaptureStage.photoCamera;
    if (isCaptureReady) return SingleCaptureStage.ready;
    return isbnChosen
        ? SingleCaptureStage.identifierSelected
        : SingleCaptureStage.empty;
  }

  String? get displayedIsbn => _isbn;
  String? get captureIsbn => _isbn;
  String? get pairedIsbn => isCaptureReady ? _isbn : null;
  String? get photoPath => _photoPath;
  String get captureId => _captureId;
  int get cameraSession => _cameraSession;
  bool get changingIdentifier => _changingIdentifier;
  bool get isCaptureReady =>
      isbnChosen &&
      _photoPath != null &&
      !_scannerActive &&
      !_photoCameraActive;
  bool get isbnChosen => _isbnChosen && !_changingIdentifier;
  bool get isNoIsbn => isbnChosen && _isbn == null;
  bool get scannerActive => _scannerActive;
  bool get photoCameraActive => _photoCameraActive;
  bool get hasCaptureData => _isbnChosen || _photoPath != null;

  bool beginIsbnScan() {
    if (_disposed || _scannerActive || _photoCameraActive) return false;
    _scannerActive = true;
    _notifyListeners();
    return true;
  }

  void cancelIsbnScan() {
    _scannerActive = false;
    _notifyListeners();
  }

  Future<bool> scanIsbn(String rawValue) async {
    final isbn = IsbnValidator.normalizeAndValidate(rawValue);
    if (isbn == null || _disposed) return false;
    _scannerActive = false;
    _selectIdentifier(isbn);
    return true;
  }

  bool chooseManualIsbn(String rawValue) {
    final isbn = IsbnValidator.normalizeAndValidate(rawValue);
    if (isbn == null || _disposed || _photoCameraActive || _scannerActive) {
      return false;
    }
    _selectIdentifier(isbn);
    return true;
  }

  bool chooseNoIsbn() {
    if (_disposed || _photoCameraActive || _scannerActive) return false;
    _selectIdentifier(null);
    return true;
  }

  void _selectIdentifier(String? isbn) {
    _isbn = isbn;
    _isbnChosen = true;
    _changingIdentifier = false;
    _photoCameraActive = _photoPath == null;
    _cameraSession++;
    _notifyListeners();
  }

  void returnToIsbnChoice() {
    if (_disposed) return;
    _cameraSession++;
    _photoCameraActive = false;
    _scannerActive = false;
    _changingIdentifier = _isbnChosen;
    _notifyListeners();
  }

  void cancelIdentifierChange() {
    _changingIdentifier = false;
    _scannerActive = false;
    _notifyListeners();
  }

  bool beginPhotoCapture() {
    if (_disposed || !isbnChosen || _photoCameraActive || _scannerActive) {
      return false;
    }
    _photoCameraActive = true;
    _cameraSession++;
    _notifyListeners();
    return true;
  }

  void cancelPhotoCapture() {
    _cameraSession++;
    _photoCameraActive = false;
    _notifyListeners();
  }

  Future<bool> photoCaptured(String path, {int? session}) async {
    if (_disposed ||
        !_photoCameraActive ||
        !isbnChosen ||
        path.isEmpty ||
        (session != null && session != _cameraSession)) {
      return false;
    }
    final previousPhotoPath = _photoPath;
    _photoPath = path;
    _photoCameraActive = false;
    _notifyListeners();
    if (previousPhotoPath != path) {
      await _deletePhoto(previousPhotoPath);
    }
    return true;
  }

  bool resetAfterSuccessfulQueue() => resetAfterSuccessfulTransfer();

  bool resetAfterSuccessfulTransfer() {
    if (!isCaptureReady || _photoPath == null) {
      return false;
    }
    _isbn = null;
    _changingIdentifier = false;
    _cameraSession++;
    _photoPath = null;
    _captureId = _newUuid();
    _isbnChosen = false;
    _scannerActive = false;
    _photoCameraActive = false;
    _notifyListeners();
    return true;
  }

  Future<void> clear() async {
    final previousPhotoPath = _photoPath;
    _isbn = null;
    _changingIdentifier = false;
    _cameraSession++;
    _photoPath = null;
    _captureId = _newUuid();
    _isbnChosen = false;
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
