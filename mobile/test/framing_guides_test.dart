import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/capture/framing_guides.dart';

void main() {
  test('guide mode cycles in the required order', () {
    expect(FramingGuideMode.lFrame.next, FramingGuideMode.grid3x3);
    expect(FramingGuideMode.grid3x3.next, FramingGuideMode.grid4x4);
    expect(FramingGuideMode.grid4x4.next, FramingGuideMode.off);
    expect(FramingGuideMode.off.next, FramingGuideMode.lFrame);
  });

  test(
    'guide preference values load and invalid values default to L-frame',
    () {
      expect(framingGuideModeFromPreference('lFrame'), FramingGuideMode.lFrame);
      expect(
        framingGuideModeFromPreference('grid3x3'),
        FramingGuideMode.grid3x3,
      );
      expect(
        framingGuideModeFromPreference('grid4x4'),
        FramingGuideMode.grid4x4,
      );
      expect(framingGuideModeFromPreference('off'), FramingGuideMode.off);
      expect(
        framingGuideModeFromPreference('invalid'),
        FramingGuideMode.lFrame,
      );
      expect(framingGuideModeFromPreference(null), FramingGuideMode.lFrame);
    },
  );

  test('guide strokes are approximately half their previous widths', () {
    expect(framingGuideOutlineStrokeWidth, 2.0);
    expect(framingGuideStrokeWidth, 1.0);
  });

  test('L-frame geometry is centered and portrait-oriented', () {
    final layout = framingGuideLayout(
      const Size(400, 700),
      FramingGuideMode.lFrame,
    );

    expect(layout.frame.center, const Offset(200, 350));
    expect(layout.frame.width / layout.frame.height, closeTo(0.68, 0.001));
    expect(layout.verticalLines, isEmpty);
    expect(layout.horizontalLines, isEmpty);
    expect(layout.centerDot, isFalse);
  });

  test('3x3 grid has two internal lines each way and a centered dot', () {
    final layout = framingGuideLayout(
      const Size(400, 700),
      FramingGuideMode.grid3x3,
    );

    expect(layout.verticalLines, hasLength(2));
    expect(layout.horizontalLines, hasLength(2));
    expect(layout.centerDot, isTrue);
    expect(layout.verticalLines, [
      layout.frame.left + layout.frame.width / 3,
      layout.frame.left + layout.frame.width * 2 / 3,
    ]);
    expect(layout.frame.center, const Offset(200, 350));
  });

  test('4x4 grid has three internal lines each way and a centered dot', () {
    final layout = framingGuideLayout(
      const Size(400, 700),
      FramingGuideMode.grid4x4,
    );

    expect(layout.verticalLines, hasLength(3));
    expect(layout.horizontalLines, hasLength(3));
    expect(layout.centerDot, isTrue);
    expect(layout.verticalLines[1], layout.frame.center.dx);
    expect(layout.horizontalLines[1], layout.frame.center.dy);
  });

  test('guides off has no frame or marks', () {
    final layout = framingGuideLayout(
      const Size(400, 700),
      FramingGuideMode.off,
    );

    expect(layout.frame, Rect.zero);
    expect(layout.verticalLines, isEmpty);
    expect(layout.horizontalLines, isEmpty);
    expect(layout.centerDot, isFalse);
  });

  testWidgets('framing overlay does not intercept camera control taps', (
    WidgetTester tester,
  ) async {
    var tapped = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Stack(
            children: [
              Center(
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => tapped = true,
                  child: const SizedBox(width: 200, height: 200),
                ),
              ),
              Positioned.fill(
                child: IgnorePointer(
                  child: CustomPaint(
                    painter: const FramingGuidesPainter(
                      FramingGuideMode.grid3x3,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );

    await tester.tapAt(tester.getCenter(find.byType(GestureDetector)));

    expect(tapped, isTrue);
  });
}
