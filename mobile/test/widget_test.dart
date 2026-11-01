import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobile/main.dart';

void main() {
  testWidgets('home menu and single entry show the foundation UI', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const MyApp());

    expect(find.text('BookLedger'), findsWidgets);
    expect(find.text('Single Entry'), findsOneWidget);
    expect(find.text('Bulk Entry'), findsOneWidget);
    expect(find.text('Not connected'), findsOneWidget);

    await tester.tap(find.byTooltip('Menu'));
    await tester.pumpAndSettle();
    expect(find.text('About'), findsOneWidget);
    expect(find.text('Settings'), findsOneWidget);
    expect(find.text('Exit'), findsOneWidget);
    await tester.tap(find.text('Settings'));
    await tester.pumpAndSettle();
    expect(
      find.text('Settings will be available in a later version.'),
      findsOneWidget,
    );
    await tester.pageBack();
    await tester.pumpAndSettle();

    await tester.tap(find.text('Single Entry'));
    await tester.pumpAndSettle();

    expect(find.bySemanticsLabel('Camera preview area'), findsOneWidget);
    expect(find.text('Scan'), findsOneWidget);
    expect(find.text('Take Photo'), findsOneWidget);
    expect(find.text('Retake'), findsOneWidget);
    expect(find.text('Save'), findsOneWidget);
    expect(find.text('Send'), findsOneWidget);
    expect(find.text('Clear'), findsOneWidget);
    expect(find.text('Not connected'), findsOneWidget);

    for (final label in [
      'Scan',
      'Take Photo',
      'Retake',
      'Save',
      'Send',
      'Clear',
    ]) {
      final button = tester.widget<ElevatedButton>(
        find.widgetWithText(ElevatedButton, label),
      );
      expect(button.onPressed != null, label == 'Scan');
    }
  });

  testWidgets('bulk entry selects a bounded queue and opens capture', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const MyApp());

    await tester.tap(find.text('Bulk Entry'));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('selected-queue-size')), findsOneWidget);
    expect(find.byType(Slider), findsOneWidget);

    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();

    expect(find.text('Queue'), findsWidgets);
    expect(find.text('0 / 5'), findsOneWidget);
    expect(find.text('Send'), findsNothing);
    expect(find.text('Not connected'), findsOneWidget);

    for (final label in [
      'Scan',
      'Take Photo',
      'Retake',
      'Save',
      'Queue',
      'Clear',
    ]) {
      final button = tester.widget<ElevatedButton>(
        find.widgetWithText(ElevatedButton, label),
      );
      expect(button.onPressed != null, label == 'Scan');
    }
  });
}
