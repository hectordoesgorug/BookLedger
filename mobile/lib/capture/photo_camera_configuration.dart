import 'package:camera/camera.dart';

/// Ask CameraX for the largest still/preview stream and avoid zooming in.
///
/// Camera presets are target resolutions; the platform may choose the nearest
/// supported stream. max avoids forcing the 16:9 720p target used by high.
const photoCameraResolutionPreset = ResolutionPreset.max;

const discreteCameraZoomLevels = <double>[0.5, 1.0, 1.5, 2.0, 2.5, 3.0];

List<double> supportedCameraZoomLevels({
  required double minimum,
  required double maximum,
}) {
  if (!minimum.isFinite || !maximum.isFinite || minimum > maximum) {
    return const [];
  }
  return [
    for (final level in discreteCameraZoomLevels)
      if (level >= minimum && level <= maximum) level,
  ];
}

double nearestCameraZoomLevel(double preferred, List<double> supported) {
  if (supported.isEmpty) return 1.0;
  return supported.reduce(
    (nearest, level) => (level - preferred).abs() < (nearest - preferred).abs()
        ? level
        : nearest,
  );
}
