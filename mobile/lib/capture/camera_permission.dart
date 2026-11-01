import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';

Future<bool> requestCaptureCameraPermission(
  BuildContext context, {
  required String purpose,
}) async {
  var status = await Permission.camera.status;
  if (!status.isGranted && status.isDenied) {
    status = await Permission.camera.request();
  }
  if (status.isGranted) {
    return true;
  }
  if (!context.mounted) {
    return false;
  }

  final isPermanentlyDenied = status.isPermanentlyDenied || status.isRestricted;
  final shouldOpenSettings = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: const Text('Camera permission needed'),
      content: Text(
        isPermanentlyDenied
            ? 'Camera access is blocked. Enable camera permission in Settings to $purpose.'
            : 'Allow camera access to $purpose.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(dialogContext).pop(false),
          child: const Text('Cancel'),
        ),
        if (isPermanentlyDenied)
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Open settings'),
          ),
      ],
    ),
  );

  if (shouldOpenSettings == true) {
    await openAppSettings();
  }
  return false;
}
