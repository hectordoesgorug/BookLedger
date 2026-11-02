import 'package:camera/camera.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/capture/photo_camera_configuration.dart';

void main() {
  test('photo camera targets the highest available resolution', () {
    expect(photoCameraResolutionPreset, ResolutionPreset.max);
  });

  test('widest supported zoom honors the camera minimum', () {
    expect(widestSupportedZoomLevel(minimum: 1.0, maximum: 10.0), 1.0);
  });

  test('widest supported zoom never requests less than 1x', () {
    expect(widestSupportedZoomLevel(minimum: 0.8, maximum: 10.0), 1.0);
  });
}
