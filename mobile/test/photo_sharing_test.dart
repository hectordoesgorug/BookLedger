import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:share_plus/share_plus.dart';
import 'package:mobile/capture/captured_photo_preview.dart';
import 'package:mobile/capture/photo_sharing.dart';
import 'package:mobile/capture/share_photo_button.dart';

void main() {
  group('captured photo sharing', () {
    late Directory temporaryDirectory;
    late File photo;
    final originalBytes = <int>[0xff, 0xd8, 0xff, 0xd9, 0x31, 0x42];

    setUp(() async {
      temporaryDirectory = await Directory.systemTemp.createTemp(
        'bookledger-photo-share-',
      );
      photo = File('${temporaryDirectory.path}/bookledger_capture_test.jpg');
      await photo.writeAsBytes(originalBytes);
    });

    tearDown(() async {
      if (await temporaryDirectory.exists()) {
        await temporaryDirectory.delete(recursive: true);
      }
    });

    test('shares the stored JPEG path and leaves bytes unchanged', () async {
      ShareParams? receivedParams;

      final result = await shareCapturedPhoto(
        photo,
        launchShare: (params) async {
          receivedParams = params;
          expect(await params.files!.single.readAsBytes(), originalBytes);
          return const ShareResult('selected', ShareResultStatus.success);
        },
      );

      expect(result.status, ShareResultStatus.success);
      expect(receivedParams!.files!.single.path, photo.path);
      expect(receivedParams!.files!.single.mimeType, 'image/jpeg');
      expect(receivedParams!.title, 'Share BookLedger photo');
      expect(await photo.readAsBytes(), originalBytes);
    });

    test('a dismissed share sheet keeps the original photo', () async {
      final result = await shareCapturedPhoto(
        photo,
        launchShare: (_) async =>
            const ShareResult('dismissed', ShareResultStatus.dismissed),
      );

      expect(result.status, ShareResultStatus.dismissed);
      expect(await photo.exists(), isTrue);
      expect(await photo.readAsBytes(), originalBytes);
    });

    testWidgets('share action is hidden until a captured file is supplied', (
      tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: SharePhotoButton())),
      );
      expect(find.text('Share Photo'), findsNothing);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SharePhotoButton(
              file: photo,
              sharePhoto: (_) async =>
                  const ShareResult('dismissed', ShareResultStatus.dismissed),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Share Photo'), findsOneWidget);
    });

    testWidgets('sharing errors show feedback without removing the file', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SharePhotoButton(
              file: photo,
              sharePhoto: (_) async => throw StateError('Share failed'),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Share Photo'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));

      expect(
        find.text('Could not share the photo. Try again.'),
        findsOneWidget,
      );
      expect(await tester.runAsync(() => photo.exists()), isTrue);
      expect(await tester.runAsync(() => photo.readAsBytes()), originalBytes);
    });

    testWidgets('photo preview uses theme surface around a contained image', (
      tester,
    ) async {
      const canvasSurface = Color(0xFFF7F7F3);
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(
              seedColor: Colors.teal,
              surface: canvasSurface,
            ),
          ),
          home: SizedBox(
            width: 400,
            height: 300,
            child: CapturedPhotoPreview(file: photo),
          ),
        ),
      );

      expect(tester.widget<Image>(find.byType(Image)).fit, BoxFit.contain);
      expect(
        tester
            .widget<ColoredBox>(
              find.descendant(
                of: find.byType(CapturedPhotoPreview),
                matching: find.byType(ColoredBox),
              ),
            )
            .color,
        canvasSurface,
      );
    });
  });
}
