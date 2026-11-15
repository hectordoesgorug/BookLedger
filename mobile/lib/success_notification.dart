import 'package:flutter/material.dart';

SnackBar successNotification(BuildContext context, String message) {
  final colors = Theme.of(context).colorScheme;
  return SnackBar(
    content: Text(
      message,
      style: Theme.of(context).textTheme.bodyMedium
          ?.copyWith(color: colors.onTertiaryContainer),
    ),
    backgroundColor: colors.tertiaryContainer,
    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
  );
}
