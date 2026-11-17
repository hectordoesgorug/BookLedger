import 'package:camera/camera.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/capture/photo_camera_configuration.dart';

void main() {
  test('photo camera targets the highest available resolution', () {
    expect(photoCameraResolutionPreset, ResolutionPreset.max);
  });

  test('camera starts at 1x within the supported zoom range', () {
    expect(initialPhotoZoomLevel(minimum: 1.0, maximum: 10.0), 1.0);
  });

  test('camera start zoom clamps to a hardware minimum above 1x', () {
    expect(initialPhotoZoomLevel(minimum: 2.0, maximum: 10.0), 2.0);
  });

  test('camera start zoom clamps to a fixed zoom range', () {
    expect(initialPhotoZoomLevel(minimum: 2.0, maximum: 2.0), 2.0);
  });

  test('invalid zoom limits fall back to 1x without enabling the slider', () {
    expect(initialPhotoZoomLevel(minimum: 4.0, maximum: 2.0), 1.0);
    expect(initialPhotoZoomLevel(minimum: double.nan, maximum: 2.0), 1.0);
    expect(hasAdjustableZoom(minimum: 2.0, maximum: 2.0), isFalse);
    expect(hasAdjustableZoom(minimum: 1.0, maximum: 4.0), isTrue);
  });
}
