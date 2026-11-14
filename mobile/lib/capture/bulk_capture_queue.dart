import 'dart:async';
import 'dart:io';
import 'dart:math';

import 'package:flutter/foundation.dart';

import 'isbn_validator.dart';

class CaptureEntry {
  const CaptureEntry({
    required this.captureId,
    required this.isbn,
    required this.photoPath,
    required this.sequence,
    required this.capturedAt,
    this.acknowledged = false,
  });

  final String captureId;
  final String? isbn;
  final String photoPath;
  final int sequence;
  final DateTime capturedAt;
  final bool acknowledged;

  CaptureEntry copyWith({bool? acknowledged}) => CaptureEntry(
    captureId: captureId,
    isbn: isbn,
    photoPath: photoPath,
    sequence: sequence,
    capturedAt: capturedAt,
    acknowledged: acknowledged ?? this.acknowledged,
  );
}

String newCaptureUuid() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final hex = bytes
      .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

/// Holds one in-memory bulk session and owns its queued temporary photographs.
class BulkCaptureQueue extends ChangeNotifier {
  BulkCaptureQueue({
    required this.capacity,
    Future<bool> Function(String path)? photoExists,
  }) : _photoExists = photoExists ?? ((path) => File(path).exists()),
       batchId = newCaptureUuid() {
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

  final int capacity;
  String batchId;
  final Future<bool> Function(String path) _photoExists;
  final List<CaptureEntry> _entries = <CaptureEntry>[];
  bool _batchReady = false;
  bool _disposed = false;

  List<CaptureEntry> get entries => List<CaptureEntry>.unmodifiable(_entries);
  int get count => _entries.length;
  bool get isFull => count >= capacity;
  bool get isBatchReady => _batchReady;
  int get unacknowledgedCount =>
      _entries.where((entry) => !entry.acknowledged).length;

  Future<CaptureEntry> addCapture({
    required String? isbn,
    required String photoPath,
    DateTime? capturedAt,
    String? captureId,
  }) async {
    if (_disposed) {
      throw StateError('This capture queue is closed.');
    }
    if (_batchReady || isFull) {
      throw StateError('This capture queue is already full or finished.');
    }

    final normalizedIsbn = isbn == null
        ? null
        : IsbnValidator.normalizeAndValidate(isbn);
    if (isbn != null && normalizedIsbn == null) {
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
    if (_entries.any((entry) => entry.captureId == captureId)) {
      throw StateError('This capture identifier is already queued.');
    }
    if (_batchReady || isFull) {
      throw StateError('This capture queue is already full or finished.');
    }

    final entry = CaptureEntry(
      captureId: captureId ?? newCaptureUuid(),
      isbn: normalizedIsbn,
      photoPath: photoPath,
      sequence: _entries.length + 1,
      capturedAt: capturedAt ?? DateTime.now(),
    );
    _entries.add(entry);
    if (isFull) {
      _batchReady = true;
    }
    _notifyListeners();
    return entry;
  }

  bool markAcknowledged(String captureId) {
    final index = _entries.indexWhere((entry) => entry.captureId == captureId);
    if (index < 0 || _entries[index].acknowledged) {
      return false;
    }
    _entries[index] = _entries[index].copyWith(acknowledged: true);
    _notifyListeners();
    return true;
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
    batchId = newCaptureUuid();
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
