import 'dart:io';

import 'package:flutter/material.dart';

class CapturedPhotoPreview extends StatelessWidget {
  const CapturedPhotoPreview({required this.file, super.key});

  final File file;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return ColoredBox(
      color: colors.surface,
      child: Image.file(
        file,
        fit: BoxFit.contain,
        errorBuilder: (context, error, stackTrace) => Center(
          child: Icon(
            Icons.broken_image_outlined,
            color: colors.onSurfaceVariant,
            size: 42,
          ),
        ),
      ),
    );
  }
}
