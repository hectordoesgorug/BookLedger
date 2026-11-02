import 'dart:developer' as developer;
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';

import 'photo_sharing.dart';

typedef SharePhotoAction = Future<ShareResult> Function(File photo);

class SharePhotoButton extends StatelessWidget {
  const SharePhotoButton({this.file, this.sharePhoto, super.key});

  final File? file;
  final SharePhotoAction? sharePhoto;

  Future<void> _share(BuildContext context) async {
    final photo = file;
    if (photo == null) {
      return;
    }

    try {
      await (sharePhoto ?? shareCapturedPhoto)(photo);
    } catch (error, stackTrace) {
      developer.log(
        'Could not share the captured photo.',
        name: 'BookLedger.photo',
        error: error,
        stackTrace: stackTrace,
      );
      if (!context.mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not share the photo. Try again.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (file == null) {
      return const SizedBox.shrink();
    }

    return TextButton.icon(
      onPressed: () => _share(context),
      icon: const Icon(Icons.share_outlined),
      label: const Text('Share Photo'),
    );
  }
}
