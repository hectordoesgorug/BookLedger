import 'dart:math' as math;

import 'package:flutter/material.dart';

enum FramingGuideMode { lFrame, grid3x3, grid4x4, off }

extension FramingGuideModeDetails on FramingGuideMode {
  String get label => switch (this) {
    FramingGuideMode.lFrame => 'L-frame',
    FramingGuideMode.grid3x3 => '3×3 grid',
    FramingGuideMode.grid4x4 => '4×4 grid',
    FramingGuideMode.off => 'Guides off',
  };

  IconData get icon => switch (this) {
    FramingGuideMode.lFrame => Icons.crop_free,
    FramingGuideMode.grid3x3 => Icons.grid_3x3,
    FramingGuideMode.grid4x4 => Icons.grid_on,
    FramingGuideMode.off => Icons.grid_off,
  };

  FramingGuideMode get next => switch (this) {
    FramingGuideMode.lFrame => FramingGuideMode.grid3x3,
    FramingGuideMode.grid3x3 => FramingGuideMode.grid4x4,
    FramingGuideMode.grid4x4 => FramingGuideMode.off,
    FramingGuideMode.off => FramingGuideMode.lFrame,
  };
}

class FramingGuideLayout {
  const FramingGuideLayout({
    required this.frame,
    required this.verticalLines,
    required this.horizontalLines,
    required this.centerDot,
  });

  final Rect frame;
  final List<double> verticalLines;
  final List<double> horizontalLines;
  final bool centerDot;
}

FramingGuideLayout framingGuideLayout(Size size, FramingGuideMode mode) {
  if (mode == FramingGuideMode.off || size.isEmpty) {
    return const FramingGuideLayout(
      frame: Rect.zero,
      verticalLines: [],
      horizontalLines: [],
      centerDot: false,
    );
  }

  const bookAspectRatio = 0.68;
  final width = math.min(
    size.width * 0.86,
    size.height * 0.78 * bookAspectRatio,
  );
  final height = width / bookAspectRatio;
  final frame = Rect.fromCenter(
    center: size.center(Offset.zero),
    width: width,
    height: height,
  );
  final divisions = switch (mode) {
    FramingGuideMode.grid3x3 => 3,
    FramingGuideMode.grid4x4 => 4,
    _ => 1,
  };
  final verticalLines = [
    for (var index = 1; index < divisions; index++)
      frame.left + frame.width * index / divisions,
  ];
  final horizontalLines = [
    for (var index = 1; index < divisions; index++)
      frame.top + frame.height * index / divisions,
  ];

  return FramingGuideLayout(
    frame: frame,
    verticalLines: verticalLines,
    horizontalLines: horizontalLines,
    centerDot:
        mode == FramingGuideMode.grid3x3 || mode == FramingGuideMode.grid4x4,
  );
}

class FramingGuidesPainter extends CustomPainter {
  const FramingGuidesPainter(this.mode);

  final FramingGuideMode mode;

  @override
  void paint(Canvas canvas, Size size) {
    if (mode == FramingGuideMode.off || size.isEmpty) return;

    final layout = framingGuideLayout(size, mode);
    final outline = Paint()
      ..color = Colors.black.withAlpha(180)
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 4;
    final guide = Paint()
      ..color = const Color(0xFFFFEB3B)
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 2;

    if (mode == FramingGuideMode.lFrame) {
      final length = math.min(layout.frame.width, layout.frame.height) * 0.09;
      final frame = layout.frame;
      final corners = <Path>[
        Path()
          ..moveTo(frame.left, frame.top + length)
          ..lineTo(frame.left, frame.top)
          ..lineTo(frame.left + length, frame.top),
        Path()
          ..moveTo(frame.right - length, frame.top)
          ..lineTo(frame.right, frame.top)
          ..lineTo(frame.right, frame.top + length),
        Path()
          ..moveTo(frame.left, frame.bottom - length)
          ..lineTo(frame.left, frame.bottom)
          ..lineTo(frame.left + length, frame.bottom),
        Path()
          ..moveTo(frame.right - length, frame.bottom)
          ..lineTo(frame.right, frame.bottom)
          ..lineTo(frame.right, frame.bottom - length),
      ];
      for (final corner in corners) {
        canvas.drawPath(corner, outline);
        canvas.drawPath(corner, guide);
      }
      return;
    }

    for (final x in layout.verticalLines) {
      canvas.drawLine(
        Offset(x, layout.frame.top),
        Offset(x, layout.frame.bottom),
        outline,
      );
      canvas.drawLine(
        Offset(x, layout.frame.top),
        Offset(x, layout.frame.bottom),
        guide,
      );
    }
    for (final y in layout.horizontalLines) {
      canvas.drawLine(
        Offset(layout.frame.left, y),
        Offset(layout.frame.right, y),
        outline,
      );
      canvas.drawLine(
        Offset(layout.frame.left, y),
        Offset(layout.frame.right, y),
        guide,
      );
    }
    if (layout.centerDot) {
      canvas.drawCircle(
        layout.frame.center,
        5,
        outline..style = PaintingStyle.fill,
      );
      canvas.drawCircle(layout.frame.center, 3, Paint()..color = Colors.red);
    }
  }

  @override
  bool shouldRepaint(covariant FramingGuidesPainter oldDelegate) =>
      oldDelegate.mode != mode;
}
