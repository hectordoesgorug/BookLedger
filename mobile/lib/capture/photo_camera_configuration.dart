import 'package:camera/camera.dart';

/// Ask CameraX for the largest still/preview stream and avoid zooming in.
///
/// Camera presets are target resolutions; the platform may choose the nearest
/// supported stream. max avoids forcing the 16:9 720p target used by high.
const photoCameraResolutionPreset = ResolutionPreset.max;

double widestSupportedZoomLevel({
  required double minimum,
  required double maximum,
}) {
  return minimum.clamp(1.0, maximum).toDouble();
}
