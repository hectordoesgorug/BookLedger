import 'package:camera/camera.dart';

/// Ask CameraX for the largest still/preview stream and avoid zooming in.
///
/// Camera presets are target resolutions; the platform may choose the nearest
/// supported stream. max avoids forcing the 16:9 720p target used by high.
const photoCameraResolutionPreset = ResolutionPreset.max;

double initialPhotoZoomLevel({
  required double minimum,
  required double maximum,
}) {
  if (!minimum.isFinite || !maximum.isFinite || minimum > maximum) return 1.0;
  return 1.0.clamp(minimum, maximum).toDouble();
}

bool hasAdjustableZoom({required double minimum, required double maximum}) =>
    minimum.isFinite && maximum.isFinite && minimum < maximum;
