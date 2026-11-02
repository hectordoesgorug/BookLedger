import 'dart:io';

import 'package:share_plus/share_plus.dart';

typedef SharePhotoLauncher = Future<ShareResult> Function(ShareParams params);

Future<ShareResult> shareCapturedPhoto(
  File photo, {
  SharePhotoLauncher? launchShare,
}) async {
  if (!await photo.exists()) {
    throw FileSystemException(
      'The captured photo is no longer available.',
      photo.path,
    );
  }

  final params = ShareParams(
    title: 'Share BookLedger photo',
    files: [XFile(photo.path, mimeType: 'image/jpeg')],
  );
  return (launchShare ?? SharePlus.instance.share)(params);
}
