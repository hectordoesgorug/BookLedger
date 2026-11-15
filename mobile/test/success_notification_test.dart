import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/success_notification.dart';

void main() {
  testWidgets('success notification uses readable Default colors', (
    WidgetTester tester,
  ) async {
    await _verifyTheme(tester, Brightness.light);
  });

  testWidgets('success notification uses readable Dark colors', (
    WidgetTester tester,
  ) async {
    await _verifyTheme(tester, Brightness.dark);
  });
}

Future<void> _verifyTheme(WidgetTester tester, Brightness brightness) async {
  const seedColor = Color(0xFF346B63);
  SnackBar? generated;
  final colors = ColorScheme.fromSeed(
    seedColor: seedColor,
    brightness: brightness,
    surface: brightness == Brightness.light
        ? const Color(0xFFF7F7F3)
        : const Color(0xFF171C1B),
  );
  final theme = ThemeData(colorScheme: colors, useMaterial3: true);

  await tester.pumpWidget(
    MaterialApp(
      theme: theme,
      home: Scaffold(
        body: Builder(
          builder: (context) => TextButton(
            onPressed: () =>
                generated = successNotification(context, 'Operation complete.'),
            child: const Text('Show'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Show'));
  await tester.pump();

  final snackBar = generated!;
  final text = snackBar.content as Text;
  expect(snackBar.backgroundColor, colors.tertiaryContainer);
  expect(text.style?.color, colors.onTertiaryContainer);
  expect(
    snackBar.padding,
    const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
  );
  expect(snackBar.duration, const Duration(seconds: 4));
  final textLuminance = colors.onTertiaryContainer.computeLuminance();
  final backgroundLuminance = colors.tertiaryContainer.computeLuminance();
  final contrast =
      (textLuminance > backgroundLuminance
          ? textLuminance + 0.05
          : backgroundLuminance + 0.05) /
      (textLuminance < backgroundLuminance
          ? textLuminance + 0.05
          : backgroundLuminance + 0.05);
  expect(contrast, greaterThanOrEqualTo(4.5));
}
