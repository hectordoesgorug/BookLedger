import 'dart:io';

Future<File> storeOriginalCameraPhoto(
  File originalPhoto,
  Directory temporaryDirectory,
) {
  final filename =
      'bookledger_capture_${DateTime.now().microsecondsSinceEpoch}.jpg';
  final destination = File('${temporaryDirectory.path}/$filename');
  return originalPhoto.copy(destination.path);
}
