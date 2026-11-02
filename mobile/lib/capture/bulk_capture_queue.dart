import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';

import 'isbn_validator.dart';

class CaptureEntry {
  const CaptureEntry({
    required this.captureId,
    required this.isbn,
    required this.photoPath,
    required this.sequence,
    required this.capturedAt,
  });

  final String captureId;
  final String isbn;
  final String photoPath;
  final int sequence;
  final DateTime capturedAt;
}

/// Holds one in-memory bulk session and owns its queued temporary photographs.
class BulkCaptureQueue extends ChangeNotifier {
  BulkCaptureQueue({
    required this.capacity,
    Future<bool> Function(String path)? photoExists,
  }) : _photoExists = photoExists ?? ((path) => File(path).exists()) {
    if (capacity < minimumCapacity || capacity > maximumCapacity) {
      throw ArgumentError.value(
        capacity,
        'capacity',
        'Capacity must be between $minimumCapacity and $maximumCapacity.',
      );
    }
  }

  static const int minimumCapacity = 5;
  static const int maximumCapacity = 20;
  static int _nextCaptureId = 0;

  final int capacity;
  final Future<bool> Function(String path) _photoExists;
  final List<CaptureEntry> _entries = <CaptureEntry>[];
  bool _batchReady = false;
  bool _disposed = false;

  List<CaptureEntry> get entries => List<CaptureEntry>.unmodifiable(_entries);
  int get count => _entries.length;
  bool get isFull => count >= capacity;
  bool get isBatchReady => _batchReady;

  Future<CaptureEntry> addCapture({
    required String isbn,
    required String photoPath,
    DateTime? capturedAt,
  }) async {
    if (_disposed) {
      throw StateError('This capture queue is closed.');
    }
    if (_batchReady || isFull) {
      throw StateError('This capture queue is already full or finished.');
    }

    final normalizedIsbn = IsbnValidator.normalizeAndValidate(isbn);
    if (normalizedIsbn == null) {
      throw ArgumentError.value(isbn, 'isbn', 'A valid ISBN is required.');
    }

    if (!await _photoExists(photoPath)) {
      throw FileSystemException(
        'The captured photo is unavailable.',
        photoPath,
      );
    }
    if (_disposed) {
      throw StateError('This capture queue is closed.');
    }
    if (_entries.any((entry) => entry.photoPath == photoPath)) {
      throw StateError('This photo already belongs to a queued capture.');
    }
    // Recheck after the file operation in case another insertion completed.
    if (_batchReady || isFull) {
      throw StateError('This capture queue is already full or finished.');
    }

    final sequence = _entries.length + 1;
    final id =
        'capture_${DateTime.now().microsecondsSinceEpoch}_'
        '${_nextCaptureId++}';
    final entry = CaptureEntry(
      captureId: id,
      isbn: normalizedIsbn,
      photoPath: photoPath,
      sequence: sequence,
      capturedAt: capturedAt ?? DateTime.now(),
    );
    _entries.add(entry);
    if (isFull) {
      _batchReady = true;
    }
    _notifyListeners();
    return entry;
  }

  bool finishEarly() {
    if (_disposed || _entries.isEmpty || _batchReady) {
      return false;
    }
    _batchReady = true;
    _notifyListeners();
    return true;
  }

  /// Clears this session and deletes only photographs owned by queued entries.
  Future<void> clearSession() async {
    final paths = _entries.map((entry) => entry.photoPath).toSet();
    _entries.clear();
    _batchReady = false;
    if (!_disposed) {
      notifyListeners();
    }
    await Future.wait(paths.map(_deletePhoto));
  }

  Future<void> _deletePhoto(String path) async {
    try {
      final photo = File(path);
      if (await photo.exists()) {
        await photo.delete();
      }
    } on FileSystemException {
      // Temporary cleanup is best-effort.
    }
  }

  void _notifyListeners() {
    if (!_disposed) {
      notifyListeners();
    }
  }

  @override
  void dispose() {
    if (_disposed) {
      return;
    }
    _disposed = true;
    final paths = _entries.map((entry) => entry.photoPath).toSet();
    _entries.clear();
    unawaited(Future.wait(paths.map(_deletePhoto)));
    super.dispose();
  }
}
